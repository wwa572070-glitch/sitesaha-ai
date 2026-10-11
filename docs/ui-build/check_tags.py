"""逐行做 div/section 栈检查，定位标签不配平的准确行号。"""

from __future__ import annotations

import re
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
BODY = BUILD / "index_body.html"
TRACKED = ("div", "section", "aside", "style", "header", "nav", "main", "footer")


def main() -> int:
    lines = BODY.read_text(encoding="utf-8").split("\n")
    stack: list[tuple[str, int]] = []
    problems: list[str] = []

    for number, line in enumerate(lines, 1):
        for match in re.finditer(r"<(/?)([a-zA-Z0-9]+)\b[^>]*?(/?)>", line):
            closing, tag, self_close = match.groups()
            if tag not in TRACKED or self_close:
                continue
            if closing:
                if not stack:
                    problems.append(f"第 {number} 行：</{tag}> 没有对应的开标签")
                    continue
                top_tag, top_line = stack.pop()
                if top_tag != tag:
                    problems.append(
                        f"第 {number} 行：</{tag}> 与第 {top_line} 行的 <{top_tag}> 不匹配"
                    )
            else:
                stack.append((tag, number))

    print(f"扫描 {len(lines)} 行，未闭合 {len(stack)} 个")
    for tag, line in stack[-8:]:
        print(f"  未闭合：第 {line} 行 <{tag}>")
    if problems:
        print(f"\n问题 {len(problems)} 处：")
        for item in problems[:12]:
            print("  -", item)
    return 1 if stack or problems else 0


if __name__ == "__main__":
    sys.exit(main())
