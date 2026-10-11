"""sitesaha/structure.py 的单元测试（第 16 轮 §3.3）。

重点覆盖实测踩到的两种章节写法：
  · 标题独占一行（"**可见风险**："）
  · 标题 + 冒号 + 同行内容（"**看不清的**：画面左侧…"）
后者早先会把内容误当成上一条风险，所以专门加断言。
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sitesaha.structure import parse_answer, parse_inspection, strip_markdown  # noqa: E402

FULL = """- **作业类型**：深基坑开挖
- **可见风险**：
  - 画面中部：基坑边缘没有明显的防护措施，立即动作：停止作业，撤离至安全区域。
  - 画面右侧：钢筋裸露在外，立即动作：设置防护并报告现场负责人。
- **看不清的**：画面左侧是否有安全通道，需要现场确认。
- **依据**：
  - [1] 建筑施工安全检查标准 JGJ59-2011 / 第 23 页
本页仅辅助识别肉眼可见的风险，不替代现场安全员检查。"""


class ParseInspectionTests(unittest.TestCase):
    def test_extracts_all_four_sections(self) -> None:
        result = parse_inspection(FULL)
        self.assertEqual(result["work_type"], "深基坑开挖")
        self.assertEqual(len(result["risks"]), 2)
        self.assertEqual(len(result["uncertain"]), 1)
        self.assertEqual(len(result["citations"]), 1)

    def test_risk_split_into_where_what_action(self) -> None:
        risk = parse_inspection(FULL)["risks"][0]
        self.assertEqual(risk["where"], "画面中部")
        self.assertIn("基坑边缘", risk["what"])
        self.assertIn("撤离", risk["action"])
        # 动作不应残留在 what 里
        self.assertNotIn("立即动作", risk["what"])

    def test_inline_section_content_not_treated_as_risk(self) -> None:
        """实测踩过的坑：'**看不清的**：内容' 曾被算成上一条风险。"""
        result = parse_inspection(FULL)
        for risk in result["risks"]:
            self.assertNotIn("看不清", risk["what"])
            self.assertNotIn("看不清", risk["where"])
        self.assertIn("安全通道", result["uncertain"][0])

    def test_disclaimer_not_in_structure(self) -> None:
        result = parse_inspection(FULL)
        blob = str(result)
        self.assertNotIn("本页仅辅助识别", blob)

    def test_blank_or_unclear_returns_empty(self) -> None:
        for text in ("", "   ", "这张照片看不清，请重拍。"):
            result = parse_inspection(text)
            self.assertEqual(result["risks"], [])
            self.assertEqual(result["work_type"], "")

    def test_citation_without_index_still_captured(self) -> None:
        text = "- **依据**：\n  - 项目安全管理制度 第 3 条\n"
        result = parse_inspection(text)
        self.assertEqual(len(result["citations"]), 1)
        self.assertIsNone(result["citations"][0]["index"])


class StripMarkdownTests(unittest.TestCase):
    def test_bold_removed(self) -> None:
        self.assertNotIn("**", strip_markdown("这是 **重点** 内容"))

    def test_bullet_converted(self) -> None:
        out = strip_markdown("- 第一条\n- 第二条")
        self.assertIn("· 第一条", out)
        self.assertIn("· 第二条", out)


class ParseAnswerTests(unittest.TestCase):
    def test_numbered_citations(self) -> None:
        text = "按规范要求作业。\n[1] 建筑施工安全检查标准 JGJ59-2011\n[2] 项目安全交底"
        result = parse_answer(text)
        self.assertEqual(len(result["citations"]), 2)
        self.assertEqual(result["citations"][0]["index"], 1)

    def test_no_citations(self) -> None:
        self.assertEqual(parse_answer("普通回答，没有引用。")["citations"], [])


if __name__ == "__main__":
    unittest.main()
