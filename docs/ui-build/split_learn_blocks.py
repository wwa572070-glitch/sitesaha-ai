"""按 h2 标题切出 learn 视图的 17 个逻辑块，并给出精确边界。

不用正则贪婪匹配，而是按 div 深度配对找每个 <div class="panel"> 的完整范围，
再按 h2 标题给它们命名。输出用于 IA 收敛脚本的锚点。

用法：python split_learn_blocks.py [--json]
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
BODY = BUILD / "index_body.html"

TAG = re.compile(r"<(/?)(div)\b[^>]*?(/?)>")


def find_blocks(segment: str) -> list[tuple[int, int]]:
    """找出所有顶层 <div class="panel..."> 的 (start, end)，按 div 深度配对。"""
    blocks: list[tuple[int, int]] = []
    for match in re.finditer(r'<div class="panel[^"]*"', segment):
        start = match.start()
        depth = 0
        position = start
        while position < len(segment):
            tag = TAG.search(segment, position)
            if not tag:
                break
            position = tag.end()
            if tag.group(1) == "/":
                depth -= 1
                if depth == 0:
                    blocks.append((start, tag.end()))
                    break
            elif tag.group(3) != "/":
                depth += 1
    return blocks


def main() -> int:
    body = BODY.read_text(encoding="utf-8")
    start = body.find('<section id="learn"')
    end = body.find('<section id="', start + 10)
    segment = body[start:end]

    blocks = find_blocks(segment)
    # 只保留不互相包含的顶层块
    top: list[tuple[int, int]] = []
    for item in sorted(blocks, key=lambda pair: (pair[0], -pair[1])):
        if any(outer[0] <= item[0] and item[1] <= outer[1] for outer in top):
            continue
        top.append(item)

    records = []
    for index, (block_start, block_end) in enumerate(top, 1):
        text = segment[block_start:block_end]
        heading = re.search(r"<h2[^>]*>(.*?)</h2>", text, re.S)
        title = re.sub(r"<[^>]+>", "", heading.group(1)).strip() if heading else "(无标题)"
        line = segment[:block_start].count("\n") + 1
        records.append({
            "n": index,
            "line": line,
            "title": title,
            "chars": len(text),
            "ids": re.findall(r'id="([^"]+)"', text),
            "start": block_start,
            "end": block_end,
        })

    if "--json" in sys.argv:
        print(json.dumps(records, ensure_ascii=False, indent=1))
        return 0

    print(f"learn 视图 {len(segment)} 字符，顶层 panel {len(records)} 个\n")
    for item in records:
        print(f"  {item['n']:>2}. 行{item['line']:<5} {item['chars']:>5} 字符  {item['title'][:44]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
