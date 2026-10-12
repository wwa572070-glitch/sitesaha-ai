"""实测问答提速效果（第 20 轮 §2）。

跑若干问题，记录耗时、答案长度、上下文大小。

用法：python bench_ask_speed.py
"""

from __future__ import annotations

import statistics
import sys
import time
from pathlib import Path

APP = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(APP))

import webapp  # noqa: E402

QUESTIONS = [
    "高处作业前要检查什么？",
    "我没有挂安全带",
    "基坑出现裂缝和渗水怎么处理？",
    "动火作业前要做哪些确认？",
    "配电箱进水怎么办？",
]


def main() -> int:
    services = webapp.build_services()
    engine = services.engine
    config = services.config

    print("=" * 78)
    print("当前配置")
    print("=" * 78)
    print(f"  max_context_chars  {config.max_context_chars}")
    print(f"  top_k              {config.top_k}")
    print(f"  llm_timeout        {config.llm_timeout_seconds}s")
    print()

    times: list[float] = []
    lengths: list[int] = []

    print("=" * 78)
    print("逐个提问计时")
    print("=" * 78)
    for question in QUESTIONS:
        started = time.time()
        answer = engine.answer(question, worker_role="", training_context="")
        elapsed = time.time() - started
        times.append(elapsed)
        lengths.append(len(answer.text))
        flag = "" if elapsed < 15 else "  ← 超过 15s"
        print(f"  {elapsed:>5.1f}s  {answer.mode:<11} {len(answer.text):>4} 字  {question[:22]}{flag}")

    print()
    print("=" * 78)
    print("统计")
    print("=" * 78)
    if times:
        print(f"  平均   {statistics.mean(times):.1f}s")
        print(f"  中位   {statistics.median(times):.1f}s")
        print(f"  最快   {min(times):.1f}s")
        print(f"  最慢   {max(times):.1f}s")
        print(f"  答案平均 {int(statistics.mean(lengths))} 字")
    print()
    print("  目标：<15s（理想 <10s）")
    ok = times and statistics.median(times) < 15
    print(f"  结论: {'达标' if ok else '未达标'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
