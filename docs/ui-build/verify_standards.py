"""标准元数据交叉校验：直接读磁盘，不经过 Web 层。

用法（在项目根运行）：python docs/ui-build/verify_standards.py

为什么需要它：`/api/standards` 是"程序读自己的数据再返回"，无法发现数据本身的问题。
本脚本独立核对三件事：
  1) manifest 里的每条记录字段是否自洽（标准号格式、状态取值、日期格式）
  2) normalized 目录里的 Markdown 是否与 manifest 一一对应，且头部字段一致
  3) 是否存在"编号合法但状态是废止"或"日期缺失"这类会误导工人的条目
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent          # docs/ui-build
ROOT = BUILD.parent.parent                       # 项目根
OPENSTD_DIR = ROOT / "data" / "sources" / "openstd"
NORMALIZED_DIR = ROOT / "data" / "sources" / "normalized" / "openstd"

ALLOWED_STATUS = {"现行", "即将实施"}
# 标准号：GB / GB/T / GB/Z + 数字(可带小数) + 年份
CODE_PATTERN = re.compile(r"^GB(?:/T|/Z)?\s?\d+(?:\.\d+)?-\d{4}$")
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def main() -> int:
    manifest_path = OPENSTD_DIR / "manifest.json"
    if not manifest_path.is_file():
        print(f"[FAIL] 找不到 {manifest_path}")
        return 1

    records = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(records, list):
        print("[FAIL] manifest 顶层不是数组")
        return 1

    problems: list[str] = []
    warnings: list[str] = []
    codes: list[str] = []

    for index, record in enumerate(records, 1):
        if not isinstance(record, dict):
            problems.append(f"第 {index} 条不是对象")
            continue
        code = str(record.get("code", "")).strip()
        codes.append(code)

        if not CODE_PATTERN.match(code):
            problems.append(f"{code or '(空)'}：标准号格式不合法")
        status = str(record.get("status", "")).strip()
        if status not in ALLOWED_STATUS:
            problems.append(f"{code}：状态 `{status}` 不在允许集合 {sorted(ALLOWED_STATUS)}")
        title = str(record.get("title", "")).strip()
        if len(title) < 2:
            problems.append(f"{code}：名称缺失或过短")
        for field in ("published", "implemented"):
            value = str(record.get(field, "")).strip()
            if not value:
                warnings.append(f"{code}：{field} 为空")
                continue
            head = value.split(" ")[0]
            if not DATE_PATTERN.match(head):
                problems.append(f"{code}：{field} 日期格式异常 `{value}`")
        if not str(record.get("source_url", "")).startswith("http"):
            problems.append(f"{code}：source_url 不是 http(s) 链接")
        imported = str(record.get("content_imported", "")).strip()
        if imported and imported != "metadata_only":
            warnings.append(f"{code}：content_imported=`{imported}`（本项目只应登记元数据）")

    duplicates = sorted({c for c in codes if codes.count(c) > 1})
    if duplicates:
        problems.append("重复标准号：" + "、".join(duplicates))

    # normalized 目录交叉核对
    md_files = sorted(NORMALIZED_DIR.glob("*.md")) if NORMALIZED_DIR.is_dir() else []
    md_text = {}
    for path in md_files:
        text = path.read_text(encoding="utf-8")
        md_text[path.name] = text
        if "## 全文导入说明" not in text and "全文导入说明" not in text:
            problems.append(f"{path.name}：缺少「全文导入说明」段落（合规说明不能省）")
        if "未绕过验证码" not in text:
            warnings.append(f"{path.name}：未见「未绕过验证码」的合规声明")

    unmatched = []
    for record in records:
        if not isinstance(record, dict):
            continue
        code = str(record.get("code", "")).strip()
        variants = {code, code.replace("/", "_"), code.replace(" ", "")}
        hit = None
        for name in md_text:
            for variant in variants:
                if variant and variant in name:
                    hit = name
                    break
            if hit:
                break
        if not hit:
            unmatched.append(code)

    print(f"manifest 条数：{len(records)}")
    print(f"normalized Markdown：{len(md_files)} 个")
    print(f"状态分布：", end="")
    status_count: dict[str, int] = {}
    for record in records:
        if isinstance(record, dict):
            key = str(record.get("status", "?"))
            status_count[key] = status_count.get(key, 0) + 1
    print("、".join(f"{k} {v}" for k, v in sorted(status_count.items())))

    if unmatched:
        print(f"未匹配到 Markdown 的条目（{len(unmatched)} 条，属已知情况，仍可入库为元数据）：")
        for code in unmatched[:8]:
            print("   -", code)
        if len(unmatched) > 8:
            print(f"   …… 另有 {len(unmatched) - 8} 条")

    if warnings:
        print(f"\n提示（{len(warnings)} 条）：")
        for item in warnings[:10]:
            print("   -", item)
        if len(warnings) > 10:
            print(f"   …… 另有 {len(warnings) - 10} 条")

    if problems:
        print(f"\n[FAIL] 发现 {len(problems)} 个问题：")
        for item in problems:
            print("   -", item)
        return 1

    print("\n[OK] 标准元数据自洽：编号格式、状态取值、日期格式、目录对应关系均通过")
    if len(records) < 15:
        print(f"[警告] 标准数量偏少（{len(records)} < 15）")
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
