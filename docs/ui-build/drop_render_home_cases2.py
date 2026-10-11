"""删除 index_script_a.js 里的 renderHomeCases（旧实现，目标 id 已不存在）。

上一版改错了文件（去 index_script_b.js 找，实际定义在 a）。
同时 learn 页已无「每日警示案例」块，这个函数没有任何消费者。

用法：python drop_render_home_cases2.py [--dry-run]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
SCRIPT_A = BUILD / "index_script_a.js"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    text = SCRIPT_A.read_text(encoding="utf-8")
    start = text.find("function renderHomeCases")
    if start < 0:
        print("[跳过] 未找到 renderHomeCases")
        return 0

    line_start = text.rfind("\n", 0, start) + 1
    # 函数结束：下一个同级缩进的 function
    nxt = text.find("\n    function ", start + 10)
    if nxt < 0:
        # 可能是块中最后一个函数，找收尾
        nxt = text.find("\n  })();", start)
        if nxt < 0:
            print("[FAIL] 找不到函数结束位置")
            return 1

    removed = text[line_start:nxt]
    print(f"[信息] 将删除 {len(removed)} 字符")
    print(f"  预览：{' '.join(removed.split())[:130]}")

    text = text[:line_start] + text[nxt + 1:]
    leftover = text.count("renderHomeCases") + text.count("homeCaseGrid")
    print(f"[复核] 残留引用 {leftover} 处")

    if text.count(chr(92)):
        print("[FAIL] 引入反斜杠")
        return 1

    if args.dry_run:
        print("（dry-run，未写入）")
        return 0
    SCRIPT_A.write_text(text, encoding="utf-8")
    print("[ok] index_script_a.js 已更新")
    return 0


if __name__ == "__main__":
    sys.exit(main())
