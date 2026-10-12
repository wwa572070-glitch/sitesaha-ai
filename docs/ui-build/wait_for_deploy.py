"""等 Render 部署完成，并验证回退答案修复已生效（第 16 轮线上修复验证）。

怎么判断新代码已上线（版本号没变，所以不能靠 version）：
  修复前的回退告警格式：在线模型生成失败，已回退到检索摘要：ProviderError
  修复后的回退告警格式：在线模型生成失败，已回退到检索摘要（ProviderError/xxx：原因）

  所以只要触发一次回退、看告警格式，就能判断。

策略：反复问同一个问题（原来会触发回退的那个），
  · 模型成功 → 说明服务正常，且答案可读
  · 模型失败 → 看告警格式判断新旧代码

用法：python wait_for_deploy.py
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request

BASE = "https://sitesaha-ai-v16.onrender.com"
QUESTION = "我没有挂安全带"


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
        return exc.code, exc.read().decode("utf-8", "replace")[:300], time.time() - started
    except Exception as exc:  # noqa: BLE001
        return 0, f"{type(exc).__name__}: {exc}", time.time() - started


def main() -> int:
    print("=" * 76)
    print("等待 Render 部署（最多约 6 分钟）")
    print("=" * 76)

    new_code_seen = False
    for attempt in range(1, 13):
        print(f"\n--- 第 {attempt} 轮 ---")
        status, data, elapsed = ask(QUESTION)
        print(f"  HTTP {status}  耗时 {elapsed:.1f}s")

        if not isinstance(data, dict):
            print(f"  {str(data)[:150]}")
            time.sleep(25)
            continue

        mode = data.get("mode")
        warnings = data.get("warnings") or []
        text = data.get("text") or ""
        print(f"  mode     = {mode}")
        print(f"  warnings = {warnings[:2]}")
        print(f"  答案长度 = {len(text)}")
        print(f"  答案前 140 字: {text[:140]}")

        # 判断新旧代码
        fallback = [w for w in warnings if "在线模型生成失败" in w]
        if fallback:
            message = fallback[0]
            if "（" in message:
                print()
                print("  ✅ 检测到**修复后**的回退格式（告警里带了真实原因）")
                new_code_seen = True
            else:
                print()
                print("  ⏳ 还是**修复前**的格式（只有异常类名），部署可能仍在进行")
            # 检查答案是否还有碎片
            bad_markers = ["扣10", "扣6", "扣5", "得分"]
            hit = [m for m in bad_markers if m in text]
            print(f"  答案里还有评分碎片吗: {hit if hit else '没有 ✅'}")
        else:
            print()
            print("  ✅ 模型正常返回，未触发回退")
            new_code_seen = True

        if new_code_seen:
            break
        time.sleep(25)

    print()
    print("=" * 76)
    if new_code_seen:
        print("  部署已完成，服务正常")
    else:
        print("  仍未确认部署完成；可能构建还在进行，稍后再试")
    print("=" * 76)
    return 0


if __name__ == "__main__":
    sys.exit(main())
