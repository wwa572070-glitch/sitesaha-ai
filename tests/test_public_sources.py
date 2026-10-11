from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from sitesaha.db import KnowledgeBase
from sitesaha.hybrid import HybridRetriever
from sitesaha.ingest import ingest_file


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class PublicSourceTests(unittest.TestCase):
    @staticmethod
    def _jgj59_path() -> Path:
        directory = (
            PROJECT_ROOT / "data" / "sources" / "normalized" / "jncc"
        )
        matches = list(directory.glob("*jgj59*2011*.md"))
        if len(matches) != 1:
            raise AssertionError(f"JGJ59-2011 标准化文件数量异常：{len(matches)}")
        return matches[0]

    def test_jncc_manifest_contains_primary_standard(self) -> None:
        manifest_path = PROJECT_ROOT / "data" / "sources" / "jncc" / "manifest.json"
        records = json.loads(manifest_path.read_text(encoding="utf-8"))
        titles = " ".join(record["title"] for record in records)
        self.assertIn("JGJ59-2011", titles)

    def test_normalized_jgj59_contains_inspection_content(self) -> None:
        path = self._jgj59_path()
        text = path.read_text(encoding="utf-8")
        self.assertIn("高处作业检查评定项目", text)
        self.assertIn("安全带", text)

    def test_openstd_manifest_excludes_withdrawn_standards(self) -> None:
        manifest_path = (
            PROJECT_ROOT / "data" / "sources" / "openstd" / "manifest.json"
        )
        records = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertTrue(records)
        self.assertTrue(all(record["status"] in {"现行", "即将实施"} for record in records))

    def test_public_standard_is_retrieved_for_worker_question(self) -> None:
        path = self._jgj59_path()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            kb = KnowledgeBase(root / "kb.db")
            ingest_file(kb, path, category="公开标准")
            results = HybridRetriever(kb).search("高处作业要检查哪些项目", top_k=3)
            self.assertTrue(results)
            self.assertIn("JGJ59-2011", results[0].title)


if __name__ == "__main__":
    unittest.main()
