"""§3 收尾：pre 收敛到达标（第 20 轮 P0）。

实测 pre = 5148px（6.1 屏），目标 ≤6 屏（5064px），只差 84px。

把「导入项目自有清单」panel 收进折叠即可达标 ——
它是低频操作，不该常驻占屏。

用法：python patch_pre_import_fold.py [--dry-run]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
BODY = BUILD / "index_body.html"

TAG = re.compile(r"<(/?)(div)\b[^>]*?(/?)>")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    body = BODY.read_text(encoding="utf-8")
    if "<summary>导入项目自有清单" in body:
        print("[跳过] 已折叠")
        return 0

    index = body.find("导入项目自有清单")
    if index < 0:
        print("[FAIL] 找不到导入面板")
        return 1
    start = body.rfind('<div class="panel"', 0, index)
    if start < 0:
        print("[FAIL] 找不到 panel 起点")
        return 1

    depth = 0
    position = start
    end = None
    while position < len(body):
        match = TAG.search(body, position)
        if not match:
            break
        position = match.end()
        if match.group(1) == "/":
            depth -= 1
            if depth == 0:
                end = match.end()
                break
        elif match.group(3) != "/":
            depth += 1
    if end is None:
        print("[FAIL] 找不到 panel 终点")
        return 1

    block = body[start:end]
    body = (
        body[:start]
        + '<details class="disclosure">\n'
        + '  <summary>导入项目自有清单'
        + '<span class="disclosure-hint">csv / txt / md / xlsx</span></summary>\n'
        + '  <div class="disclosure-body">\n' + block + '\n  </div>\n'
        + '</details>'
        + body[end:]
    )
    print(f"[ok] 导入面板已折叠（原块 {len(block)} 字符）")

    if body.count(chr(92)):
        print("[FAIL] 含反斜杠")
        return 1
    print("[ok] 无反斜杠")

    if args.dry_run:
        print("（dry-run，未写入）")
        return 0
    BODY.write_text(body, encoding="utf-8")
    print("[ok] 已写入")
    return 0


if __name__ == "__main__":
    sys.exit(main())
