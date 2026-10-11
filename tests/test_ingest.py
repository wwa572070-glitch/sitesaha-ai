from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sitesaha.db import KnowledgeBase
from sitesaha.ingest import ingest_directory, ingest_file


class IngestionTests(unittest.TestCase):
    def test_ingest_markdown_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "rule.md"
            source.write_text(
                "# 临时用电\n\n## 配电箱\n\n配电箱应有防雨措施，不得进水。",
                encoding="utf-8",
            )
            kb = KnowledgeBase(root / "kb.db")
            _, chunk_count = ingest_file(kb, source, source_root=root)
            self.assertGreater(chunk_count, 0)
            self.assertTrue(kb.search("配电箱进水"))

    def test_ingest_directory_indexes_supported_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            knowledge = root / "knowledge"
            knowledge.mkdir()
            (knowledge / "a.md").write_text("# 基坑\n\n出现裂缝先撤离。", encoding="utf-8")
            (knowledge / "b.txt").write_text("吊装区域禁止站人。", encoding="utf-8")
            (knowledge / "ignored.json").write_text("{}", encoding="utf-8")

            kb = KnowledgeBase(root / "kb.db")
            results = ingest_directory(kb, knowledge)
            self.assertEqual(len(results), 2)
            self.assertEqual(kb.stats()["documents"], 2)


if __name__ == "__main__":
    unittest.main()
