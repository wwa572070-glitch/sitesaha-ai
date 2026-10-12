"""检测线上是否已部署「依据区清理」修复（第 16 轮）。

可靠的检测方法：
  新代码给依据区加了 src-details / cleanSourceText 等标识，
  它们嵌在 INDEX_HTML 里随页面一起下发。
  所以直接抓线上首页 HTML，搜这些标识即可判断新旧代码。

用法：python detect_deploy.py [--wait 分钟数]
"""

from __future__ import annotations

import argparse
import sys
import time
import urllib.request

BASE = "https://sitesaha-ai-v16.onrender.com"

MARKERS = {
    "src-details": "依据区折叠容器",
    "cleanSourceText": "正文清理函数",
    "source-excerpt": "清理后的预览样式",
    "RE_LEAD_PUNCT": "起首标点剥除",
}


def fetch_home(timeout: int = 90) -> str:
    with urllib.request.urlopen(BASE + "/", timeout=timeout) as response:
        return response.read().decode("utf-8", "replace")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wait", type=int, default=0, help="等待分钟数，期间轮询")
    args = parser.parse_args()

    deadline = time.time() + args.wait * 60
    attempt = 0
    while True:
        attempt += 1
        print("=" * 74)
        print(f"第 {attempt} 次检测  （{time.strftime('%H:%M:%S')}）")
        print("=" * 74)
        try:
            html = fetch_home()
        except Exception as exc:  # noqa: BLE001
            print(f"  抓取失败: {type(exc).__name__}")
            html = ""

        found = {key: (key in html) for key in MARKERS}
        for key, ok in found.items():
            print(f"  [{'有' if ok else '无'}] {key:<18} {MARKERS[key]}")
        print(f"  页面大小 {len(html) / 1024:.0f} KB")

        if all(found.values()):
            print()
            print("  ✅ 新代码已部署上线")
            return 0

        if any(found.values()):
            print()
            print("  ⚠️ 部分标识存在 —— 可能是抓取不完整，再试一次")

        if time.time() >= deadline:
            print()
            print("  ❌ 仍是旧代码（等待超时）")
            print("     需要在 Render 触发一次部署")
            return 1

        print()
        print("  30 秒后重试…")
        time.sleep(30)


if __name__ == "__main__":
    sys.exit(main())
