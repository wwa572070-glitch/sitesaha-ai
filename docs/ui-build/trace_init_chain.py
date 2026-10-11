"""追踪 DOM 模拟里 init() 的执行链，定位为什么没请求 /api/status。"""

from __future__ import annotations

import re
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
A = (BUILD / "index_script_a.js").read_text(encoding="utf-8")
B = (BUILD / "index_script_b.js").read_text(encoding="utf-8")


def show(label: str, text: str, pattern: str, width: int = 700) -> None:
    print(f"=== {label} ===")
    hits = list(re.finditer(pattern, text))
    if not hits:
        print("  （未找到）")
    for match in hits[:4]:
        line = text[: match.start()].count("\n") + 1
        print(f"  [script_{'a' if text is A else 'b'}] 第 {line} 行")
        print("    " + " ".join(text[max(0, match.start() - 60): match.start() + width].split())[:width])
    print()


def main() -> int:
    js = A + B
    show("getJson 定义", js, r"function getJson|getJson\s*=")
    show("loadStatus 定义与调用", js, r"loadStatus")
    show("init 函数与调用", js, r"function init\s*\(|init\(\)")
    show("fetch 的实际调用形式", js, r"fetch\(")
    print("=== 脚本里出现的 fetch 调用（逐处）===")
    for match in re.finditer(r"fetch\(", js):
        line = js[: match.start()].count("\n") + 1
        snippet = " ".join(js[match.start(): match.start() + 110].split())
        print(f"  第 {line} 行: {snippet[:110]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
