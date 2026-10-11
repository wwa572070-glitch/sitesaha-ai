"""列出脚本里每处 emoji 的精确上下文，供人工确认替换方式。

用法：python list_script_emoji.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
FILES = ["index_script_a.js", "index_script_b.js"]
PATTERN = re.compile(r"[\U0001F300-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF]")


def main() -> int:
    for name in FILES:
        text = (BUILD / name).read_text(encoding="utf-8")
        print(f"===== {name}")
        for index, match in enumerate(PATTERN.finditer(text), 1):
            start = match.start()
            line = text[:start].count("\n") + 1
            ctx = text[max(0, start - 95): start + 70].replace("\n", " ")
            print(f"  {index:>2}. 行 {line:<5} {match.group(0)!r:<6} …{' '.join(ctx.split())}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
