"""列出首页里每个 .panel 的标题，用于归类重组。"""

from __future__ import annotations

import re
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
BODY = BUILD / "index_body.html"


def panels(text: str) -> list[tuple[str, int, int]]:
    """返回 (标题, 起始, 结束) 列表；按 <div class="panel"> 配对花括号深度切分。"""
    out: list[tuple[str, int, int]] = []
    for match in re.finditer(r'<div class="panel"', text):
        # 从该 <div 开始按标签深度扫描到配对结束
        depth = 0
        i = match.start()
        while i < len(text):
            nxt = re.search(r"<(/?)div\b[^>]*>", text[i:])
            if not nxt:
                break
            if nxt.group(1) == "/":
                depth -= 1
            else:
                depth += 1
            i += nxt.end()
            if depth == 0:
                break
        block = text[match.start():i]
        head = re.search(r"<h2[^>]*>(.*?)</h2>", block, re.S)
        title = re.sub(r"<[^>]+>", "", head.group(1)).strip() if head else "(无标题)"
        out.append((title, match.start(), i))
    return out


def main() -> int:
    body = BODY.read_text(encoding="utf-8")
    start = body.find('<section id="home"')
    nxt = re.search(r'<section id="(?!home")', body[start + 10:])
    end = start + 10 + nxt.start() if nxt else len(body)
    home = body[start:end]

    found = panels(home)
    print(f"首页共 {len(found)} 个 .panel：\n")
    for index, (title, s, e) in enumerate(found, 1):
        print(f"{index:2}. {title[:46]:<48} {e - s:>6} 字符")
    return 0


if __name__ == "__main__":
    sys.exit(main())
