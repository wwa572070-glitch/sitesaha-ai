"""sitesaha/checklists.py 的条件化生成与导入解析测试（第 16 轮 §11）。

覆盖 §11.D 的验收标准：
  · 不选条件 → 全量基础清单
  · 选「动火 + 高温」→ 出现动火许可 / 看火人 / 灭火器材 / 防暑项，且带命中理由
  · 导入 6 行含 1 行错 → 标错误行、正确行入库
另外覆盖实测踩到的两个坑：
  · 表头行「类别,检查内容,判定要点,依据」被当成数据
  · 过短内容（如单字「乙」）应标错而不是当有效项
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sitesaha import checklists as C  # noqa: E402


class GenerateTests(unittest.TestCase):
    def test_no_conditions_returns_baseline_only(self) -> None:
        result = C.generate([])
        self.assertEqual(result["stats"]["required"], 0)
        self.assertGreater(result["stats"]["routine"], 0)
        self.assertEqual(result["conditions"], [])

    def test_none_conditions_do_not_crash(self) -> None:
        self.assertEqual(C.generate(None)["stats"]["required"], 0)

    def test_hotwork_and_heat_accepted_items(self) -> None:
        """§11.D 验收：动火 + 高温要出现许可 / 看火人 / 灭火器 / 防暑。"""
        result = C.generate(["hotwork", "heat"])
        blob = " ".join(item["content"] for item in result["required"])
        self.assertIn("动火许可证", blob)
        self.assertIn("看火人", blob)
        self.assertIn("灭火器材", blob)
        self.assertIn("防暑", blob)

    def test_every_required_item_carries_reason(self) -> None:
        """每条必查都要能说清被哪个条件命中。"""
        result = C.generate(["hotwork", "heat"])
        for item in result["required"]:
            self.assertTrue(item["source"], item)
            self.assertTrue(item["source_key"], item)
            self.assertIn(item["source_key"], {"hotwork", "heat"})

    def test_items_have_stable_shape(self) -> None:
        result = C.generate(["height"])
        for item in result["required"] + result["routine"]:
            for field in ("code", "category", "content", "judge", "basis",
                          "mandatory", "source", "origin"):
                self.assertIn(field, item, field)
            self.assertTrue(item["category"])

    def test_unknown_conditions_ignored(self) -> None:
        result = C.generate(["hotwork", "not_a_condition", "", "  "])
        self.assertEqual([c["key"] for c in result["conditions"]], ["hotwork"])

    def test_duplicate_conditions_deduped(self) -> None:
        result = C.generate(["heat", "heat", "heat"])
        self.assertEqual(len(result["conditions"]), 1)

    def test_basis_never_invented_for_project_rules(self) -> None:
        """对不上国标的条目要写「项目制度」，不能编条款号。"""
        result = C.generate(None)
        for item in result["routine"]:
            basis = item["basis"]
            self.assertTrue(basis)
            if basis != "项目制度":
                # 写了标准号就必须长得像标准号
                self.assertRegex(basis, r"[A-Z]{2,}|GB|JGJ|项目")


class ParseDelimitedTests(unittest.TestCase):
    SAMPLE = """# 项目自有班前检查补充
类别,检查内容,判定要点,依据
临时设施,宿舍内是否使用大功率电器,无电炉热得快等,项目制度
消防,灭火器压力表是否在绿区,指针在绿区且在有效期内,项目制度
- 塔吊基础是否有积水
乙
5、高处作业平台是否设置防坠栏杆
配电箱,箱内是否堆放杂物,箱内无杂物,项目制度
"""

    def test_header_row_is_skipped(self) -> None:
        """实测踩过的坑：表头被当成数据行。"""
        rows = C.parse_delimited(self.SAMPLE)
        for row in rows:
            self.assertNotEqual(row["content"], "检查内容")
            self.assertNotEqual(row["category"], "类别")

    def test_comment_lines_skipped(self) -> None:
        rows = C.parse_delimited(self.SAMPLE)
        for row in rows:
            self.assertFalse(row["content"].startswith("#"))

    def test_markdown_bullet_and_number_stripped(self) -> None:
        rows = C.parse_delimited(self.SAMPLE)
        contents = [row["content"] for row in rows]
        self.assertIn("塔吊基础是否有积水", contents)
        self.assertIn("高处作业平台是否设置防坠栏杆", contents)

    def test_short_line_flagged_as_error(self) -> None:
        """单字行「乙」必须标错，不能当有效检查项。"""
        rows = C.parse_delimited(self.SAMPLE)
        short = [row for row in rows if row["content"] == "乙"]
        self.assertEqual(len(short), 1)
        self.assertTrue(short[0]["error"])

    def test_four_column_row_parsed(self) -> None:
        rows = C.parse_delimited(self.SAMPLE)
        target = [r for r in rows if "大功率电器" in r["content"]]
        self.assertEqual(len(target), 1)
        self.assertEqual(target[0]["category"], "临时设施")
        self.assertEqual(target[0]["basis"], "项目制度")

    def test_import_marked_as_project_owned(self) -> None:
        """导入内容必须标注「项目自有文件」，不得冒充国标条款。"""
        rows = C.parse_delimited(self.SAMPLE)
        for row in rows:
            self.assertEqual(row["origin"], "项目自有文件")

    def test_single_column_defaults_category(self) -> None:
        rows = C.parse_delimited("检查脚手架连墙件是否缺失")
        self.assertEqual(rows[0]["category"], "项目自定义")


class NormalizeImportTests(unittest.TestCase):
    def test_accepts_good_and_rejects_bad(self) -> None:
        rows = C.parse_delimited(ParseDelimitedTests.SAMPLE)
        result = C.normalize_import(rows)
        self.assertEqual(len(result["rejected"]), 1)
        self.assertGreaterEqual(len(result["accepted"]), 5)

    def test_accepted_items_numbered(self) -> None:
        rows = C.parse_delimited(ParseDelimitedTests.SAMPLE)
        result = C.normalize_import(rows)
        codes = [item["code"] for item in result["accepted"]]
        self.assertEqual(codes[0], "I-01")
        self.assertEqual(len(set(codes)), len(codes))

    def test_duplicates_dropped(self) -> None:
        text = "消防,灭火器是否有效,在有效期内\n消防,灭火器是否有效,在有效期内"
        rows = C.parse_delimited(text)
        result = C.normalize_import(rows)
        self.assertEqual(len(result["accepted"]), 1)
        self.assertEqual(result["duplicates"], 1)

    def test_empty_input(self) -> None:
        result = C.normalize_import(C.parse_delimited(""))
        self.assertEqual(result["accepted"], [])
        self.assertEqual(result["rejected"], [])


class RuleTableTests(unittest.TestCase):
    def test_every_rule_trigger_is_known(self) -> None:
        for rule in C.RULES:
            self.assertIn(rule["trigger"], C.ALL_CONDITION_KEYS, rule["trigger"])
            self.assertTrue(rule["items"], rule["trigger"])

    def test_every_condition_has_a_rule(self) -> None:
        """每个可选条件都要有对应规则，否则选了等于没选。"""
        covered = {rule["trigger"] for rule in C.RULES}
        missing = C.ALL_CONDITION_KEYS - covered
        self.assertEqual(missing, set(), f"这些条件没有规则：{missing}")

    def test_all_items_have_basis(self) -> None:
        for rule in C.RULES:
            for item in rule["items"]:
                self.assertTrue(item.get("basis"), item)


if __name__ == "__main__":
    unittest.main()
