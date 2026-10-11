"""去掉 §11 前端脚本里的 5 个反斜杠（分片硬约束）。

inject.py 拒绝任何反斜杠，这是个硬约束（之前踩过一次）。
JS 里常见的反斜杠来自正则转义与换行转义，都有无反斜杠的等价写法：

  /\\.xlsx$/i          →  用 indexOf 判断扩展名
  /[",\\n]/            →  用 indexOf 判断是否含逗号/引号/换行
  "\\n"                →  String.fromCharCode(10)
  "\\r\\n"             →  String.fromCharCode(13, 10)
  "\\ufeff"            →  String.fromCharCode(65279)   // BOM

用法：python strip_pre_backslash.py [--dry-run]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
SCRIPT_B = BUILD / "index_script_b.js"

BS = chr(92)  # 反斜杠：脚本里不写字面量，避免本文件本身也被判违规

EDITS: list[tuple[str, str, str]] = [
    (
        "xlsx 扩展名判断",
        "var isXlsx = /" + BS + ".xlsx$/i.test(file.name);",
        'var isXlsx = file.name.toLowerCase().indexOf(".xlsx") >= 0;',
    ),
    (
        "CSV 转义判断",
        'return /[",' + BS + 'n]/.test(text) ?',
        'return (text.indexOf(",") >= 0 || text.indexOf(String.fromCharCode(34)) >= 0'
        " || text.indexOf(String.fromCharCode(10)) >= 0) ?",
    ),
    (
        "CSV 行尾",
        'lines.join("' + BS + 'r' + BS + 'n")',
        "lines.join(String.fromCharCode(13, 10))",
    ),
    (
        "BOM 前缀",
        '"' + BS + 'ufeff" + lines.join',
        "String.fromCharCode(65279) + lines.join",
    ),
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    text = SCRIPT_B.read_text(encoding="utf-8")
    before = text.count(BS)
    print(f"[信息] 修改前反斜杠 {before} 个")
    if before == 0:
        print("[跳过] 已经没有反斜杠")
        return 0

    applied = 0
    for note, old, new in EDITS:
        if old in text:
            text = text.replace(old, new, 1)
            applied += 1
            print(f"  [ok] {note}")
        else:
            print(f"  [跳过] {note}（锚点未匹配）")

    after = text.count(BS)
    print(f"[复核] 修改后反斜杠 {after} 个")
    if after:
        import re
        for match in re.finditer(re.escape(BS) + r".{0,60}", text):
            line = text[: match.start()].count("\n") + 1
            print(f"   还剩 行 {line}: {' '.join(match.group(0).split())[:90]}")
        print("[FAIL] 还有残留")
        return 1

    if args.dry_run:
        print(f"（dry-run，未写入；{applied} 处）")
        return 0
    SCRIPT_B.write_text(text, encoding="utf-8")
    print(f"[ok] 已写入（{applied} 处），无反斜杠")
    return 0


if __name__ == "__main__":
    sys.exit(main())
