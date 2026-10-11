from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sitesaha.db import KnowledgeBase
from sitesaha.text import ChunkDraft


class KnowledgeBaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db = KnowledgeBase(Path(self.temp_dir.name) / "test.db")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_add_search_and_replace_document(self) -> None:
        self.db.add_document(
            title="高处作业制度",
            source="high-work.md",
            category="高处作业",
            chunks=[
                ChunkDraft(
                    heading="安全带",
                    content="高处作业人员必须正确使用安全带，优先高挂低用。",
                )
            ],
        )
        results = self.db.search("安全带怎么使用", top_k=3)
        self.assertTrue(results)
        self.assertEqual(results[0].title, "高处作业制度")

        self.db.add_document(
            title="高处作业制度",
            source="high-work.md",
            chunks=[ChunkDraft(heading="新版", content="临边防护应完整可靠。")],
        )
        self.assertEqual(self.db.stats(), {"documents": 1, "chunks": 1})
        self.assertFalse(self.db.search("安全带怎么使用"))
        self.assertTrue(self.db.search("临边防护"))

    def test_missing_query_returns_empty_list(self) -> None:
        self.assertEqual(self.db.search("的了吗"), [])


if __name__ == "__main__":
    unittest.main()
