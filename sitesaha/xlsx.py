"""xlsx 读取（第 16 轮 §11.C）。

为什么手写而不是用 openpyxl：项目约束是"不新增依赖"，且要能在
离线/内网环境跑。xlsx 本质是一个 zip 包，里面的工作表是 XML，
用标准库 zipfile + xml.etree 就能读。

只读需要的部分：
  · xl/sharedStrings.xml —— 共享字符串表（单元格文本大多存这里）
  · xl/worksheets/sheet1.xml —— 第一张工作表
  · xl/workbook.xml —— 找第一张表的实际文件名

不支持：公式求值（只取缓存值）、合并单元格展开、样式。
对本用途（一行一条检查项）足够。
"""

from __future__ import annotations

import re
import zipfile
from io import BytesIO
from xml.etree import ElementTree

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
REL_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
PKG_REL_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"

MAX_ROWS = 1000
MAX_COLS = 12


class XlsxError(ValueError):
    """xlsx 读取失败，message 面向用户。"""


def _shared_strings(archive: zipfile.ZipFile) -> list[str]:
    try:
        raw = archive.read("xl/sharedStrings.xml")
    except KeyError:
        return []
    strings: list[str] = []
    root = ElementTree.fromstring(raw)
    for si in root.findall(f"{NS}si"):
        # 一个 si 可能由多个 r/t 组成（富文本），拼起来
        parts = [node.text or "" for node in si.iter(f"{NS}t")]
        strings.append("".join(parts))
    return strings


def _first_sheet_path(archive: zipfile.ZipFile) -> str:
    """按 workbook.xml + rels 找第一张工作表的实际路径。"""
    try:
        workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
        rels = ElementTree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    except KeyError:
        # 退化：直接找第一个 sheet xml
        for name in archive.namelist():
            if re.match(r"xl/worksheets/sheet\d+\.xml$", name):
                return name
        raise XlsxError("这个文件里没有找到工作表，可能不是有效的 xlsx。")

    rel_map = {}
    for rel in rels.findall(f"{PKG_REL_NS}Relationship"):
        rel_map[rel.get("Id")] = rel.get("Target", "")

    sheets = workbook.find(f"{NS}sheets")
    if sheets is None:
        raise XlsxError("这个文件里没有找到工作表。")
    first = sheets.find(f"{NS}sheet")
    if first is None:
        raise XlsxError("这个文件里没有找到工作表。")

    rel_id = first.get(f"{REL_NS}id")
    target = rel_map.get(rel_id or "", "")
    if not target:
        raise XlsxError("无法定位工作表内容。")
    if target.startswith("/"):
        return target.lstrip("/")
    if target.startswith("xl/"):
        return target
    return "xl/" + target


def _column_index(ref: str) -> int:
    """把 A1 / C7 这样的引用转成 0 基列号。"""
    letters = re.match(r"([A-Z]+)", ref or "")
    if not letters:
        return 0
    index = 0
    for char in letters.group(1):
        index = index * 26 + (ord(char) - ord("A") + 1)
    return index - 1


def _cell_text(cell: ElementTree.Element, shared: list[str]) -> str:
    kind = cell.get("t")
    if kind == "inlineStr":
        node = cell.find(f"{NS}is")
        if node is None:
            return ""
        return "".join(part.text or "" for part in node.iter(f"{NS}t"))
    value = cell.find(f"{NS}v")
    if value is None or value.text is None:
        return ""
    text = value.text
    if kind == "s":
        try:
            return shared[int(text)]
        except (ValueError, IndexError):
            return ""
    return text


def read_rows(data: bytes, sheet: int = 1) -> list[list[str]]:
    """读第一张（或指定）工作表，返回二维字符串数组。

    空行会被保留占位，交给上层的解析器判断，避免行号错位。
    """
    try:
        archive = zipfile.ZipFile(BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise XlsxError("这个文件不是有效的 xlsx（可能是改了扩展名的 csv 或旧版 xls）。") from exc

    with archive:
        names = archive.namelist()
        if "xl/workbook.xml" not in names and not any(
            n.startswith("xl/worksheets/") for n in names
        ):
            raise XlsxError("这个文件不是有效的 xlsx（缺少工作表结构）。")

        shared = _shared_strings(archive)
        path = _first_sheet_path(archive)
        try:
            sheet_root = ElementTree.fromstring(archive.read(path))
        except KeyError as exc:
            raise XlsxError("工作表内容读不出来，文件可能已损坏。") from exc

    rows: list[list[str]] = []
    sheet_data = sheet_root.find(f"{NS}sheetData")
    if sheet_data is None:
        return rows

    for row in sheet_data.findall(f"{NS}row"):
        cells: list[str] = [""] * MAX_COLS
        for cell in row.findall(f"{NS}c"):
            index = _column_index(cell.get("r", "A1"))
            if 0 <= index < MAX_COLS:
                cells[index] = _cell_text(cell, shared).strip()
        rows.append(cells)
        if len(rows) >= MAX_ROWS:
            break

    return rows


def to_text(data: bytes) -> str:
    """把 xlsx 转成 parse_delimited 能吃的文本（逗号分隔）。

    这样导入解析逻辑只有一份，csv/txt/md/xlsx 走同一条路。
    """
    lines: list[str] = []
    for row in read_rows(data):
        cells = [cell.replace(",", "，") for cell in row]
        while cells and not cells[-1]:
            cells.pop()
        if not cells:
            continue
        lines.append(",".join(cells))
    return "\n".join(lines)
