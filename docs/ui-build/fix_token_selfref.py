"""修上一次批量替换造成的循环引用（第 21 轮）。

事故：我用「整行含该十六进制就替换」的粗糙逻辑，把**变量定义**也换了：
    --surface:#ffffff;        →  --surface:var(--surface);         ← 自引用，暗色主题崩
    --danger-100:#f0c4bc;     →  --danger-100:var(--danger-100);   ← 同上
    --green-bg:#12291d;       →  --green-bg:var(--risk-low-bg);    ← 语义被改，暗色主题变浅

教训：替换颜色必须区分「定义」与「使用」——
      定义行（--xxx: #hex;）不能替换成变量引用。

本脚本恢复这三处定义，只保留真正的使用处替换。

用法：python fix_token_selfref.py [--dry-run]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent

RESTORE = [
    ("v15_dark.css", "  --green-bg:var(--risk-low-bg);", "  --green-bg:#12291d;"),
    ("v15_theme.css", "  --surface:var(--surface);", "  --surface:#ffffff;"),
    ("v15_theme.css", "  --danger-100:var(--danger-100);", "  --danger-100:#f0c4bc;"),
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    applied = 0
    for filename, broken, fixed in RESTORE:
        path = BUILD / filename
        if not path.is_file():
            print(f"  [跳过] {filename} 不存在")
            continue
        text = path.read_text(encoding="utf-8")
        if broken in text:
            text = text.replace(broken, fixed, 1)
            path.write_text(text, encoding="utf-8")
            applied += 1
            print(f"  [ok] {filename}: 恢复 {fixed.strip()}")
        elif fixed in text:
            print(f"  [跳过] {filename}: {fixed.strip()} 已正确")
        else:
            print(f"  [注意] {filename}: 找不到 {broken.strip()}")

    # ---- 全量自查：还有没有别的自引用 ----
    print()
    print("=" * 70)
    print("自查：所有变量定义里是否还有自引用")
    print("=" * 70)
    problems = 0
    for path in sorted(BUILD.glob("*.css")):
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(r"(--[a-z0-9-]+)\s*:\s*var\((--[a-z0-9-]+)\)", text):
            if match.group(1) == match.group(2):
                line = text[: match.start()].count("\n") + 1
                print(f"  [BUG] {path.name}:{line}  {match.group(0)}")
                problems += 1
    if problems == 0:
        print("  没有自引用 ✅")
    else:
        print(f"  仍有 {problems} 处")
        return 1

    if args.dry_run:
        print(f"\n（dry-run，未写入；{applied} 处）")
        return 0
    print(f"\n[ok] 已修 {applied} 处")
    return 0


if __name__ == "__main__":
    sys.exit(main())
