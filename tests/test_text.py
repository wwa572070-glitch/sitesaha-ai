from __future__ import annotations

import unittest

from sitesaha.text import (
    chunk_markdown,
    fts_query,
    normalize_text,
    searchable_text,
)


class TextProcessingTests(unittest.TestCase):
    def test_chinese_text_is_converted_to_search_terms(self) -> None:
        terms = searchable_text("高处作业必须系安全带")
        self.assertIn("高处", terms)
        self.assertIn("安全带", terms)

    def test_fts_query_contains_chinese_bigrams(self) -> None:
        expression = fts_query("基坑渗水怎么办")
        self.assertIn('"基坑"', expression)
        self.assertIn('"渗水"', expression)

    def test_markdown_headings_are_preserved(self) -> None:
        chunks = chunk_markdown(
            "# 标准\n\n## 高处作业\n\n确认临边防护。\n\n### 安全带\n\n高挂低用。"
        )
        headings = [chunk.heading for chunk in chunks]
        self.assertIn("标准 / 高处作业", headings)
        self.assertIn("标准 / 高处作业 / 安全带", headings)

    def test_normalize_preserves_chinese_punctuation(self) -> None:
        self.assertEqual(normalize_text("先停机，再检修。"), "先停机，再检修。")


if __name__ == "__main__":
    unittest.main()
