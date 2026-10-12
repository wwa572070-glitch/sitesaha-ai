"""清理回退答案里的页码残留（第 16 轮线上问题收尾）。

现象：过滤掉评分表碎片后，答案里还剩这种：
    4. 91
    起重吊装作业前应结合施工实际，编制专项施工方案……

那个 "91" 是标准 PDF 的页码，被 split_sentences 粘到了句子前面。

修法：在挑选候选句时，先剥掉开头的页码/编号残留。

用法：python fix_page_number_noise.py [--dry-run]
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
APP = BUILD.parent.parent
RAG = APP / "sitesaha" / "rag.py"

# 在过滤器里加一个「剥页码」函数
CLEANER = '''

def _strip_page_number(text: str) -> str:
    """剥掉粘在句子开头的页码或条目编号。

    标准 PDF 转文本后常见 "91\\n起重吊装作业前应…" 这种，
    页码会被并到句子里，显示成 "91 起重吊装作业前应…"。
    """
    if not text:
        return text
    # 开头是 1~4 位数字，后面紧跟非数字（说明是页码而不是内容里的数字）
    cleaned = re.sub(r"^\\s*\\d{1,4}\\s*[、.．)）]?\\s+(?=\\D)", "", text)
    # 纯页码行
    if re.fullmatch(r"\\s*\\d{1,4}\\s*", cleaned or ""):
        return ""
    return cleaned

'''

OLD = '''                # 剔除评分表碎片 —— 否则回退答案会把「扣10分」这类片段堆出来
                if _looks_like_table_fragment(sentence):
                    continue
                seen.add(normalized)
                selected.append((_sentence_score(sentence, units), sentence.strip(), source_index))'''

NEW = '''                # 剔除评分表碎片 —— 否则回退答案会把「扣10分」这类片段堆出来
                if _looks_like_table_fragment(sentence):
                    continue
                # 剥掉粘在句首的页码，如 "91 起重吊装作业前应…"
                cleaned = _strip_page_number(sentence).strip()
                if _looks_like_table_fragment(cleaned):
                    continue
                seen.add(normalized)
                selected.append((_sentence_score(cleaned, units), cleaned, source_index))'''

ANCHOR = "def _looks_like_table_fragment(text: str) -> bool:"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    text = RAG.read_text(encoding="utf-8")
    applied = 0

    if "_strip_page_number" not in text:
        if ANCHOR not in text:
            print("[FAIL] 找不到过滤器函数")
            return 1
        text = text.replace(ANCHOR, CLEANER.lstrip("\n") + "\n" + ANCHOR, 1)
        applied += 1
        print("[ok] 新增 _strip_page_number")
    else:
        print("[跳过] 已存在")

    if "剥掉粘在句首的页码" not in text:
        if OLD in text:
            text = text.replace(OLD, NEW, 1)
            applied += 1
            print("[ok] 句子挑选时先剥页码")
        else:
            print("[跳过] 锚点未匹配")
    else:
        print("[跳过] 已接入")

    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        print(f"[FAIL] 语法错误：{exc}")
        return 1
    print("[ok] 语法通过")

    # 断言：两个函数都在模块顶层，类方法没被破坏
    print()
    print("=== 断言 ===")
    ok = True
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in (
            "_looks_like_table_fragment", "_strip_page_number"
        ):
            print(f"  [ok] 模块级函数 {node.name}")
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "RAGEngine":
            methods = [c.name for c in node.body if isinstance(c, ast.FunctionDef)]
            print(f"  RAGEngine 方法: {methods}")
            for needed in ("answer", "retrieve", "_extractive_answer"):
                if needed not in methods:
                    print(f"  [FAIL] 缺 {needed}")
                    ok = False
            if ok:
                print("  [ok] 类方法完整")
    if not ok:
        return 1

    if args.dry_run:
        print(f"\n（dry-run，未写入；{applied} 处）")
        return 0
    RAG.write_text(text, encoding="utf-8")
    print(f"\n[ok] 已写入（{applied} 处）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
