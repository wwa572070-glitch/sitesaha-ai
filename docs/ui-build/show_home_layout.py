"""打印首页区块的结构骨架，便于规划按流程分类重组。"""

from __future__ import annotations

import re
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
BODY = BUILD / "index_body.html"
VOID = {"input", "img", "br", "meta", "hr", "source", "link"}


def main() -> int:
    body = BODY.read_text(encoding="utf-8")
    start = body.find('<section id="home"')
    if start < 0:
        print("[FAIL] 找不到首页区块")
        return 1
    nxt = re.search(r'<section id="(?!home")', body[start + 10:])
    end = start + 10 + nxt.start() if nxt else len(body)
    home = body[start:end]
    print(f"首页区块 {len(home)} 字符\n")

    depth = 0
    for raw in home.split("\n"):
        line = raw.strip()
        if not line:
            continue
        token = re.match(r"<(/?)([a-zA-Z0-9]+)([^>]*)>", line)
        if not token:
            continue
        closing, tag, attrs = token.groups()
        if closing:
            depth = max(0, depth - 1)
            if tag in {"div", "section", "aside"}:
                print(f"{'  ' * min(depth, 7)}</{tag}>")
            continue

        ident = re.search(r'id="([^"]+)"', attrs)
        klass = re.search(r'class="([^"]+)"', attrs)
        label = f"<{tag}"
        if ident:
            label += f" #{ident.group(1)}"
        if klass:
            label += f" .{klass.group(1).split()[0]}"
        label += ">"
        if tag in {"div", "section", "aside", "h2", "h3", "p", "span"}:
            print(f"{'  ' * min(depth, 7)}{label}")
        if tag not in VOID and not line.endswith("/>"):
            depth += 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
