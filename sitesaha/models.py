from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class SearchResult:
    chunk_id: int
    document_id: int
    title: str
    source: str
    version: str
    category: str
    heading: str
    content: str
    score: float


@dataclass(slots=True)
class Answer:
    text: str
    sources: list[SearchResult] = field(default_factory=list)
    mode: str = "extractive"
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class DocumentInfo:
    id: int
    title: str
    source: str
    version: str
    category: str
    chunk_count: int
