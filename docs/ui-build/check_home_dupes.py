"""检查首页里同标题模块是"嵌套"还是"真重复"，并给出各模块的唯一性清单。"""

from __future__ import annotations

import re
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
BODY = BUILD / "index_body.html"


def find_panels(text: str) -> list[tuple[int, int, str, bool]]:
    """返回 (start, end, title, nested)。nested 表示该 panel 位于另一个 panel 内部。"""
    spans = []
    for match in re.finditer(r'<div class="panel[^"]*"', text):
        depth = 0
        i = match.start()
        while i < len(text):
            nxt = re.search(r"<(/?)div\b[^>]*>", text[i:])
            if not nxt:
                break
            depth += -1 if nxt.group(1) == "/" else 1
            i += nxt.end()
            if depth == 0:
                break
        block = text[match.start():i]
        head = re.search(r"<h2[^>]*>(.*?)</h2>", block, re.S)
        title = re.sub(r"<[^>]+>", "", head.group(1)).strip() if head else "(无标题)"
        spans.append((match.start(), i, title))

    out = []
    for start, end, title in spans:
        nested = any(s < start and end <= e for s, e, _t in spans if (s, e) != (start, end))
        out.append((start, end, title, nested))
    return out


def main() -> int:
    body = BODY.read_text(encoding="utf-8")
    start = body.find('<section id="home"')
    nxt = re.search(r'<section id="(?!home")', body[start + 10:])
    end = start + 10 + nxt.start() if nxt else len(body)
    home = body[start:end]

    panels = find_panels(home)
    print(f"首页 <div class=\"panel\"> 匹配 {len(panels)} 处\n")
    print(f"{'标题':<26} {'大小':>7}  {'嵌套在别的 panel 里'}")
    print("-" * 62)
    outer = []
    for s, e, title, nested in panels:
        flag = "是（不是独立模块）" if nested else "否"
        print(f"{title[:24]:<26} {e - s:>7}  {flag}")
        if not nested:
            outer.append((title, e - s))

    print()
    print(f"真正独立的模块：{len(outer)} 个")
    for title, size in outer:
        print(f"  · {title:<26} {size:>7}")

    print()
    titles = [t for t, _ in outer]
    dupes = {t for t in titles if titles.count(t) > 1}
    print(f"独立模块中的重复标题：{dupes if dupes else '无'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
