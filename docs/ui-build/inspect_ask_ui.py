"""检查问答提交与等待气泡（第 20 轮 §2 前端部分）。

用法：python inspect_ask_ui.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
SCRIPT_B = BUILD / "index_script_b.js"


def main() -> int:
    text = SCRIPT_B.read_text(encoding="utf-8")

    print("=" * 78)
    print("一、等待气泡 chatThinking")
    print("=" * 78)
    for match in re.finditer(r"[^\n]*chatThinking[^\n]*", text):
        line = text[: match.start()].count("\n") + 1
        print(f"  行 {line:>5}  {match.group(0).strip()[:150]}")

    print()
    print("=" * 78)
    print("二、提交函数")
    print("=" * 78)
    for name in ("submitQuestion", "askQuestion", "function ask", "askButton"):
        index = text.find(name)
        if index < 0:
            continue
        line = text[:index].count("\n") + 1
        print(f"  {name}: 行 {line}")

    # 找 askButton 的监听
    index = text.find('"askButton"')
    if index >= 0:
        start = text.rfind("function", 0, index)
        line = text[:start].count("\n") + 1
        print()
        print(f"=== askButton 所在函数（行 {line}）===")
        print(text[start : start + 2200])
    return 0


if __name__ == "__main__":
    sys.exit(main())
