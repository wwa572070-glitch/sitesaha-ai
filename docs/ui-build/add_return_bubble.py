"""让 appendAnswer 返回气泡（第 20 轮 §2，位置法）。

三次字符串锚点都失败（分片空行数量不一致），改用「askQuestion 前那个右花括号」
作为定位点 —— 它必然属于 appendAnswer，因为两者紧邻。

用法：python add_return_bubble.py [--dry-run]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
SCRIPT_B = BUILD / "index_script_b.js"

# appendAnswer 的结尾右花括号紧跟在 askQuestion 之前
MARKER = "    }\n\n\n\n    async function askQuestion() {"
REPLACEMENT = (
    "      /* 返回气泡，便于调用方追加内容（如超时后的重试按钮） */\n"
    "      return bubble;\n"
    "\n"
    "    }\n"
    "\n"
    "\n"
    "\n"
    "    async function askQuestion() {"
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    text = SCRIPT_B.read_text(encoding="utf-8")

    if "return bubble;" in text:
        print("[跳过] 已返回 bubble")
        return 0

    count = text.count(MARKER)
    print(f"[信息] 定位标记出现 {count} 次")
    if count != 1:
        print("[FAIL] 标记不唯一或找不到，中止以免改错位置")
        return 1

    text = text.replace(MARKER, REPLACEMENT, 1)
    print("[ok] appendAnswer 已返回 bubble")

    # 复核：askQuestion 仍在
    if "async function askQuestion() {" not in text:
        print("[FAIL] askQuestion 不见了")
        return 1
    if text.count(chr(92)):
        print("[FAIL] 含反斜杠")
        return 1
    print("[ok] 结构完好，无反斜杠")

    if args.dry_run:
        print("（dry-run，未写入）")
        return 0
    SCRIPT_B.write_text(text, encoding="utf-8")
    print("[ok] 已写入")
    return 0


if __name__ == "__main__":
    sys.exit(main())
