from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from hashlib import blake2b
from math import sqrt
from pathlib import Path
from typing import Iterator, Sequence

from .models import DocumentInfo, SearchResult
from .text import (
    ChunkDraft,
    fts_query,
    normalize_text,
    overlap_units,
    searchable_text,
    truncate,
)


@dataclass(frozen=True, slots=True)
class _VectorDocument:
    result: SearchResult
    vector: dict[int, float]


VECTOR_DIMENSIONS = 1024


def _sparse_vector(value: str) -> dict[int, float]:
    counts: dict[int, float] = {}
    for token in searchable_text(value).split():
        digest = blake2b(token.encode("utf-8"), digest_size=4).digest()
        index = int.from_bytes(digest, "little") % VECTOR_DIMENSIONS
        counts[index] = counts.get(index, 0.0) + 1.0
    norm = sqrt(sum(weight * weight for weight in counts.values()))
    if not norm:
        return {}
    return {index: weight / norm for index, weight in counts.items()}


def _cosine(
    left: dict[int, float], right: dict[int, float]
) -> float:
    if len(left) > len(right):
        left, right = right, left
    return sum(weight * right.get(index, 0.0) for index, weight in left.items())


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    source TEXT NOT NULL UNIQUE,
    version TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    ordinal INTEGER NOT NULL,
    heading TEXT NOT NULL DEFAULT '',
    content TEXT NOT NULL,
    search_text TEXT NOT NULL,
    UNIQUE(document_id, ordinal)
);

CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON chunks(document_id);

CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    heading,
    content,
    search_text,
    content='chunks',
    content_rowid='id',
    tokenize='unicode61 remove_diacritics 2'
);

CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
    INSERT INTO chunks_fts(rowid, heading, content, search_text)
    VALUES (new.id, new.heading, new.content, new.search_text);
END;

CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
    INSERT INTO chunks_fts(chunks_fts, rowid, heading, content, search_text)
    VALUES ('delete', old.id, old.heading, old.content, old.search_text);
END;

CREATE TRIGGER IF NOT EXISTS chunks_au AFTER UPDATE ON chunks BEGIN
    INSERT INTO chunks_fts(chunks_fts, rowid, heading, content, search_text)
    VALUES ('delete', old.id, old.heading, old.content, old.search_text);
    INSERT INTO chunks_fts(rowid, heading, content, search_text)
    VALUES (new.id, new.heading, new.content, new.search_text);
END;
"""


class KnowledgeBase:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self._vector_cache: tuple[
            tuple[int, int], list[_VectorDocument]
        ] | None = None

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.db_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = NORMAL")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(SCHEMA)

    def clear_cache(self) -> None:
        self._vector_cache = None

    def add_document(
        self,
        *,
        title: str,
        source: str,
        chunks: Sequence[ChunkDraft],
        version: str = "",
        category: str = "",
        replace: bool = True,
    ) -> tuple[int, int]:
        clean_title = normalize_text(title) or source
        clean_source = normalize_text(source)
        clean_chunks = [
            ChunkDraft(
                heading=normalize_text(chunk.heading),
                content=normalize_text(chunk.content),
            )
            for chunk in chunks
            if normalize_text(chunk.content)
        ]
        if not clean_source:
            raise ValueError("source cannot be empty")
        if not clean_chunks:
            raise ValueError("document has no text chunks")

        self.initialize()
        with self.connect() as connection:
            existing = connection.execute(
                "SELECT id FROM documents WHERE source = ?", (clean_source,)
            ).fetchone()

            if existing and not replace:
                count = connection.execute(
                    "SELECT COUNT(*) FROM chunks WHERE document_id = ?",
                    (existing["id"],),
                ).fetchone()[0]
                return int(existing["id"]), int(count)

            if existing:
                document_id = int(existing["id"])
                connection.execute(
                    """
                    UPDATE documents
                    SET title = ?, version = ?, category = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (clean_title, version, category, document_id),
                )
                connection.execute(
                    "DELETE FROM chunks WHERE document_id = ?", (document_id,)
                )
            else:
                cursor = connection.execute(
                    """
                    INSERT INTO documents(title, source, version, category)
                    VALUES (?, ?, ?, ?)
                    """,
                    (clean_title, clean_source, version, category),
                )
                document_id = int(cursor.lastrowid)

            rows = [
                (
                    document_id,
                    ordinal,
                    chunk.heading,
                    chunk.content,
                    searchable_text(f"{chunk.heading} {chunk.content}"),
                )
                for ordinal, chunk in enumerate(clean_chunks)
            ]
            connection.executemany(
                """
                INSERT INTO chunks(document_id, ordinal, heading, content, search_text)
                VALUES (?, ?, ?, ?, ?)
                """,
                rows,
            )

        self.clear_cache()
        return document_id, len(clean_chunks)

    def search(self, question: str, *, top_k: int = 5) -> list[SearchResult]:
        expression = fts_query(question)
        if not expression:
            return []

        self.initialize()
        fetch_limit = max(top_k * 5, 20)
        units = overlap_units(question)

        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    c.id AS chunk_id,
                    c.document_id,
                    d.title,
                    d.source,
                    d.version,
                    d.category,
                    c.heading,
                    c.content,
                    bm25(chunks_fts, 8.0, 2.0, 5.0) AS rank
                FROM chunks_fts
                JOIN chunks c ON c.id = chunks_fts.rowid
                JOIN documents d ON d.id = c.document_id
                WHERE chunks_fts MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (expression, fetch_limit),
            ).fetchall()

        results: list[SearchResult] = []
        for row in rows:
            candidate_units = overlap_units(
                f"{row['heading']} {row['content']}"
            )
            overlap = (
                len(units.intersection(candidate_units)) / len(units) if units else 0.0
            )
            heading_overlap = overlap_units(row["heading"])
            heading_score = (
                len(units.intersection(heading_overlap)) / len(units) if units else 0.0
            )
            bm25_score = 1.0 / (1.0 + max(0.0, float(row["rank"])))
            score = bm25_score + overlap * 3.0 + heading_score * 1.5

            results.append(
                SearchResult(
                    chunk_id=int(row["chunk_id"]),
                    document_id=int(row["document_id"]),
                    title=row["title"],
                    source=row["source"],
                    version=row["version"],
                    category=row["category"],
                    heading=row["heading"],
                    content=truncate(row["content"], 1800),
                    score=round(score, 6),
                )
            )

        results.sort(key=lambda item: item.score, reverse=True)
        return results[:top_k]

    def vector_search(self, question: str, *, top_k: int = 25) -> list[SearchResult]:
        query_vector = _sparse_vector(question)
        if not query_vector:
            return []

        documents = self._load_vector_documents()
        if not documents:
            return []

        scored = [
            (document, _cosine(query_vector, document.vector))
            for document in documents
        ]
        scored = [
            (document, score)
            for document, score in scored
            if score > 0.01
        ]
        scored.sort(key=lambda item: item[1], reverse=True)

        results: list[SearchResult] = []
        for document, score in scored[:top_k]:
            result = document.result
            results.append(
                SearchResult(
                    chunk_id=result.chunk_id,
                    document_id=result.document_id,
                    title=result.title,
                    source=result.source,
                    version=result.version,
                    category=result.category,
                    heading=result.heading,
                    content=result.content,
                    score=round(score, 6),
                )
            )
        return results

    def _load_vector_documents(self) -> list[_VectorDocument]:
        if not self.db_path.exists():
            return []
        signature = (self.db_path.stat().st_mtime_ns, self.db_path.stat().st_size)
        if self._vector_cache and self._vector_cache[0] == signature:
            return self._vector_cache[1]

        self.initialize()
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    c.id AS chunk_id,
                    c.document_id,
                    d.title,
                    d.source,
                    d.version,
                    d.category,
                    c.heading,
                    c.content
                FROM chunks c
                JOIN documents d ON d.id = c.document_id
                ORDER BY c.id
                """
            ).fetchall()

        documents: list[_VectorDocument] = []
        for row in rows:
            result = SearchResult(
                chunk_id=int(row["chunk_id"]),
                document_id=int(row["document_id"]),
                title=row["title"],
                source=row["source"],
                version=row["version"],
                category=row["category"],
                heading=row["heading"],
                content=truncate(row["content"], 1800),
                score=0.0,
            )
            vector = _sparse_vector(
                f"{row['title']} {row['heading']} {row['content']}"
            )
            documents.append(_VectorDocument(result=result, vector=vector))

        self._vector_cache = (signature, documents)
        return documents

    def stats(self) -> dict[str, int]:
        self.initialize()
        with self.connect() as connection:
            documents = int(
                connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
            )
            chunks = int(connection.execute("SELECT COUNT(*) FROM chunks").fetchone()[0])
        return {"documents": documents, "chunks": chunks}

    def list_documents(self) -> list[DocumentInfo]:
        self.initialize()
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT d.id, d.title, d.source, d.version, d.category, COUNT(c.id) AS chunk_count
                FROM documents d
                LEFT JOIN chunks c ON c.document_id = d.id
                GROUP BY d.id
                ORDER BY d.updated_at DESC, d.title
                """
            ).fetchall()
        return [
            DocumentInfo(
                id=int(row["id"]),
                title=row["title"],
                source=row["source"],
                version=row["version"],
                category=row["category"],
                chunk_count=int(row["chunk_count"]),
            )
            for row in rows
        ]
