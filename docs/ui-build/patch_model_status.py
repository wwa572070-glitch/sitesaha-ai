"""补上 modelStatus 的语义修正（锚点跨空行）。

上一版锚点没按分片的空行格式给出，所以跳过了。
分片风格：每行之间有一个空行。

用法：python patch_model_status.py [--dry-run]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
SCRIPT_B = BUILD / "index_script_b.js"

NEEDLE = 'var pill = $("modelStatus");'


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    text = SCRIPT_B.read_text(encoding="utf-8")
    if "未连接模型 · 当前为检索摘要" in text:
        print("[跳过] 已修正")
        return 0

    # 用正则跨空行匹配整段 if (pill) { ... }
    pattern = re.compile(
        re.escape('var pill = $("modelStatus");')
        + r"\s*if \(pill\) \{.*?\}",
        re.S,
    )
    match = pattern.search(text)
    if not match:
        print("[FAIL] 找不到 modelStatus 赋值段")
        return 1

    print(f"[信息] 命中 {len(match.group(0))} 字符")
    print(f"  原文：{' '.join(match.group(0).split())[:150]}")

    replacement = (
        'var pill = $("modelStatus");\n\n'
        "        /* 语义修正（§5 第 5 条）：这不是功能标签，而是模型没连上的降级状态。\n"
        "           模型可用时退场，不占位；不可用时说清影响与下一步。 */\n\n"
        "        if (model.available) {\n\n"
        "          pill.hidden = true;\n\n"
        '          pill.textContent = "";\n\n'
        '          pill.classList.remove("offline");\n\n'
        "        } else {\n\n"
        "          pill.hidden = false;\n\n"
        '          pill.textContent = "未连接模型 · 当前为检索摘要";\n\n'
        '          pill.classList.add("offline");\n\n'
        '          pill.title = (model.detail || "未配置模型服务地址")\n\n'
        '            + "；检索摘要仍可用，成段解释需管理员配置 SITESHAHA_LLM_*";\n\n'
        "        }\n"
    )
    text = text[: match.start()] + replacement + text[match.end():]

    if text.count(chr(92)):
        print("[FAIL] 引入反斜杠")
        return 1

    if args.dry_run:
        print("（dry-run，未写入）")
        return 0
    SCRIPT_B.write_text(text, encoding="utf-8")
    print("[ok] modelStatus 语义已修正")
    return 0


if __name__ == "__main__":
    sys.exit(main())
