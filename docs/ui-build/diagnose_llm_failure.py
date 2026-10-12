"""复现线上「在线模型生成失败」并抓出真实异常（第 16 轮线上问题排查）。

线上现象：问「我没有挂安全带」时，回答退化成检索摘要，
warnings 里只有 "在线模型生成失败，已回退到检索摘要：ProviderError" ——
真实错误信息被 rag.py 丢掉了，所以看不到原因。

本脚本直接调本地引擎，把完整异常打出来。

用法：python diagnose_llm_failure.py
"""

from __future__ import annotations

import sys
import time
import traceback
from pathlib import Path

APP = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(APP))

import webapp  # noqa: E402

QUESTIONS = [
    "我没有挂安全带",
    "工地上不挂安全带",
    "安全带怎么用",
    "高处作业前要检查什么？",
]


def main() -> int:
    services = webapp.build_services()
    engine = services.engine
    config = services.config

    print("=" * 78)
    print("配置")
    print("=" * 78)
    print(f"  llm_mode        {config.llm_mode}")
    print(f"  llm_base_url    {config.llm_base_url}")
    print(f"  llm_model       {config.llm_model}")
    print(f"  llm_timeout     {config.llm_timeout_seconds}s")
    print(f"  top_k           {config.top_k}")
    print(f"  max_context     {config.max_context_chars} 字符")

    for question in QUESTIONS:
        print()
        print("=" * 78)
        print(f"问题：{question}")
        print("=" * 78)

        sources = engine.retriever.search(
            question, top_k=config.top_k, worker_role=""
        )
        total = sum(len(s.content or "") for s in sources)
        print(f"  检索 {len(sources)} 条来源，正文合计 {total} 字符")
        for index, source in enumerate(sources[:3], 1):
            heading = (source.heading or "")[:28]
            print(f"    [{index}] {source.title[:38]} / {heading} "
                  f"长度 {len(source.content or '')}")

        started = time.time()
        try:
            text = engine.model.generate(
                question, sources, mode="一般/绿色风险",
                worker_role="", training_context="",
            )
            elapsed = time.time() - started
            print(f"  [成功] {elapsed:.1f}s  长度 {len(text)}")
            print(f"  前 160 字: {text[:160]}")
        except Exception as exc:  # noqa: BLE001
            elapsed = time.time() - started
            print(f"  [失败] {elapsed:.1f}s")
            print(f"  类型: {type(exc).__name__}")
            print(f"  消息: {str(exc)[:500]}")
            for attribute in ("code", "http_status", "hint", "retryable", "raw"):
                if hasattr(exc, attribute):
                    value = getattr(exc, attribute)
                    print(f"  {attribute}: {str(value)[:400]}")
            print()
            traceback.print_exc()
    return 0


if __name__ == "__main__":
    sys.exit(main())
