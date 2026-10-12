"""复现线上「乱码」并判断部署的是旧代码还是新代码（第 16 轮线上反馈）。

判断依据：
  旧代码的回退告警：在线模型生成失败，已回退到检索摘要：ProviderError
  新代码的回退告警：在线模型生成失败，已回退到检索摘要（ProviderError/xxx：原因）

用法：python check_live_garbage.py
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request

BASE = "https://sitesaha-ai-v16.onrender.com"

# 用户反馈会出问题的问法，以及几个变体
QUESTIONS = [
    "我没有挂安全带",
    "我没有带安全帽",
    "我没有挂安全带怎么办",
    "工地不戴安全帽",
    "高处作业不系安全带",
]

BAD_MARKERS = ["扣10", "扣6", "扣5", "扣8", "扣4", "扣2", "应得", "实得", "扣 10"]


def ask(question: str, timeout: int = 200):
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
    deploy_verdict = "unknown"

    for question in QUESTIONS:
        print("=" * 78)
        print(f"问：{question}")
        print("=" * 78)
        status, data, elapsed = ask(question)
        print(f"  HTTP {status}  耗时 {elapsed:.1f}s")

        if not isinstance(data, dict):
            print(f"  {str(data)[:200]}")
            print()
            continue

        mode = data.get("mode")
        warnings = data.get("warnings") or []
        text = data.get("text") or ""
        print(f"  mode = {mode}")
        print(f"  warnings = {warnings}")
        print(f"  答案长度 = {len(text)}")

        fallback = [w for w in warnings if "在线模型生成失败" in w]
        if fallback:
            message = fallback[0]
            if "（" in message:
                deploy_verdict = "new"
                print("  >>> 这是【新代码】的回退格式（带真实原因）")
            else:
                deploy_verdict = "old"
                print("  >>> 这是【旧代码】的回退格式（只有异常类名）")

        hits = [m for m in BAD_MARKERS if m in text]
        if hits:
            print(f"  >>> 答案里**仍有评分碎片**: {sorted(set(hits))}")
        print()
        print("  ---- 答案全文 ----")
        for line in text.split("\n"):
            print("  | " + line)
        print()

    print("=" * 78)
    print("判定")
    print("=" * 78)
    if deploy_verdict == "new":
        print("  线上跑的是**新代码** —— 若仍看到碎片，说明过滤规则还有漏网")
    elif deploy_verdict == "old":
        print("  线上跑的是**旧代码** —— 我的修复还没部署上去")
        print("  需要让同学在 Render 点一次 Manual Deploy")
    else:
        print("  这几轮模型都成功了，没触发回退，无法判定新旧")
    return 0


if __name__ == "__main__":
    sys.exit(main())
