"""统计 §3.1「SVG 被当成文字打印」的全部受影响位置。

根因：make(tag, className, value) 用 node.textContent = String(value)，
而部分调用点传的是 HTML 字符串（含 <svg>），于是标签被转义成可见文本。

本脚本把三类位置都找出来：
  1. make(...) 第三参直接含 <svg>
  2. make(...) 第三参是变量，但赋值处含 <svg>（如 scene.icon）
  3. .textContent = 右侧含 <svg>

用法：python audit_svg_as_text.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
FILES = ["index_script_a.js", "index_script_b.js"]


def main() -> int:
    js = ""
    offsets: list[tuple[str, int]] = []
    for name in FILES:
        start = len(js)
        js += (BUILD / name).read_text(encoding="utf-8")
        offsets.append((name, start))

    def where(index: int) -> str:
        best = FILES[0]
        for name, start in offsets:
            if index >= start:
                best = name
        return best

    total = 0

    print("=" * 76)
    print("一、make(...) 第三参直接含 <svg>")
    print("=" * 76)
    pattern1 = re.compile(
        r'make\(\s*"[a-z0-9]+"\s*,\s*"[^"]*"\s*,\s*([^;]{0,220}?<svg[^;]{0,220}?)\)\s*;',
        re.S,
    )
    seen: set[int] = set()
    for match in pattern1.finditer(js):
        line = js[: match.start()].count("\n") + 1
        seen.add(match.start())
        total += 1
        print(f"  [{where(match.start())} 行 {line}] " + " ".join(match.group(0).split())[:150])

    print()
    print("=" * 76)
    print("二、make(...) 第三参是变量，但该变量的赋值含 <svg>")
    print("=" * 76)
    # 找出含 <svg 的变量定义
    variables: dict[str, str] = {}
    for match in re.finditer(r"(\w+)\s*[:=]\s*'[^']*<svg[^']*'", js):
        variables[match.group(1)] = match.group(0)[:110]
    for name, snippet in variables.items():
        print(f"  变量 {name}：{snippet}")
        # 找使用它的 make() 调用
        for use in re.finditer(
            r'make\(\s*"[a-z0-9]+"\s*,\s*"[^"]*"\s*,\s*' + re.escape(name) + r'\b',
            js,
        ):
            line = js[: use.start()].count("\n") + 1
            total += 1
            print(f"    → 用于 make()：[{where(use.start())} 行 {line}] "
                  + " ".join(js[use.start(): use.start() + 90].split()))

    print()
    print("=" * 76)
    print("三、.textContent = 右侧含 <svg>")
    print("=" * 76)
    for match in re.finditer(r"\.textContent\s*=\s*[^;]{0,300}?<svg[^;]{0,200}?;", js):
        line = js[: match.start()].count("\n") + 1
        total += 1
        print(f"  [{where(match.start())} 行 {line}] " + " ".join(match.group(0).split())[:150])

    print()
    print("=" * 76)
    print(f"受影响调用点合计：{total} 处")
    print("=" * 76)
    print()
    print("建议修法：新增 makeIcon(symbolId, className) 用 createElementNS 建真实")
    print("svg/use 节点；make() 继续只处理纯文本。所有图标调用点改走 makeIcon。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
