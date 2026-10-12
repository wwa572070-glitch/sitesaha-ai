"""检查问答耗时瓶颈（第 20 轮 §2）。

看三件事：
  1. 生成参数（max_tokens / temperature）
  2. 问答 system prompt 有多长、约束有多繁
  3. 知识库上下文（top_k / max_context_chars）

用法：python inspect_ask_perf.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

APP = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(APP))


def main() -> int:
    llm = (APP / "sitesaha" / "llm.py").read_text(encoding="utf-8")
    config = (APP / "sitesaha" / "config.py").read_text(encoding="utf-8")
    rag = (APP / "sitesaha" / "rag.py").read_text(encoding="utf-8")

    print("=" * 78)
    print("一、生成参数")
    print("=" * 78)
    for match in re.finditer(r"[^\n]*(max_tokens|temperature|top_p)[^\n]*", llm):
        line = llm[: match.start()].count("\n") + 1
        print(f"  行 {line:>5}  {match.group(0).strip()[:110]}")

    print()
    print("=" * 78)
    print("二、配置默认值")
    print("=" * 78)
    for name in ("top_k", "max_context_chars", "llm_timeout_seconds",
                 "max_image_bytes", "request_timeout_seconds"):
        for match in re.finditer(rf"{name}\s*[:=]\s*([^,\n]+)", config):
            print(f"  {name:<26} {match.group(1).strip()[:40]}")

    print()
    print("=" * 78)
    print("三、问答 system prompt")
    print("=" * 78)
    # 找生成分支里的 system（不是视觉那个）
    index = llm.find("你是筑安智培")
    while index >= 0:
        # 往前找 system = """
        start = llm.rfind("system", 0, index)
        if start >= 0:
            end = llm.find('"""', index)
            if end > 0:
                body = llm[start:end]
                line = llm[:start].count("\n") + 1
                print(f"  --- 行 {line}，长度 {len(body)} 字符 ---")
                preview = body[:900].replace("\n", "\n      ")
                print(f"      {preview}")
                print()
        index = llm.find("你是筑安智培", index + 1)

    print()
    print("=" * 78)
    print("四、上下文拼装")
    print("=" * 78)
    for match in re.finditer(r"[^\n]*(max_context_chars|context_parts|used \+=)[^\n]*", llm):
        line = llm[: match.start()].count("\n") + 1
        print(f"  行 {line:>5}  {match.group(0).strip()[:110]}")

    print()
    print("=" * 78)
    print("五、rag 里传给模型的内容")
    print("=" * 78)
    for match in re.finditer(r"[^\n]*(generate\(|top_k=|sources\[)[^\n]*", rag):
        line = rag[: match.start()].count("\n") + 1
        print(f"  行 {line:>5}  {match.group(0).strip()[:110]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
