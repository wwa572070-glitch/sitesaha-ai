"""逼出一次回退，验证修复后的告警格式（第 16 轮线上部署验证）。

为什么要这么做：版本号没变，光靠「模型成功」不能证明新代码上线了
（可能是旧代码碰巧没失败）。

做法：连续快速提问，制造免费模型的限流，逼出回退路径。
然后看告警格式：
  旧：在线模型生成失败，已回退到检索摘要：ProviderError          ← 只有类名
  新：在线模型生成失败，已回退到检索摘要（ProviderError/xxx：原因）  ← 带原因
同时检查回退答案里有没有评分表碎片。

用法：python burst_test_fallback.py
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request

BASE = "https://sitesaha-ai-v16.onrender.com"

QUESTIONS = [
    "我没有挂安全带",
    "脚手架搭拆要注意什么",
    "基坑出现裂缝怎么办",
    "动火作业前要做什么",
    "配电箱进水怎么处理",
    "高处作业要检查什么",
    "吊装时哪里不能站人",
    "临边洞口防护要求",
]

BAD_MARKERS = ["扣10", "扣6", "扣5", "扣8", "扣4", "扣2", "扣1", "应得", "实得"]


def ask(question: str, timeout: int = 180):
    request = urllib.request.Request(
        BASE + "/api/ask",
        data=json.dumps({"question": question}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.time()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, json.loads(response.read().decode("utf-8")), time.time() - started
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")[:200], time.time() - started
    except Exception as exc:  # noqa: BLE001
        return 0, f"{type(exc).__name__}: {exc}", time.time() - started


def main() -> int:
    print("=" * 76)
    print("连续提问，逼出回退路径")
    print("=" * 76)

    fallback_seen = False
    new_format_seen = False
    fragments_found: list[str] = []

    for index, question in enumerate(QUESTIONS, 1):
        status, data, elapsed = ask(question)
        if not isinstance(data, dict):
            print(f"  [{index}] {question[:16]:<18} HTTP {status}  {str(data)[:70]}")
            continue

        mode = data.get("mode")
        warnings = data.get("warnings") or []
        text = data.get("text") or ""
        fallback = [w for w in warnings if "在线模型生成失败" in w]

        tag = "回退" if fallback else "正常"
        print(f"  [{index}] {question[:16]:<18} {mode:<10} {tag:<4} {elapsed:>5.1f}s  长度 {len(text)}")

        if fallback:
            fallback_seen = True
            message = fallback[0]
            print(f"        告警: {message[:130]}")
            if "（" in message:
                new_format_seen = True
                print("        → 这是**修复后**的格式 ✅")
            else:
                print("        → 这是**修复前**的格式（部署可能还没完成）")

            hits = [m for m in BAD_MARKERS if m in text]
            if hits:
                fragments_found.extend(hits)
                print(f"        → 答案里仍有评分碎片: {set(hits)} ❌")
            else:
                print("        → 答案里没有评分碎片 ✅")
            print()
            print("        ---- 回退答案全文 ----")
            for line in text.split("\n"):
                print("        " + line)
            print()

    print("=" * 76)
    print("结果")
    print("=" * 76)
    print(f"  触发过回退        : {fallback_seen}")
    print(f"  见到新告警格式    : {new_format_seen}")
    print(f"  回退答案里的碎片  : {set(fragments_found) if fragments_found else '无'}")

    if not fallback_seen:
        print()
        print("  说明：这轮没有触发回退（模型都成功了）——这本身是好消息，")
        print("        但无法据此确认新代码已上线。可以稍后再跑一次。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
