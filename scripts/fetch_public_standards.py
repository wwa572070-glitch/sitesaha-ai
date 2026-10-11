from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lxml import html


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sitesaha.text import normalize_text


JNCC_URL = (
    "https://jncc.jinan.gov.cn/col45066/art/2021/art_45066_3462265.html"
)
OPENSTD_SEARCH = (
    "https://openstd.samr.gov.cn/bzgk/std/std_list"
    "?p.p1=0&p.p90=circulation_date&p.p91=desc&p.p2={query}"
)
OPENSTD_DETAIL = "https://openstd.samr.gov.cn/bzgk/std/newGbInfo?hcno={hcno}"
OPENSTD_PREVIEW = (
    "https://openstd.samr.gov.cn/bzgk/std/showGb"
    "?type=online&hcno={hcno}&request_locale=zh"
)
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 Chrome/126 Safari/537.36"
)

# OpenStd 检索的瞬时失败重试策略；两次检索之间留出间隔，避免被站点限流。
RETRY_TIMES = 3
RETRY_DELAY = 2.0
REQUEST_INTERVAL = 0.8


OPENSTD_TARGETS = [
    # 首批：劳动防护用品与高处作业基础标准
    "GB 2811-2019",
    "GB 6095-2021",
    "GB/T 3608-2008",
    "GB/T 13869-2017",
    "GB 39800.1-2020",
    "GB 45943-2025",
    "GB 12523-2025",
    "GB/T 3787-2017",
    "GB/T 5972-2023",
    # 扩充：建筑一线新工人直接相关（PPE、爆破、应急、机械、起重、
    # 钢梯平台、电气安全）。逐条经 OpenStd 检索核对为现行/即将实施，
    # 已被替代或已废止的标准号不列入本清单。
    "GB 6722-2014",
    "GB/T 29639-2020",
    "GB 2890-2022",
    "GB 2626-2019",
    "GB/T 6096-2020",
    "GB 39800.2-2020",
    "GB 39800.3-2020",
    "GB/T 12903-2025",
    "GB/T 2893.1-2013",
    "GB/T 2893.2-2020",
    "GB/T 2893.5-2020",
    "GB/T 15706-2012",
    "GB/T 4208-2017",
    "GB/T 6067.1-2010",
    "GB/T 29086-2012",
    "GB 4053.1-2009",
    "GB 4053.2-2009",
    "GB 4053.3-2009",
    "GB/T 25295-2010",
    "GB/T 13861-2022",
    # 第三批：建筑施工现场安全方向补齐（施工机械与升降设备、起重吊装、
    # 电气安全、个体防护、防火防爆与气瓶、机械防护装置、安全标志与安全色）。
    # 逐条经 OpenStd 检索核对，均返回"现行"或"即将实施"的精确匹配；
    # 已废止/被替代的版本一律不列入（脚本也会二次校验 status）。
    # 检索核对无结果、故不列入的标准号：GB 13955（仅 GB 13955-1992 已废止）、
    # GB 50194、GB 50720、GB/T 5083、GB 5100（仅 1994 版已废止）、
    # GB/T 11651（仅 2008 版已废止）、GB/T 20303.1 之外的 50xxx/55xxx
    # 工程建设标准与 JGJ 行业标准均不在 OpenStd 收录范围。
    # 建筑施工机械与升降设备安全
    "GB/T 26557-2021",
    "GB/T 27547-2011",
    "GB 5144-2006",
    "GB/T 19154-2017",
    "GB/T 34023-2017",
    "GB 10055-2007",
    # 起重与吊装（GB/T 6067.1-2010、GB/T 5972-2023 已在上面批次）
    "GB/T 6067.5-2014",
    "GB/T 20303.1-2016",
    # 电气安全（GB/T 13869-2017、GB/T 3787-2017 已在上面批次）
    "GB/T 16895.1-2008",
    "GB/T 16895.6-2014",
    "GB/T 16895.21-2020",
    # 个体防护（GB 39800.1/.2/.3-2020 已在上面批次）
    # 防火防爆与气瓶
    "GB/T 2550-2025",
    "GB/T 11638-2020",
    "GB 4351-2023",
    # 机械与防护装置（GB/T 15706-2012 已在上面批次）
    "GB/T 8196-2018",
    # 安全标志与安全色
    "GB 2894-2025",
    "GB/T 2893.3-2010",
    "GB/T 2893.4-2013",
]


@dataclass(slots=True)
class SourceRecord:
    title: str
    file_name: str
    source_url: str
    sha256: str
    bytes: int
    normalized_file: str = ""
    normalization_note: str = ""


def request_bytes(url: str, *, referer: str = "") -> bytes:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/pdf,*/*",
    }
    if referer:
        headers["Referer"] = referer
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()


def safe_name(value: str) -> str:
    value = normalize_text(value)
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value)
    value = re.sub(r"\s+", " ", value).strip(" .")
    return value[:180] or "document"


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def fetch_jncc(output_dir: Path) -> list[SourceRecord]:
    page = request_bytes(JNCC_URL)
    document = html.fromstring(page)
    output_dir.mkdir(parents=True, exist_ok=True)

    records: list[SourceRecord] = []
    for anchor in document.xpath(
        '//a[contains(@href, "document/download")]'
    ):
        label = normalize_text(" ".join(anchor.itertext()))
        href = anchor.get("href")
        if not label or not href:
            continue
        source_url = urllib.parse.urljoin(JNCC_URL, href)
        suffix = Path(label).suffix or ".bin"
        file_name = safe_name(label)
        if not file_name.lower().endswith(suffix.lower()):
            file_name += suffix

        print(f"下载 JNCC：{file_name}")
        body = request_bytes(source_url, referer=JNCC_URL)
        target = output_dir / file_name
        target.write_bytes(body)
        records.append(
            SourceRecord(
                title=label,
                file_name=file_name,
                source_url=source_url,
                sha256=hashlib.sha256(body).hexdigest(),
                bytes=len(body),
            )
        )
    return records


def parse_openstd_row(row: Any) -> dict[str, str] | None:
    cells = row.xpath("./td")
    if len(cells) < 9:
        return None
    code = normalize_text(" ".join(cells[1].itertext()))
    title = normalize_text(" ".join(cells[4].itertext()))
    onclick = " ".join(cells[1].xpath(".//@onclick"))
    match = re.search(r"showInfo\(['\"]([A-F0-9]+)['\"]\)", onclick)
    if not code or not title or not match:
        return None
    return {
        "code": code,
        "title": title,
        "type": normalize_text(" ".join(cells[5].itertext())),
        "status": normalize_text(" ".join(cells[6].itertext())),
        "published": normalize_text(" ".join(cells[7].itertext())),
        "implemented": normalize_text(" ".join(cells[8].itertext())),
        "hcno": match.group(1),
    }


def openstd_query(target: str) -> list[dict[str, str]]:
    """检索 OpenStd 并返回全部可解析结果行。

    HTTP 400 视为站点侧硬拒绝，直接抛出不再重试；其余瞬时故障
    （连接重置、5xx、非预期页面）重试 RETRY_TIMES 次。
    """
    url = OPENSTD_SEARCH.format(query=urllib.parse.quote(target))
    last_error: Exception | None = None
    for attempt in range(RETRY_TIMES):
        try:
            page = request_bytes(
                url, referer="https://openstd.samr.gov.cn/bzgk/std/"
            )
            document = html.fromstring(page)
            return [
                parsed
                for row in document.xpath("//table//tr")
                if (parsed := parse_openstd_row(row))
            ]
        except urllib.error.HTTPError as exc:
            if exc.code == 400:
                raise
            last_error = exc
        except Exception as exc:  # noqa: BLE001 - 瞬时故障按次重试
            last_error = exc
        if attempt + 1 < RETRY_TIMES:
            time.sleep(RETRY_DELAY)
    raise RuntimeError(f"检索失败：{type(last_error).__name__}: {last_error}")


def fetch_openstd(output_dir: Path) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    seen: set[str] = set()
    for target in OPENSTD_TARGETS:
        print(f"检索 OpenStd：{target}")
        try:
            candidates = [
                parsed
                for parsed in openstd_query(target)
                if parsed["code"] == target
            ]
        except urllib.error.HTTPError as exc:
            if exc.code == 400:
                raise SystemExit(f"HTTP 400，立即停止：{target}")
            print(f"  跳过：HTTPError {exc.code}")
            continue
        except Exception as exc:
            print(f"  跳过：{type(exc).__name__}: {exc}")
            continue

        if not candidates:
            print("  未找到精确匹配")
            continue
        selected = candidates[0]
        if selected["status"] not in {"现行", "即将实施"}:
            print(f"  跳过非现行标准：{selected['status']}")
            continue
        selected.update(
            {
                "source": "国家标准全文公开系统",
                "source_url": OPENSTD_DETAIL.format(hcno=selected["hcno"]),
                "preview_url": OPENSTD_PREVIEW.format(hcno=selected["hcno"]),
                "full_text_access": "official_online_preview; download requires CAPTCHA",
                "content_imported": "metadata_only",
            }
        )
        if selected["code"] in seen:
            print("  重复目标，已跳过")
            continue
        seen.add(selected["code"])
        records.append(selected)
        time.sleep(REQUEST_INTERVAL)
    write_json(output_dir / "manifest.json", records)
    return records


def pdf_text(path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    pages = []
    for index, page in enumerate(reader.pages, start=1):
        text = normalize_text(page.extract_text() or "")
        if text:
            pages.append(f"## 第 {index} 页\n\n{text}")
    return "\n\n".join(pages)


def docx_text(path: Path) -> str:
    from docx import Document

    document = Document(str(path))
    parts = [
        normalize_text(paragraph.text)
        for paragraph in document.paragraphs
        if normalize_text(paragraph.text)
    ]
    for table_index, table in enumerate(document.tables, start=1):
        parts.append(f"## 表格 {table_index}")
        for row in table.rows:
            cells = [normalize_text(cell.text) for cell in row.cells]
            if any(cells):
                parts.append(" | ".join(cells))
    return "\n\n".join(parts)


def zip_text(path: Path) -> str:
    parts: list[str] = []
    with zipfile.ZipFile(path) as archive:
        for name in archive.namelist():
            suffix = Path(name).suffix.lower()
            if suffix not in {".txt", ".md", ".markdown"}:
                continue
            text = archive.read(name).decode("utf-8-sig", "replace")
            parts.append(f"# {Path(name).stem}\n\n{normalize_text(text)}")
    return "\n\n".join(parts)


def doc_text(path: Path) -> str:
    """Best-effort text extraction for a legacy Word file."""
    body = path.read_bytes()
    if body.startswith(b"{\\rtf"):
        decoded = body.decode("latin-1", "ignore")
        decoded = re.sub(r"\\'[0-9a-fA-F]{2}", " ", decoded)
        decoded = re.sub(r"\\[a-zA-Z]+-?\d* ?", " ", decoded)
        decoded = decoded.replace("{", " ").replace("}", " ")
        return normalize_text(decoded)

    fragments: list[str] = []
    for match in re.finditer(rb"(?:[\x20-\x7e]\x00){12,}", body):
        fragments.append(match.group(0).decode("utf-16le", "ignore"))
    for match in re.finditer(rb"(?:[\x81-\xfe][\x40-\xfe]){8,}", body):
        fragments.append(match.group(0).decode("gb18030", "ignore"))
    return normalize_text("\n".join(fragments))


def extract_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return pdf_text(path)
    if suffix == ".docx":
        return docx_text(path)
    if suffix == ".zip":
        return zip_text(path)
    if suffix == ".doc":
        return doc_text(path)
    if suffix in {".txt", ".md", ".markdown"}:
        return normalize_text(path.read_text(encoding="utf-8-sig", errors="replace"))
    raise ValueError(f"unsupported source: {suffix}")


def normalize_jncc(
    source_dir: Path,
    output_dir: Path,
    records: list[SourceRecord],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for stale in output_dir.glob("*.md"):
        stale.unlink()
    for index, record in enumerate(records, start=1):
        source_path = source_dir / record.file_name
        try:
            body = extract_text(source_path)
        except Exception as exc:
            record.normalization_note = f"{type(exc).__name__}: {exc}"
            body = ""

        if len(re.sub(r"\s+", "", body)) < 40:
            record.normalization_note = (
                record.normalization_note
                or "未提取到足够正文，可能是扫描件或旧版 DOC 格式。"
            )

        clean_title = re.sub(
            r"^\d+\s*", "", Path(record.file_name).stem
        ).strip()
        normalized_name = f"{index:02d}_{safe_name(clean_title)}.md"
        normalized_path = output_dir / normalized_name
        header = (
            f"# {clean_title}\n\n"
            f"> 公开来源：{record.source_url}\n"
            f"> 原始文件：{record.file_name}\n"
            f"> 说明：正文由官方公开附件自动提取，正式使用时应核对标准出版物。\n\n"
        )
        normalized_path.write_text(header + body, encoding="utf-8")
        record.normalized_file = normalized_name
    write_json(source_dir / "manifest.json", [asdict(item) for item in records])


def normalize_openstd(
    output_dir: Path, records: list[dict[str, str]]
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for stale in output_dir.glob("*.md"):
        stale.unlink()
    for index, record in enumerate(records, start=1):
        normalized_name = f"{index:02d}_{safe_name(record['code'])}.md"
        normalized_path = output_dir / normalized_name
        normalized_path.write_text(
            (
                f"# {record['code']} {record['title']}\n\n"
                f"> 标准状态：{record['status']}\n"
                f"> 发布日期：{record['published']}\n"
                f"> 实施日期：{record['implemented']}\n"
                f"> 官方详情：{record['source_url']}\n"
                f"> 在线预览：{record['preview_url']}\n\n"
                "## 全文导入说明\n\n"
                "国家标准全文公开系统的下载入口需要验证码，本程序未绕过验证码。"
                "当前仅导入标准编号、名称、状态和官方入口，不把未授权正文写入知识库。"
                "如需让 AI 引用具体条款，请由项目取得合法文本后放入 knowledge 目录。\n"
            ),
            encoding="utf-8",
        )
    write_json(output_dir / "manifest.json", records)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="下载公开建筑安全标准并生成可入库的本地 Markdown"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "data" / "sources",
    )
    parser.add_argument(
        "--skip-jncc",
        action="store_true",
        help="跳过济南住建公开附件",
    )
    parser.add_argument(
        "--skip-openstd",
        action="store_true",
        help="跳过国家标准全文公开系统元数据",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = args.output.resolve()
    normalized_dir = output_dir / "normalized"
    started = datetime.now(timezone.utc).isoformat()

    if not args.skip_jncc:
        records = fetch_jncc(output_dir / "jncc")
        normalize_jncc(
            output_dir / "jncc",
            normalized_dir / "jncc",
            records,
        )

    if not args.skip_openstd:
        records = fetch_openstd(output_dir / "openstd")
        normalize_openstd(normalized_dir / "openstd", records)

    write_json(
        output_dir / "acquisition.json",
        {
            "started_at": started,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "jncc_url": JNCC_URL,
            "openstd_url": "https://openstd.samr.gov.cn/bzgk/gb/",
            "policy": (
                "Only publicly downloadable attachments are stored. "
                "CAPTCHA-protected OpenStd downloads are not bypassed."
            ),
        },
    )
    print(f"标准来源已写入：{output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
