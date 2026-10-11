"""把学习动作写进活动记录，供热力格使用（第 16 轮 §7 收尾）。

没有这一步，热力格会永远是空的 —— 它是「近 7 天学习记录」，
必须有写入点才有数据。

挂三个点（都是用户真实完成学习动作的时刻）：
  1. 完成一次测验
  2. 勾选一个培训步骤（取消不记）
  3. 勾选一个班前确认项（取消不记）

原则：只在"做成了一件事"时记一次，不在页面加载时记，
否则热力格会变成"打开过页面"的记录，没有意义。

注意：分片里每行之间有空行，锚点必须按空行格式给出。

用法：python hook_activity_log.py [--dry-run]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
SCRIPT_A = BUILD / "index_script_a.js"
SCRIPT_B = BUILD / "index_script_b.js"


def blank(text: str) -> str:
    """把普通多行文本转成分片风格（行间插空行）。"""
    return "\n\n".join(text.split("\n"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    edits = [
        (
            SCRIPT_A,
            "完成一次测验",
            blank('writeStore(QUIZ_KEY, record); var host = clear($("quizResult"));'),
            blank('writeStore(QUIZ_KEY, record); logActivity(); var host = clear($("quizResult"));'),
        ),
        (
            SCRIPT_A,
            "勾选培训步骤",
            blank('writeStore("sitesaha-steps-v1", state);'),
            blank('writeStore("sitesaha-steps-v1", state); if (box.checked) logActivity();'),
        ),
        (
            SCRIPT_B,
            "勾选班前确认项",
            blank('writeStore(CHECKLIST_KEY, current);'),
            blank('writeStore(CHECKLIST_KEY, current); if (box.checked) logActivity();'),
        ),
    ]

    cache: dict[Path, str] = {}
    for path in (SCRIPT_A, SCRIPT_B):
        cache[path] = path.read_text(encoding="utf-8")

    applied = 0
    for path, note, old, new in edits:
        text = cache[path]
        if old not in text:
            print(f"  [跳过] {note}（锚点未匹配）")
            continue
        if new in text:
            print(f"  [跳过] {note}（已挂钩）")
            continue
        cache[path] = text.replace(old, new, 1)
        applied += 1
        print(f"  [ok] {note}")

    if "function logActivity" not in cache[SCRIPT_A]:
        print("[WARN] script_a 里没有 logActivity 定义")
    else:
        print("[ok] logActivity 定义在 script_a")

    for path, text in cache.items():
        if text.count(chr(92)):
            print(f"[FAIL] {path.name} 含反斜杠")
            return 1
    print("[ok] 无反斜杠")

    if args.dry_run:
        print(f"（dry-run，未写入；{applied} 处）")
        return 0

    for path, text in cache.items():
        path.write_text(text, encoding="utf-8")
    print(f"[ok] 已写入（{applied} 处）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
