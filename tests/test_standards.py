"""``sitesaha.standards.load_standards`` 的只读契约测试。

故意**不使用 tempfile**：本项目的沙箱会拒绝临时目录（WinError 5），
这里直接用仓库内 ``data/`` 下的固定文件，保证测试在沙箱里可复现。
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from sitesaha.standards import (
    DEFAULT_TYPE,
    KNOWN_STATUSES,
    STANDARD_FIELDS,
    empty_standards,
    load_standards,
    normalize_date,
    normalize_status,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent

OPENSTD_DIR = PROJECT_ROOT / "data" / "sources" / "openstd"
NORMALIZED_DIR = PROJECT_ROOT / "data" / "sources" / "normalized" / "openstd"

#: 状态白名单，另加实现约定的兜底值「未知」。
ALLOWED_STATUSES = set(KNOWN_STATUSES) | {"未知"}

DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class StandardsFixtureMixin:
    """共享一份真实数据快照，避免每个用例重复读盘。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.payload = load_standards(PROJECT_ROOT)
        cls.items = cls.payload["items"]


class StandardsDataTests(StandardsFixtureMixin, unittest.TestCase):
    def test_real_data_loads_with_items(self) -> None:
        self.assertIsInstance(self.payload, dict)
        self.assertTrue(self.items, "真实 openstd 清单应至少产出一条标准")
        self.assertEqual(self.payload["counts"]["total"], len(self.items))

    def test_counts_match_status_buckets(self) -> None:
        counts = self.payload["counts"]
        expected_active = sum(1 for item in self.items if item["status"] == "现行")
        expected_pending = sum(
            1 for item in self.items if item["status"] == "即将实施"
        )
        self.assertEqual(counts["active"], expected_active)
        self.assertEqual(counts["pending"], expected_pending)
        self.assertLessEqual(counts["active"] + counts["pending"], counts["total"])

    def test_every_item_has_expected_fields(self) -> None:
        for item in self.items:
            for field in STANDARD_FIELDS:
                self.assertIn(field, item)
                self.assertIsInstance(item[field], str)

    def test_items_are_not_fabricated(self) -> None:
        """产出的条目必须能在清单里逐条对上，且字段值与清单一致。"""
        records = json.loads(
            (OPENSTD_DIR / "manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(len(self.items), len(records))
        by_code = {record["code"]: record for record in records}
        for item in self.items:
            record = by_code.get(item["code"])
            self.assertIsNotNone(record, f"清单里没有标准号 {item['code']}")
            self.assertEqual(item["title"], record["title"])
            self.assertEqual(item["published"], record["published"].split(" ")[0])
            self.assertEqual(
                item["implemented"], record["implemented"].split(" ")[0]
            )
            self.assertEqual(item["source_url"], record["source_url"])
            self.assertEqual(item["preview_url"], record["preview_url"])
            self.assertEqual(item["content_imported"], record["content_imported"])

    def test_status_values_are_within_whitelist(self) -> None:
        for item in self.items:
            self.assertIn(item["status"], ALLOWED_STATUSES)

    def test_type_is_never_empty(self) -> None:
        for item in self.items:
            self.assertTrue(item["type"])
            self.assertEqual(item["type"], item["type"].strip())

    def test_dates_are_normalized(self) -> None:
        for item in self.items:
            for field in ("published", "implemented"):
                value = item[field]
                if not value:
                    continue
                self.assertNotIn("00:00:00", value)
                self.assertNotIn(" ", value)
                self.assertRegex(value, DATE_PATTERN)

    def test_normalized_file_exists_on_disk(self) -> None:
        matched = 0
        for item in self.items:
            name = item["normalized_file"]
            if not name:
                continue
            matched += 1
            self.assertEqual(Path(name).name, name, "应只返回文件名")
            self.assertTrue(
                (NORMALIZED_DIR / name).is_file(),
                f"{name} 在 normalized/openstd 下不存在",
            )
        self.assertGreater(matched, 0, "真实数据里应能匹配到标准化文件")

    def test_generated_at_comes_from_acquisition_log(self) -> None:
        acquisition = json.loads(
            (
                PROJECT_ROOT / "data" / "sources" / "acquisition.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(self.payload["generated_at"], acquisition["completed_at"])


class StandardsMissingDataTests(unittest.TestCase):
    def test_missing_path_returns_empty_structure(self) -> None:
        payload = load_standards(PROJECT_ROOT / "no_such_dir_9f3c1a")
        self.assertEqual(payload, empty_standards())
        self.assertEqual(payload["items"], [])
        self.assertEqual(
            payload["counts"], {"total": 0, "active": 0, "pending": 0}
        )
        self.assertEqual(payload["generated_at"], "")

    def test_empty_results_are_independent_copies(self) -> None:
        first = load_standards(PROJECT_ROOT / "no_such_dir_9f3c1a")
        first["items"].append({"code": "污染"})
        second = load_standards(PROJECT_ROOT / "no_such_dir_9f3c1a")
        self.assertEqual(second["items"], [])


class StandardsHelperTests(unittest.TestCase):
    def test_normalize_date_strips_time_part(self) -> None:
        self.assertEqual(normalize_date("2020-07-01 00:00:00.0"), "2020-07-01")
        self.assertEqual(normalize_date("2019-12-31T10:00:00"), "2019-12-31")
        self.assertEqual(normalize_date(" 2020-07-01 "), "2020-07-01")
        self.assertEqual(normalize_date(""), "")
        self.assertEqual(normalize_date(None), "")

    def test_normalize_status_falls_back_to_unknown(self) -> None:
        self.assertEqual(normalize_status("现行"), "现行")
        self.assertEqual(normalize_status("即将实施"), "即将实施")
        self.assertEqual(normalize_status("已废止"), "已废止")
        self.assertEqual(normalize_status("作废"), "未知")
        self.assertEqual(normalize_status(None), "未知")

    def test_default_type_constant(self) -> None:
        self.assertEqual(DEFAULT_TYPE, "国家标准")


if __name__ == "__main__":
    unittest.main()
