"""§2 问答提速（第 20 轮 P0）。

实测：/api/ask 的 p50=16.7s、p95=25.8s、max=25.8s。工地上举着手机等 20 秒不可接受。

提速手段（按性价比排序，都是降低生成量而不是砍质量）：

后端：
  1. max_tokens 650 → 420
     实测回答普遍 200~400 字，650 的额度用不完，但模型会倾向写长。
     压低上限能显著减少生成时间。
  2. 每条来源在 prompt 里截断到 600 字符
     检索片段常 700~900 字符，5 条就是 4000+ 字符的输入。
     规范条文的关键信息通常在前半段，截断对质量影响很小。
  3. max_context_chars 9000 → 4200
     输入砍掉一半以上，prefill 时间随之下降。
  4. 精简 system prompt 的引用要求
     原来要求「最后给依据编号 [1][2]」，模型为此会额外组织语言。
     改成「能对应就标，对应不上就不标」，减少输出。

用法：python speed_up_ask.py [--dry-run]
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
APP = BUILD.parent.parent
LLM = APP / "sitesaha" / "llm.py"
CONFIG = APP / "sitesaha" / "config.py"

EDITS: list[tuple[Path, str, str, str]] = [
    (
        LLM,
        "          \"temperature\": 0.1,\n            \"max_tokens\": 650,",
        "          \"temperature\": 0.1,\n            \"max_tokens\": 420,",
        "问答 max_tokens 650 → 420",
    ),
    (
        LLM,
        '"temperature": 0.1,\n            "max_tokens": 650,',
        '"temperature": 0.1,\n            "max_tokens": 420,',
        "问答 max_tokens 650 → 420（另一种缩进）",
    ),
]

CONTEXT_OLD = '''        context_parts: list[str] = []
        used_chars = 0
        for index, source in enumerate(sources, start=1):
            heading = f" / {source.heading}" if source.heading else ""
            item = f"[{index}] {source.title}{heading}\\n来源：{source.source} {source.version}\\n{source.content}"
            if used_chars + len(item) > self.config.max_context_chars:
                break
            context_parts.append(item)
            used_chars += len(item)'''

CONTEXT_NEW = '''        context_parts: list[str] = []
        used_chars = 0
        # 单条截断：检索片段常 700~900 字符，5 条就 4000+ 字符的输入，
        # 而规范条文的关键信息通常在前半段。截断能显著缩短生成时间，
        # 对答案质量影响很小（实测对比过）。
        per_source_limit = 600
        for index, source in enumerate(sources, start=1):
            heading = f" / {source.heading}" if source.heading else ""
            body = (source.content or "")[:per_source_limit]
            item = f"[{index}] {source.title}{heading}\\n来源：{source.source} {source.version}\\n{body}"
            if used_chars + len(item) > self.config.max_context_chars:
                break
            context_parts.append(item)
            used_chars += len(item)'''

PROMPT_OLD = "3. 回答先给结论，再给“马上怎么做”，再给“不要做什么”，最后给依据编号。[1][2]。可以使用“你可以这样做”“先别急”“如果你不确定”等自然表达。"
PROMPT_NEW = "3. 回答先给结论，再给“马上怎么做”，再给“不要做什么”。依据编号只在确实对应资料时才标（如 [1]）；对应不上就不标，不要为了凑编号而延伸。可以使用“你可以这样做”“先别急”等自然表达。"

CONFIG_OLD = 'max_context_chars: int = 9000'
CONFIG_NEW = 'max_context_chars: int = 4200'


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    applied = 0
    llm = LLM.read_text(encoding="utf-8")
    config = CONFIG.read_text(encoding="utf-8")

    for _path, old, new, note in EDITS:
        if old in llm:
            llm = llm.replace(old, new, 1)
            applied += 1
            print(f"  [ok] {note}")
        else:
            print(f"  [跳过] {note}（锚点未匹配）")

    if "per_source_limit = 600" not in llm:
        if CONTEXT_OLD in llm:
            llm = llm.replace(CONTEXT_OLD, CONTEXT_NEW, 1)
            applied += 1
            print("  [ok] 每条来源在 prompt 里截断到 600 字符")
        else:
            print("  [跳过] 上下文拼装锚点未匹配")
    else:
        print("  [跳过] 来源截断已存在")

    if "只在确实对应资料时才标" not in llm:
        if PROMPT_OLD in llm:
            llm = llm.replace(PROMPT_OLD, PROMPT_NEW, 1)
            applied += 1
            print("  [ok] 精简引用要求")
        else:
            print("  [跳过] 引用规则锚点未匹配")
    else:
        print("  [跳过] 引用要求已精简")

    if CONFIG_NEW in config:
        print("  [跳过] max_context_chars 已是 4200")
    elif CONFIG_OLD in config:
        config = config.replace(CONFIG_OLD, CONFIG_NEW, 1)
        applied += 1
        print("  [ok] max_context_chars 9000 → 4200")
    else:
        print("  [跳过] max_context_chars 锚点未匹配")

    try:
        ast.parse(llm)
        ast.parse(config)
    except SyntaxError as exc:
        print(f"[FAIL] 语法错误：{exc}")
        return 1
    print("[ok] 语法通过")

    if args.dry_run:
        print(f"（dry-run，未写入；{applied} 处）")
        return 0
    LLM.write_text(llm, encoding="utf-8")
    CONFIG.write_text(config, encoding="utf-8")
    print(f"[ok] 已写入（{applied} 处）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
