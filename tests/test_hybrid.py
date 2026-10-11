from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sitesaha.db import KnowledgeBase
from sitesaha.hybrid import (
    HybridRetriever,
    cap_per_source,
    expand_query,
    reciprocal_rank_fusion,
)
from sitesaha.models import SearchResult
from sitesaha.text import ChunkDraft


def result(chunk_id: int, source: str) -> SearchResult:
    return SearchResult(
        chunk_id=chunk_id,
        document_id=chunk_id,
        title=source,
        source=source,
        version="",
        category="",
        heading="",
        content="",
        score=0.0,
    )


class HybridRetrievalTests(unittest.TestCase):
    def test_reciprocal_rank_fusion_rewards_shared_hits(self) -> None:
        fused = reciprocal_rank_fusion([[1, 2, 3], [2, 3, 1]])
        self.assertEqual(fused[0][0], 2)

    def test_per_source_cap_limits_monopoly(self) -> None:
        candidates = [
            result(1, "a"),
            result(2, "a"),
            result(3, "a"),
            result(4, "b"),
        ]
        selected = cap_per_source(candidates, top_k=3, max_per_source=2)
        self.assertEqual([item.chunk_id for item in selected], [1, 2, 4])

    def test_new_worker_query_expands_to_training_terms(self) -> None:
        expansion = expand_query("我第一次上工地")
        self.assertIn("入场安全教育", expansion)
        self.assertIn("安全帽", expansion)

    def test_hybrid_retriever_returns_standard_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            kb = KnowledgeBase(root / "kb.db")
            kb.add_document(
                title="建筑施工安全检查标准 JGJ59-2011",
                source="JGJ59.md",
                chunks=[
                    ChunkDraft(
                        heading="高处作业",
                        content=(
                            "进入施工现场的人员必须正确佩戴安全帽。"
                            "高处作业人员应按规定系挂安全带。"
                        ),
                    )
                ],
            )
            results = HybridRetriever(kb).search(
                "新工人第一次上工地要戴什么", top_k=3
            )
            self.assertTrue(results)
            self.assertIn("JGJ59", results[0].title)


if __name__ == "__main__":
    unittest.main()
