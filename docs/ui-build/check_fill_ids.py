"""核对 /api/status 回填用的元素 id 是否都还在结构里。

背景：run_dom_sim.js 报「没有请求 /api/status」，但同时 创建节点数=134、
kpiDocs/kpiChunks 等回填值全为空。需要区分两种可能：
  (a) 脚本根本没请求接口
  (b) 请求了，但回填目标 id 在信息架构重组中被改名/删掉，于是值写不进去
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent

IDS = [
    "kpiDocs", "kpiChunks", "kpiCases", "documentCount", "roleCount",
    "modelStatus", "trainStepDone", "ringNum", "libraryNote",
    "kvVision", "kvAsr", "voiceHint", "priorityBadge",
]


def main() -> int:
    body = (BUILD / "index_body.html").read_text(encoding="utf-8")
    js = (BUILD / "index_script_a.js").read_text(encoding="utf-8") + \
         (BUILD / "index_script_b.js").read_text(encoding="utf-8")

    print(f"{'id':<16} {'结构里有':<10} {'脚本引用':<10} 判定")
    print("-" * 62)
    missing: list[str] = []
    for name in IDS:
        in_body = body.count(f'id="{name}"')
        in_js = len(re.findall(r'[$]\s*\(\s*"' + re.escape(name) + r'"', js))
        if in_body:
            verdict = "正常"
        elif in_js:
            verdict = "★ 脚本在写，但结构里没有 → 值写不进去"
            missing.append(name)
        else:
            verdict = "未使用"
        print(f"{name:<16} {in_body:<10} {in_js:<10} {verdict}")

    print()
    if missing:
        print(f"[发现] {len(missing)} 个 id 被脚本引用但结构里已不存在：")
        for name in missing:
            print(f"  - {name}")
    else:
        print("[OK] 脚本引用的回填 id 在结构里都能找到")

    print()
    print("=== /api/status 的请求与回填代码 ===")
    for match in re.finditer(r"/api/status", js):
        start = max(0, match.start() - 260)
        line = js[: match.start()].count("\n") + 1
        print(f"--- 第 {line} 行 ---")
        print("   " + " ".join(js[start: match.start() + 620].split())[:800])
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
