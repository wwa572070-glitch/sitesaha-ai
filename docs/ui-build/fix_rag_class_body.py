"""修复 rag.py 的类体被提前结束（第 16 轮，重复踩坑）。

事故：
  我把 _looks_like_table_fragment（0 缩进）插到了 class RAGEngine 的**中间**，
  提前结束了类体。于是它后面的 _extractive_answer（4 缩进）
  变成了这个模块级函数**内部嵌套的函数**，
  结果 RAGEngine 上再也没有 _extractive_answer，2 个测试报 AttributeError。

  这和之前 webapp.py 里 _answer_or_summary 那次是**同一类错误**。

修法：
  把该函数整段移出类体，放到 class RAGEngine 之前（模块级）。
  移走之后，_extractive_answer 的 4 空格缩进自然重新归属到类里。

断言（ast）：
  · _looks_like_table_fragment 在模块顶层
  · RAGEngine 拥有 _extractive_answer / answer / retrieve

用法：python fix_rag_class_body.py [--dry-run]
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
APP = BUILD.parent.parent
RAG = APP / "sitesaha" / "rag.py"

FUNC_HEAD = "def _looks_like_table_fragment(text: str) -> bool:"
CLASS_HEAD = "class RAGEngine"


def top_level_kinds(tree: ast.Module) -> dict[str, str]:
    kinds: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            kinds[node.name] = "module-func"
        elif isinstance(node, ast.ClassDef):
            kinds[node.name] = "class"
    return kinds


def methods_of(tree: ast.Module, class_name: str) -> list[str]:
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return [c.name for c in node.body if isinstance(c, ast.FunctionDef)]
    return []


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    text = RAG.read_text(encoding="utf-8")
    tree = ast.parse(text)

    kinds = top_level_kinds(tree)
    if kinds.get("_looks_like_table_fragment") == "module-func":
        methods = methods_of(tree, "RAGEngine")
        if "_extractive_answer" in methods:
            print("[跳过] 结构已正确")
            print("  RAGEngine 方法:", methods)
            return 0

    # 定位该函数节点，按行范围整段取出
    node = None
    for item in tree.body:
        if isinstance(item, ast.FunctionDef) and item.name == "_looks_like_table_fragment":
            node = item
            break
    if node is None:
        print("[FAIL] 找不到 _looks_like_table_fragment")
        return 1

    lines = text.split("\n")
    start = node.lineno - 1

    # 关键：不能用 node.end_lineno —— 因为 _extractive_answer 被嵌套在这个函数里，
    # end_lineno 会一路吃到文件末尾。改为找「下一个 4 空格缩进的 def」作为边界。
    end = None
    for index in range(node.lineno, len(lines)):
        line = lines[index]
        if line.startswith("    def "):
            end = index
            break
    if end is None:
        print("[FAIL] 找不到下一个方法的起点")
        return 1

    # 连同前导空行一起取走
    while start > 0 and not lines[start - 1].strip():
        start -= 1

    block = lines[start:end]
    print(f"[信息] 取出该函数 第 {node.lineno} 行 到 第 {end} 行（共 {len(block)} 行）")
    print(f"       下一行是: {lines[end].strip()[:70]}")

    rest = lines[:start] + lines[end:]

    # 插到 class RAGEngine 之前
    class_index = None
    for index, line in enumerate(rest):
        if line.startswith(CLASS_HEAD):
            class_index = index
            break
    if class_index is None:
        print("[FAIL] 找不到 class RAGEngine")
        return 1

    # 类前面通常有装饰器/注释，往上找到该段的起点
    insert_at = class_index
    while insert_at > 0 and rest[insert_at - 1].startswith("@"):
        insert_at -= 1

    merged = rest[:insert_at] + block + ["", ""] + rest[insert_at:]

    new_text = "\n".join(merged)
    try:
        new_tree = ast.parse(new_text)
    except SyntaxError as exc:
        print(f"[FAIL] 语法错误：{exc}")
        return 1
    print("[ok] 语法通过")

    # ---- 断言 ----
    new_kinds = top_level_kinds(new_tree)
    print()
    print("=== 断言 ===")
    ok = True
    if new_kinds.get("_looks_like_table_fragment") == "module-func":
        print("  [ok] _looks_like_table_fragment 在模块顶层")
    else:
        print(f"  [FAIL] 位置不对: {new_kinds.get('_looks_like_table_fragment')}")
        ok = False

    methods = methods_of(new_tree, "RAGEngine")
    for needed in ("answer", "retrieve", "_extractive_answer"):
        if needed in methods:
            print(f"  [ok] RAGEngine.{needed}")
        else:
            print(f"  [FAIL] RAGEngine 缺 {needed}")
            ok = False
    print(f"  RAGEngine 全部方法: {methods}")

    if not ok:
        return 1

    if args.dry_run:
        print("\n（dry-run，未写入）")
        return 0
    RAG.write_text(new_text, encoding="utf-8")
    print("\n[ok] 已写入")
    return 0


if __name__ == "__main__":
    sys.exit(main())
