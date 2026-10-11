"""公开标准元数据（只读）。

数据来源：

* ``data/sources/openstd/manifest.json`` —— 国家标准全文公开系统的采集清单；
* ``data/sources/normalized/openstd/`` —— 每个标准对应的 Markdown；
* ``data/sources/acquisition.json`` —— 采集时间戳。

本模块只做归一化与只读拼装：**不编造任何字段**，清单里没有的信息一律留空串，
清单缺失或损坏时返回空结构而不是抛异常。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

#: 标准清单中的状态白名单。清单里出现白名单以外的值按「未知」处理。
KNOWN_STATUSES = ("现行", "即将实施", "已废止")

DEFAULT_TYPE = "国家标准"
# 国家标准全文公开系统在清单里存的是内部简写，这里给出可读映射。
# 原始值保留在 type_raw，未收录的简写不猜测，直接回落到原值。
TYPE_LABELS = {
    "强标": "强制性国家标准",
    "推标": "推荐性国家标准",
    "指导": "指导性技术文件",
    "国家标准": "国家标准",
}

#: 空结构的样子。请用 :func:`empty_standards` 取用，避免共享同一份字典。
EMPTY_STANDARDS: dict[str, Any] = {
    "generated_at": "",
    "counts": {"total": 0, "active": 0, "pending": 0},
    "items": [],
}

#: 条目字段顺序，便于阅读与测试对照。
STANDARD_FIELDS = (
    "code",
    "title",
    "type",
    "status",
    "published",
    "implemented",
    "source_url",
    "preview_url",
    "content_imported",
    "normalized_file",
)


def empty_standards() -> dict[str, Any]:
    """返回一份全新的空结构，调用方可以安全修改自己那一份。"""
    return {
        "generated_at": "",
        "counts": {"total": 0, "active": 0, "pending": 0},
        "items": [],
    }


def normalize_date(value: Any) -> str:
    """把 ``2020-07-01 00:00:00.0`` 这类值规整成 ``2020-07-01``。

    取不到日期部分时原样保留（去掉首尾空白）；不是字符串则返回空串。
    """
    if not isinstance(value, str):
        return ""
    text = value.strip()
    if not text:
        return ""
    head = text.split("T", 1)[0].split(" ", 1)[0].strip()
    return head or text


def normalize_status(value: Any) -> str:
    """状态缺省为「未知」，保证返回值始终落在已知集合内。"""
    if isinstance(value, str):
        text = value.strip()
        if text in KNOWN_STATUSES:
            return text
    return "未知"


def _as_text(value: Any) -> str:
    """只接受字符串字段；其它类型一律留空，避免把结构体写进 JSON。"""
    return value.strip() if isinstance(value, str) else ""


def _read_json(path: Path) -> Any:
    """容错读取 JSON；文件不存在、不可读或内容损坏时返回 ``None``。"""
    try:
        if not path.is_file():
            return None
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError):
        return None


def _generated_at(project_root: Path) -> str:
    """采集时间：优先 ``completed_at``，其次 ``started_at``，都取不到就空串。"""
    payload = _read_json(project_root / "data" / "sources" / "acquisition.json")
    if not isinstance(payload, dict):
        return ""
    for key in ("completed_at", "started_at"):
        value = _as_text(payload.get(key))
        if value:
            return value
    return ""


def _manifest_entries(project_root: Path) -> list[Any]:
    """读取 openstd 清单；同时兼容 ``normalized/openstd`` 下的同名副本。"""
    sources_dir = project_root / "data" / "sources"
    for path in (
        sources_dir / "openstd" / "manifest.json",
        sources_dir / "normalized" / "openstd" / "manifest.json",
    ):
        payload = _read_json(path)
        if isinstance(payload, list):
            return payload
    return []


def _normalized_files(project_root: Path) -> list[str]:
    """``data/sources/normalized/openstd`` 下实际存在的 Markdown 文件名。"""
    directory = project_root / "data" / "sources" / "normalized" / "openstd"
    try:
        if not directory.is_dir():
            return []
        return sorted(
            entry.name
            for entry in directory.glob("*.md")
            if entry.is_file()
        )
    except OSError:
        return []


def _match_normalized_file(code: str, files: list[str]) -> str:
    """按标准号匹配标准化文件名，例如 ``GB/T 13869-2017`` → ``03_GB_T 13869-2017.md``。

    文件名里斜杠会被写成下划线，因此两种写法都试；匹配不到返回空串。
    """
    if not code:
        return ""
    candidates = (code, code.replace("/", "_"))
    for candidate in candidates:
        for name in files:
            if candidate in name:
                return name
    return ""


def _build_item(record: Any, files: list[str]) -> dict[str, Any]:
    """把一条清单记录转成接口条目，单个记录损坏时退化为空字段。"""
    if not isinstance(record, dict):
        record = {}
    code = _as_text(record.get("code"))
    raw_type = _as_text(record.get("type"))
    item_type = raw_type or DEFAULT_TYPE
    return {
        "code": code,
        "title": _as_text(record.get("title")),
        "type": item_type,
        "type_raw": raw_type,
        "type_label": TYPE_LABELS.get(raw_type, item_type),
        "status": normalize_status(record.get("status")),
        "published": normalize_date(record.get("published")),
        "implemented": normalize_date(record.get("implemented")),
        "source_url": _as_text(record.get("source_url")),
        "preview_url": _as_text(record.get("preview_url")),
        "content_imported": _as_text(record.get("content_imported")),
        "normalized_file": _match_normalized_file(code, files),
    }


def load_standards(project_root: Path) -> dict[str, Any]:
    """只读加载公开标准元数据列表。

    返回 ``generated_at`` / ``counts`` / ``items`` 三段结构；清单缺失或 JSON
    损坏时返回空结构，**绝不抛异常**。
    """
    if isinstance(project_root, Path):
        root = project_root
    elif isinstance(project_root, str) and project_root.strip():
        root = Path(project_root)
    else:
        # None / 空串 / 其它类型：不猜测工作目录，直接给空结构。
        return empty_standards()

    entries = _manifest_entries(root)
    if not entries:
        return empty_standards()

    files = _normalized_files(root)
    items = [_build_item(record, files) for record in entries]

    total = len(items)
    active = sum(1 for item in items if item["status"] == "现行")
    pending = sum(1 for item in items if item["status"] == "即将实施")
    return {
        "generated_at": _generated_at(root),
        "counts": {"total": total, "active": active, "pending": pending},
        "items": items,
    }
