"""把「退化图拒收」块从语音分支移到视觉分支（正确缩进）。

现状（实测缩进）：
  11801 [12]             # ---- §4 硬闸：退化图不送模型 ----
  11804 [12]             width, height, image_format = image_geometry(image_bytes)

12 空格 = if path == "/api/transcribe" 的分支体 → 语音一进来就执行，
image_bytes 在该作用域不存在 → UnboundLocalError → 500。

视觉分支体是 16 空格。本脚本按行范围把整块从 12 格重缩进到 16 格，
并断言：
  · image_geometry 调用行变成 16 格缩进
  · 它前面最近的 `if path ==` 是 /api/inspect-image

前两次的锚点都误匹配到 transcribe，所以这次不靠锚点 —— 直接按行号范围操作。

用法：python fix_gate_indent.py [--dry-run]
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
APP = BUILD.parent.parent
WEBAPP = APP / "webapp.py"

MARK = "            # ---- §4 硬闸：退化图不送模型 ----"
END_MARK = "                return"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    lines = WEBAPP.read_text(encoding="utf-8").split("\n")

    start = None
    for index, line in enumerate(lines):
        if line == MARK:
            start = index
            break
    if start is None:
        print("[跳过] 找不到拒收块（可能已修正或已移除）")
        return 0

    indent_before = len(lines[start]) - len(lines[start].lstrip())
    print(f"[信息] 块起始行 {start + 1}，缩进 {indent_before} 格")

    # 找结束：块内第一个 "return" 且缩进 <= 起始缩进 + 4
    end = None
    for index in range(start + 1, min(start + 60, len(lines))):
        stripped = lines[index].strip()
        indent = len(lines[index]) - len(lines[index].lstrip())
        if stripped == "return" and indent <= indent_before + 4:
            end = index
            break
    if end is None:
        print("[FAIL] 找不到块结束位置")
        return 1
    print(f"[信息] 块结束行 {end + 1}（共 {end - start + 1} 行）")

    # 判定归属必须看**缩进**，不能看文本位置 —— 这正是前两次误判的原因：
    # 块在文本上排在 inspect-image 之后，但 12 格缩进让它归属 transcribe 分支。
    # 各分支体缩进：if path == 是 12 格，其分支体是 16 格。
    branch_indent = 16
    if indent_before == branch_indent:
        print(f"[跳过] 缩进已是 {branch_indent} 格，位于分支体内")
        return 0
    print(f"[信息] 缩进 {indent_before} 格 ≠ 分支体应有的 {branch_indent} 格，需要修正")

    shift = branch_indent - indent_before
    for index in range(start, end + 1):
        if lines[index].strip():
            lines[index] = " " * shift + lines[index]

    new_source = "\n".join(lines)
    try:
        ast.parse(new_source)
    except SyntaxError as exc:
        print(f"[FAIL] 语法错误：{exc}")
        return 1
    print("[ok] 语法通过")

    # 断言：重缩进后 image_geometry 调用行缩进为 16，且前面最近路由正确
    check_lines = new_source.split("\n")
    for index, line in enumerate(check_lines):
        if "image_geometry(image_bytes)" in line:
            indent = len(line) - len(line.lstrip())
            print(f"[信息] image_geometry 行缩进 {indent} 格")
            if indent != 16:
                print("[FAIL] 缩进不是 16 格")
                return 1
            nearest2 = None
            for back in range(index, -1, -1):
                if "if path ==" in check_lines[back]:
                    nearest2 = check_lines[back].strip()
                    break
            print(f"[信息] 重缩进后前面最近路由：{nearest2}")
            if "/api/inspect-image" not in (nearest2 or ""):
                print("[FAIL] 仍不在视觉分支内")
                return 1
    print("[ok] 断言通过：拒收块位于 /api/inspect-image 分支内")

    if args.dry_run:
        print("（dry-run，未写入）")
        return 0
    WEBAPP.write_text(new_source, encoding="utf-8")
    print("[ok] 已写入")
    return 0


if __name__ == "__main__":
    sys.exit(main())
