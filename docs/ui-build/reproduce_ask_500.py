"""复现 /api/ask 的 500，抓真实异常（第 16 轮 §3.2 接线后回归）。

不做猜测：直接按 handler 的调用路径跑一遍，打印完整 traceback。

用法：python reproduce_ask_500.py
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

APP = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(APP))

import webapp  # noqa: E402


def main() -> int:
    print("=== 1) 直接跑 engine.answer ===")
    services = webapp.build_services()
    engine = services.engine
    answer = None
    try:
        answer = engine.answer("高处作业前要检查什么？", worker_role="", training_context="")
        print(f"  成功：{answer.text[:70]}")
        print(f"  mode={answer.mode} sources={len(answer.sources)} warnings={answer.warnings}")
    except Exception as exc:  # noqa: BLE001
        print(f"  失败：{type(exc).__name__}: {exc}")
        traceback.print_exc()

    print()
    print("=== 2) answer_payload ===")
    if answer is not None:
        try:
            print("  字段:", list(webapp.answer_payload("q", answer).keys()))
        except Exception as exc:  # noqa: BLE001
            print(f"  失败：{type(exc).__name__}: {exc}")
            traceback.print_exc()

    print()
    print("=== 3) summary_text ===")
    try:
        print("  成功:", webapp.summary_text("高处作业", [])[:70])
    except Exception as exc:  # noqa: BLE001
        print(f"  失败：{type(exc).__name__}: {exc}")
        traceback.print_exc()

    print()
    print("=== 4) 模拟 handler 的 _answer_or_summary ===")
    from sitesaha.models import Answer  # noqa: F401

    class FakeHandler:
        def __init__(self, services):  # noqa: ANN001
            self.services = services

        _answer_or_summary = webapp.SiteSahaHandler._answer_or_summary

    handler = FakeHandler(services)
    try:
        payload = handler._answer_or_summary("高处作业前要检查什么？", "", "")
        print("  成功，字段:", list(payload.keys()))
        print("  mode:", payload.get("mode"), " degraded:", payload.get("degraded"))
    except Exception as exc:  # noqa: BLE001
        print(f"  失败：{type(exc).__name__}: {exc}")
        traceback.print_exc()
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
