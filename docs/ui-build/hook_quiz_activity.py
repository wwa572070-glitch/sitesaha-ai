"""补上"完成一次测验"的活动记录挂钩（第 16 轮 §7 收尾）。

前两个钩子（培训步骤、班前确认）已生效，这个因为锚点跨空行没匹配。
按实际内容精确给出锚点。

用法：python hook_quiz_activity.py
"""

from __future__ import annotations

import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
SCRIPT_A = BUILD / "index_script_a.js"

QUOTE = chr(34)


def main() -> int:
    text = SCRIPT_A.read_text(encoding="utf-8")

    old = (
        "writeStore(QUIZ_KEY, record);"
        + "\n\n      var host = clear($(" + QUOTE + "quizResult" + QUOTE + "));"
    )
    new = (
        "writeStore(QUIZ_KEY, record);"
        + "\n\n      logActivity();"
        + "\n\n      var host = clear($(" + QUOTE + "quizResult" + QUOTE + "));"
    )

    if new in text:
        print("[跳过] 已挂钩")
        return 0
    if old not in text:
        print("[FAIL] 锚点未匹配")
        return 1

    text = text.replace(old, new, 1)
    if text.count(chr(92)):
        print("[FAIL] 引入反斜杠")
        return 1
    SCRIPT_A.write_text(text, encoding="utf-8")
    print("[ok] 完成一次测验已挂钩")
    print(f"[复核] logActivity() 调用共 {text.count('logActivity()')} 处")
    return 0


if __name__ == "__main__":
    sys.exit(main())
