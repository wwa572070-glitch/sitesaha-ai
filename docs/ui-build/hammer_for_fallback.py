"""高频请求逼出限流，验证回退路径是否已是新代码（第 16 轮）。

免费模型有速率限制。连续快速提问会触发 429，
从而走进回退路径 —— 这样就能读到告警格式，判断新旧代码。

旧代码告警：...已回退到检索摘要：ProviderError
新代码告警：...已回退到检索摘要（ProviderError/xxx：原因）

用法：python hammer_for_fallback.py
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

BASE = "https://sitesaha-ai-v16.onrender.com"
QUESTIONS = [
    "我没有挂安全带", "脚手架搭设要求", "基坑监测项目", "动火作业许可",
    "配电箱防护", "洞口临边防护", "吊装警戒区", "模板支撑验收",
    "有限空间作业", "临时用电接地", "高处作业平台", "安全帽佩戴",
]


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
    print("=" * 78)
    print("并发提问，制造限流")
    print("=" * 78)

    results = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = [pool.submit(ask, q) for q in QUESTIONS]
        for future in futures:
            results.append(future.result())

    fallback_seen = False
    new_format = False
    fragments: set[str] = set()

    for index, (status, data, elapsed) in enumerate(results, 1):
        if not isinstance(data, dict):
            print(f"  [{index:>2}] HTTP {status}  {str(data)[:70]}")
            continue
        mode = data.get("mode", "?")
        warnings = data.get("warnings") or []
        text = data.get("text") or ""
        fallback = [w for w in warnings if "在线模型生成失败" in w]
        tag = "回退" if fallback else "正常"
        print(f"  [{index:>2}] {mode:<11} {tag:<4} {elapsed:>6.1f}s  长度 {len(text)}")

        if fallback:
            fallback_seen = True
            message = fallback[0]
            print(f"       告警: {message[:140]}")
            if "（" in message:
                new_format = True
            for marker in ("扣10", "扣6", "扣5", "扣8", "应得", "实得"):
                if marker in text:
                    fragments.add(marker)

    print()
    print("=" * 78)
    print("结论")
    print("=" * 78)
    print(f"  触发回退      : {fallback_seen}")
    print(f"  新告警格式    : {new_format}")
    print(f"  评分碎片      : {fragments if fragments else '无'}")

    if fallback_seen and new_format:
        print()
        print("  ✅ 新代码已上线（回退告警带真实原因）")
    elif fallback_seen and not new_format:
        print()
        print("  ❌ 仍是旧代码（告警只有异常类名）—— 部署可能还没完成")
    else:
        print()
        print("  ⚠️ 没触发回退，无法判断。可稍后重试。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
