"""修正 _answer_or_summary 的缩进（用 ast 精确定位，不靠字符串猜测）。

事故：
  用 PowerShell 内联命令插入这个方法时缩进被剥掉，它以 0 缩进写在模块顶层，
  等于提前结束了 class SiteSahaHandler 的类体 —— 其后的 do_POST（含
  /api/transcribe 路由）全被吞进这个函数，导致语音接口 500、/api/ask 找不到方法。

教训：ast.parse 只验证语法，缩进错位是**合法 Python**。
      必须额外验证「方法确实挂在预期的类上」。

本版用 ast 拿到该函数节点的精确行范围，只缩进这一段。

用法：python fix_helper_indent2.py [--dry-run]
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
APP = BUILD.parent.parent
WEBAPP = APP / "webapp.py"
TARGET = "_answer_or_summary"


def top_level_owner(tree: ast.Module, name: str) -> str | None:
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return "<module>"
        if isinstance(node, ast.ClassDef):
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name == name:
                    return node.name
    return None


def class_methods(tree: ast.Module, class_name: str) -> set[str]:
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return {c.name for c in node.body
                    if isinstance(c, (ast.FunctionDef, ast.AsyncFunctionDef))}
    return set()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    source = WEBAPP.read_text(encoding="utf-8")
    lines = source.split("\n")
    tree = ast.parse(source)

    owner = top_level_owner(tree, TARGET)
    print(f"[信息] 当前宿主：{owner!r}")
    if owner == "SiteSahaHandler":
        print("[跳过] 已挂在 SiteSahaHandler 上，无需修正")
        return 0
    if owner is None:
        print("[FAIL] 文件里找不到这个函数")
        return 1

    # 用 ast 拿到精确行范围
    node = None
    for item in tree.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == TARGET:
            node = item
            break
    if node is None:
        print("[FAIL] 无法定位节点")
        return 1

    first = node.lineno - 1
    last = node.end_lineno  # 不含，转成 0 基后正好是 end_lineno
    print(f"[信息] 行范围 {node.lineno} ~ {node.end_lineno}（共 {last - first} 行）")
    print(f"[信息] 首行：{lines[first][:70]!r}")

    # 只缩进这一段
    block = lines[first:last]
    fixed = [("    " + line) if line.strip() else line for line in block]
    new_lines = lines[:first] + fixed + lines[last:]
    new_source = "\n".join(new_lines)

    try:
        new_tree = ast.parse(new_source)
    except SyntaxError as exc:
        print(f"[FAIL] 语法错误：{exc}")
        return 1
    print("[ok] 语法通过")

    new_owner = top_level_owner(new_tree, TARGET)
    print(f"[信息] 修正后宿主：{new_owner!r}")
    if new_owner != "SiteSahaHandler":
        print(f"[FAIL] 断言未通过：宿主应为 'SiteSahaHandler'")
        return 1
    print("[ok] 断言通过：_answer_or_summary 挂回 SiteSahaHandler")

    methods = class_methods(new_tree, "SiteSahaHandler")
    all_ok = True
    for needed in ("do_GET", "do_POST", "_answer_or_summary", "_write_provider_error"):
        ok = needed in methods
        all_ok = all_ok and ok
        print(f"  [{'ok' if ok else 'FAIL'}] SiteSahaHandler.{needed}")
    if not all_ok:
        print("[FAIL] 类方法不齐")
        return 1

    if args.dry_run:
        print("（dry-run，未写入）")
        return 0
    WEBAPP.write_text(new_source, encoding="utf-8")
    print("[ok] 已写入")
    return 0


if __name__ == "__main__":
    sys.exit(main())
