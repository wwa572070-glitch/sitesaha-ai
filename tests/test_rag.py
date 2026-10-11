from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sitesaha.config import AppConfig
from sitesaha.db import KnowledgeBase
from sitesaha.rag import RAGEngine, classify_question, risk_level
from sitesaha.text import ChunkDraft


class RAGEngineTests(unittest.TestCase):
    def test_extractive_fallback_cites_sources(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            kb = KnowledgeBase(root / "kb.db")
            kb.add_document(
                title="现场用电",
                source="electric.md",
                chunks=[
                    ChunkDraft(
                        heading="配电箱进水",
                        content=(
                            "发现配电箱进水时，应立即停止使用并保持距离，"
                            "通知持证电工处理，不得自行带电操作。"
                        ),
                    )
                ],
            )
            config = AppConfig(
                project_root=root,
                db_path=root / "kb.db",
                knowledge_dir=root / "knowledge",
                llm_mode="off",
            )
            answer = RAGEngine(kb, config).answer("发现配电箱进水怎么办")
            self.assertEqual(answer.mode, "extractive")
            self.assertTrue(answer.sources)
            self.assertIn("[1]", answer.text)
            self.assertIn("停止使用", answer.text)

    def test_lifting_answer_starts_with_direct_stop_action(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            kb = KnowledgeBase(root / "kb.db")
            kb.add_document(
                title="吊装安全",
                source="lifting.md",
                chunks=[
                    ChunkDraft(heading="吊装区域", content="吊装区域应设置警戒，人员不得在吊物下方停留或通行。")
                ],
            )
            config = AppConfig(
                project_root=root,
                db_path=root / "kb.db",
                knowledge_dir=root / "knowledge",
                llm_mode="off",
            )
            answer = RAGEngine(kb, config).answer("为什么不能站在吊物下面？")
            self.assertEqual(answer.mode, "extractive")
            self.assertIn("风险等级：橙色", answer.warnings)
            self.assertIn("不要站在吊物下方", answer.text)

    def test_no_match_does_not_hallucinate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            kb = KnowledgeBase(root / "kb.db")
            config = AppConfig(
                project_root=root,
                db_path=root / "kb.db",
                knowledge_dir=root / "knowledge",
                llm_mode="off",
            )
            answer = RAGEngine(kb, config).answer("火星基地怎么搭")
            self.assertEqual(answer.mode, "no_match")
            self.assertIn("没有检索到足够依据", answer.text)

    def test_high_risk_keywords_cover_lifting_danger_zone(self) -> None:
        question = "为什么不能站在吊物下面？"
        intent = classify_question(question)
        self.assertEqual(intent, "高风险作业")
        self.assertEqual(risk_level(question, intent), "橙色")

    def test_high_risk_keywords_cover_common_site_hazards(self) -> None:
        for question in (
            "临边没有防护怎么办",
            "脚手架晃动还能继续上吗",
            "基坑旁边可以随便走吗",
            "临电箱漏电怎么办",
            "动火作业附近能不能有人",
        ):
            intent = classify_question(question)
            self.assertEqual(intent, "高风险作业", question)
            self.assertEqual(risk_level(question, intent), "橙色", question)


if __name__ == "__main__":
    unittest.main()
