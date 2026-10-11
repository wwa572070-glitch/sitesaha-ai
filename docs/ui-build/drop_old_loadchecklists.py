"""删掉旧的 loadChecklists 与重复的 updateCheckProgress（第 16 轮 §11 前端）。

问题：
  §11 前端新增了 renderChecklist() / updateCheckProgress(total)，
  但旧实现还在：
    · loadChecklists()      —— 拉 /api/checklists 渲染 priority_checks，
                               并在 init 里被调用，覆盖我的分组渲染
    · updateCheckProgress() —— 旧版没有参数，查了一个不存在的
                               #checklist 容器，导致进度永远显示 0 / 7

  两个同名函数，后定义者胜 —— 结果我的渲染被旧的盖掉。

修法：删掉旧的 loadChecklists 整个函数 + init 里的调用；
     删掉旧的 updateCheckProgress（保留新版带 total 参数的）。
     保留 inspectionChecks（检查项目索引面板）的渲染。

用法：python drop_old_loadchecklists.py [--dry-run]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
SCRIPT_B = BUILD / "index_script_b.js"


def find_function(text: str, header: str) -> tuple[int, int] | None:
    """找到 header 开始的函数范围 [start, end)，按大括号配对。"""
    start = text.find(header)
    if start < 0:
        return None
    # 往前吃掉缩进
    start = text.rfind("\n", 0, start) + 1
    brace = text.find("{", start)
    if brace < 0:
        return None
    depth = 0
    index = brace
    while index < len(text):
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return start, index + 1
        index += 1
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    text = SCRIPT_B.read_text(encoding="utf-8")
    changed = 0

    # ---- 1) 删旧的 loadChecklists ----
    span = find_function(text, "async function loadChecklists()")
    if span:
        start, end = span
        removed = text[start:end]
        text = text[:start] + text[end:]
        changed += 1
        print(f"[ok] 删除旧 loadChecklists（{len(removed)} 字符）")
    else:
        print("[跳过] 未找到旧 loadChecklists")

    # ---- 2) 删 init 里的调用 ----
    call = "await loadChecklists();"
    if call in text:
        text = text.replace(call, "/* 清单由 initPrePanels 生成 */", 1)
        changed += 1
        print("[ok] 移除 init 里的 loadChecklists 调用")
    else:
        print("[跳过] 未找到调用点")

    # ---- 3) 删旧的 updateCheckProgress（无参数的版本）----
    span2 = find_function(text, "function updateCheckProgress()")
    if span2:
        start, end = span2
        removed = text[start:end]
        text = text[:start] + text[end:]
        changed += 1
        print(f"[ok] 删除旧 updateCheckProgress（{len(removed)} 字符）")
    else:
        print("[跳过] 未找到旧 updateCheckProgress")

    # ---- 复核 ----
    print()
    for name in ("loadChecklists", "function updateCheckProgress"):
        print(f"  [复核] {name} 出现 {text.count(name)} 次")

    if text.count(chr(92)):
        print("[FAIL] 引入反斜杠")
        return 1
    print("[ok] 无反斜杠")

    if args.dry_run:
        print(f"（dry-run，未写入；{changed} 处）")
        return 0
    SCRIPT_B.write_text(text, encoding="utf-8")
    print(f"[ok] 已写入（{changed} 处）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
