"""sitesaha/xlsx.py 的测试（第 16 轮 §11.C）。

用 openpyxl 造测试文件（仅测试期用），运行时代码只依赖标准库。
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sitesaha import checklists as C  # noqa: E402
from sitesaha import xlsx  # noqa: E402

try:
    from openpyxl import Workbook

    HAS_OPENPYXL = True
except ImportError:  # pragma: no cover
    HAS_OPENPYXL = False


def make_xlsx(rows: list[list[str]]) -> bytes:
    from io import BytesIO

    workbook = Workbook()
    sheet = workbook.active
    for row in rows:
        sheet.append(row)
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


@unittest.skipUnless(HAS_OPENPYXL, "需要 openpyxl 造测试文件")
class XlsxReadTests(unittest.TestCase):
    def test_reads_shared_strings(self) -> None:
        data = make_xlsx([
            ["类别", "检查内容", "判定要点", "依据"],
            ["消防", "灭火器压力表是否在绿区", "指针在绿区", "项目制度"],
        ])
        rows = xlsx.read_rows(data)
        self.assertGreaterEqual(len(rows), 2)
        self.assertEqual(rows[0][0], "类别")
        self.assertEqual(rows[1][1], "灭火器压力表是否在绿区")

    def test_reads_numbers(self) -> None:
        data = make_xlsx([["序号", "内容"], [1, "检查内容示例"]])
        rows = xlsx.read_rows(data)
        self.assertEqual(rows[1][0], "1")

    def test_to_text_is_comma_separated(self) -> None:
        data = make_xlsx([
            ["类别", "检查内容", "判定要点", "依据"],
            ["消防", "灭火器压力表是否在绿区", "指针在绿区", "项目制度"],
        ])
        text = xlsx.to_text(data)
        self.assertIn("消防,灭火器压力表是否在绿区", text)

    def test_bad_zip_raises_friendly_error(self) -> None:
        with self.assertRaises(xlsx.XlsxError) as ctx:
            xlsx.read_rows(b"this is not a zip file at all")
        self.assertIn("xlsx", str(ctx.exception))

    def test_empty_workbook(self) -> None:
        data = make_xlsx([[]])
        self.assertEqual(xlsx.read_rows(data), [])


@unittest.skipUnless(HAS_OPENPYXL, "需要 openpyxl 造测试文件")
class XlsxToImportTests(unittest.TestCase):
    def test_end_to_end_import_with_one_error_row(self) -> None:
        """§11.D 验收：导入 6 行含 1 行错 → 标错误行、正确行入库。"""
        data = make_xlsx([
            ["类别", "检查内容", "判定要点", "依据"],
            ["临时设施", "宿舍内是否使用大功率电器", "无电炉热得快", "项目制度"],
            ["消防", "灭火器压力表是否在绿区", "指针在绿区", "项目制度"],
            ["塔吊", "塔吊基础是否有积水", "无积水", "项目制度"],
            ["", "乙", "", ""],
            ["高处", "高处作业平台是否设置防坠栏杆", "栏杆齐全", "项目制度"],
        ])
        rows = C.parse_delimited(xlsx.to_text(data))
        result = C.normalize_import(rows)

        self.assertEqual(len(result["rejected"]), 1)
        self.assertEqual(result["rejected"][0]["content"], "乙")
        self.assertEqual(len(result["accepted"]), 4)
        for item in result["accepted"]:
            self.assertEqual(item["origin"], "项目自有文件")


if __name__ == "__main__":
    unittest.main()
