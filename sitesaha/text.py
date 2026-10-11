from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


CJK_RANGE = "\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff"
SEGMENT_RE = re.compile(rf"([{CJK_RANGE}]+|[a-zA-Z0-9][a-zA-Z0-9._/-]*)")
SPACE_RE = re.compile(r"[ \t\f\v]+")
BLANK_LINES_RE = re.compile(r"\n{3,}")

SEARCH_STOPWORDS = {
    "的",
    "了",
    "是",
    "在",
    "和",
    "与",
    "或",
    "及",
    "吗",
    "呢",
    "请",
    "怎么",
    "如何",
    "什么",
    "哪些",
    "需要",
    "可以",
    "是否",
    "发现",
    "立即",
    "作业",
    "施工",
    "现场",
    "安全",
    "检查",
    "处理",
    "进行",
    "必须",
    "应该",
}


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFC", value or "")
    value = value.replace("\r\n", "\n").replace("\r", "\n").replace("\u3000", " ")
    value = SPACE_RE.sub(" ", value)
    value = BLANK_LINES_RE.sub("\n\n", value)
    return value.strip()


def _cjk_terms(block: str, *, document: bool) -> list[str]:
    terms: list[str] = []
    length = len(block)

    if length <= 12:
        terms.append(block)
    if length <= 4:
        terms.extend(block)

    terms.extend(block[index : index + 2] for index in range(max(0, length - 1)))
    if document and length >= 3:
        terms.extend(block[index : index + 3] for index in range(max(0, length - 2)))
    return terms


def _segments(value: str) -> list[str]:
    normalized = normalize_text(value).lower()
    return [match.group(1) for match in SEGMENT_RE.finditer(normalized)]


def searchable_text(value: str) -> str:
    terms: list[str] = []
    for segment in _segments(value):
        if re.fullmatch(rf"[{CJK_RANGE}]+", segment):
            terms.extend(_cjk_terms(segment, document=True))
        else:
            terms.append(segment)

    unique = list(dict.fromkeys(term for term in terms if term))
    return " ".join(unique)


def query_terms(value: str) -> list[str]:
    terms: list[str] = []
    for segment in _segments(value):
        if re.fullmatch(rf"[{CJK_RANGE}]+", segment):
            terms.extend(_cjk_terms(segment, document=False))
        else:
            terms.append(segment)

    cleaned = [
        term
        for term in terms
        if term
        and term not in SEARCH_STOPWORDS
        and (len(term) > 1 or re.fullmatch(rf"[{CJK_RANGE}]", term))
    ]
    return list(dict.fromkeys(cleaned))


def fts_query(value: str) -> str:
    terms = query_terms(value)
    if not terms:
        return ""
    escaped = [f'"{term.replace(chr(34), chr(34) * 2)}"' for term in terms]
    return " OR ".join(escaped)


def overlap_units(value: str) -> set[str]:
    units: set[str] = set()
    for segment in _segments(value):
        if re.fullmatch(rf"[{CJK_RANGE}]+", segment):
            if len(segment) <= 4:
                units.update(segment)
            units.update(
                segment[index : index + 2]
                for index in range(max(0, len(segment) - 1))
            )
        else:
            units.add(segment)
    return {unit for unit in units if unit and unit not in SEARCH_STOPWORDS}


def strip_markdown(value: str) -> str:
    value = re.sub(r"```.*?```", " ", value, flags=re.DOTALL)
    value = re.sub(r"`([^`]+)`", r"\1", value)
    value = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", value)
    value = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", value)
    value = re.sub(r"^\s{0,3}#{1,6}\s*", "", value, flags=re.MULTILINE)
    value = re.sub(r"^\s*[-*+]\s+", "", value, flags=re.MULTILINE)
    value = re.sub(r"^\s*\d+[.)、]\s+", "", value, flags=re.MULTILINE)
    value = value.replace("**", "").replace("__", "").replace("|", " ")
    value = re.sub(r"\n+", "\n", value)
    return value.strip()


def split_sentences(value: str) -> list[str]:
    text = strip_markdown(value)
    parts = re.split(r"(?<=[。！？!?；;])\s*", text)
    return [part.strip(" -\t") for part in parts if part.strip(" -\t")]


def truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: max(1, limit - 1)].rstrip() + "…"


@dataclass(frozen=True, slots=True)
class ChunkDraft:
    heading: str
    content: str


def _split_long_block(block: str, max_chars: int, overlap_chars: int) -> list[str]:
    if len(block) <= max_chars:
        return [block]

    sentences = split_sentences(block)
    if not sentences:
        sentences = [block]

    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        if len(sentence) > max_chars:
            if current:
                chunks.append(current.strip())
                current = ""
            start = 0
            while start < len(sentence):
                chunks.append(sentence[start : start + max_chars].strip())
                start += max_chars - overlap_chars
            continue

        candidate = f"{current}\n{sentence}".strip()
        if current and len(candidate) > max_chars:
            chunks.append(current.strip())
            overlap = current[-overlap_chars:].strip()
            current = f"{overlap}\n{sentence}".strip()
        else:
            current = candidate

    if current:
        chunks.append(current.strip())
    return [chunk for chunk in chunks if chunk]


def chunk_markdown(
    value: str, *, max_chars: int = 900, overlap_chars: int = 100
) -> list[ChunkDraft]:
    text = normalize_text(value)
    if not text:
        return []

    chunks: list[ChunkDraft] = []
    heading_stack: list[tuple[int, str]] = []
    buffer: list[str] = []
    buffer_heading = ""

    def flush() -> None:
        nonlocal buffer, buffer_heading
        block = "\n".join(buffer).strip()
        if not block:
            buffer = []
            return
        for part in _split_long_block(block, max_chars, overlap_chars):
            chunks.append(ChunkDraft(heading=buffer_heading, content=part))
        buffer = []

    for line in text.splitlines():
        heading_match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if heading_match:
            flush()
            level = len(heading_match.group(1))
            title = strip_markdown(heading_match.group(2)).strip()
            heading_stack = [
                (item_level, item_title)
                for item_level, item_title in heading_stack
                if item_level < level
            ]
            heading_stack.append((level, title))
            buffer_heading = " / ".join(item_title for _, item_title in heading_stack)
            continue

        if line.strip():
            buffer.append(line.rstrip())
        elif buffer:
            flush()

    flush()
    return chunks


def chunk_plain_text(
    value: str, *, max_chars: int = 900, overlap_chars: int = 100
) -> list[ChunkDraft]:
    text = normalize_text(value)
    if not text:
        return []
    parts: list[str] = []
    for block in re.split(r"\n\s*\n", text):
        parts.extend(_split_long_block(block, max_chars, overlap_chars))
    return [ChunkDraft(heading="", content=part) for part in parts if part.strip()]
