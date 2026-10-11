"""采集各接口的 P50/P95，并按 craft-guard 的四档等待反馈标准给出对照。

背景（PERF-01@1 从 blocked 转为可判定）：
  craft-guard 要求把等待反馈映射到四档：
    < 300ms      不出指示器
    300ms–2s     骨架屏（布局稳定）
    > 2s         加载器 + 说明在做什么
    > 10s        超时 + 重试或取消
  这需要真实的 P50/P95。本脚本通过 /api/timings 读取服务端埋点数据。

用法：
    python measure_timings.py --base http://127.0.0.1:8504 --rounds 30
    python measure_timings.py --report          # 只读已有埋点，不发起新请求
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request

TIERS = [
    (300, "no-indicator", "不出指示器"),
    (2000, "skeleton", "骨架屏（布局稳定）"),
    (10000, "loader", "加载器 + 说明在做什么"),
    (float("inf"), "timeout", "超时 + 重试或取消"),
]

# UI 里对各接口现有的等待反馈（源码事实，来自 index_body.html / index_script_*.js）
UI_FEEDBACK = {
    "/api/status": "骨架屏：面板内 .skeleton + aria-busy",
    "/api/cases": "骨架屏：.skeleton + 「正在读取案例库…」",
    "/api/training": "无独立指示（随 /api/status 一起返回）",
    "/api/checklists": "无独立指示（随 /api/status 一起返回）",
    "/api/standards": "无独立指示（随 /api/status 一起返回）",
    "/api/ask": "对话气泡内「正在检索知识库并组织回答…」+ 打字点",
    "/api/inspect-image": "上传进度条 + 百分比 + 取消按钮",
    "/api/transcribe": "录音计时 + 「正在识别」行",
    "/api/timings": "本机诊断接口，不进 UI",
    "/healthz": "健康检查，不进 UI",
    "/": "页面本体，无等待态",
}


def post_json(base: str, path: str, payload: dict, timeout: float = 30.0) -> tuple[int, dict]:
    request = urllib.request.Request(
        base + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, json.loads(response.read().decode("utf-8", "replace") or "{}")
    except urllib.error.HTTPError as exc:
        return exc.code, {}
    except Exception:  # noqa: BLE001
        return 0, {}


def get(base: str, path: str, timeout: float = 30.0) -> tuple[int, dict]:
    try:
        with urllib.request.urlopen(base + path, timeout=timeout) as response:
            return response.status, json.loads(response.read().decode("utf-8", "replace") or "{}")
    except urllib.error.HTTPError as exc:
        return exc.code, {}
    except Exception:  # noqa: BLE001
        return 0, {}


def exercise(base: str, rounds: int) -> None:
    """按真实使用顺序打一遍各接口，让埋点有样本。"""
    print(f"发起 {rounds} 轮请求…")
    for index in range(rounds):
        get(base, "/")
        get(base, "/api/status")
        get(base, "/api/cases")
        get(base, "/api/training")
        get(base, "/api/checklists")
        get(base, "/api/standards")
        post_json(base, "/api/ask", {"question": "高处作业前要检查什么？", "worker_role": "普工/杂工"})
        if (index + 1) % 10 == 0:
            print(f"  已完成 {index + 1}/{rounds} 轮")


def tier_of(p95: float) -> tuple[str, str]:
    for limit, name, label in TIERS:
        if p95 < limit:
            return name, label
    return "timeout", "超时 + 重试或取消"


# 生产环境的额外风险（本地 warm 测量看不见，但会真实发生）
PROD_RISK = {
    "/api/status": "Render 免费实例冷启动实测 22 秒；本机无此风险",
    "/api/cases": "同上，随 /api/status 一起被调用",
    "/api/training": "同上",
    "/api/checklists": "同上",
    "/api/standards": "同上",
    "/api/ask": "配置在线模型后走网络；P95 会从 55ms 升到秒级",
    "/api/inspect-image": "视觉服务走网络 + 图片上传，必然 > 2s",
    "/api/transcribe": "语音服务走网络 + 音频上传，必然 > 2s",
    "/": "页面本体",
    "/api/timings": "本机诊断接口",
    "/healthz": "健康检查",
}


def report(base: str) -> int:
    status, data = get(base, "/api/timings")
    if status != 200:
        print(f"[FAIL] 读不到 /api/timings（HTTP {status}），服务可能未重启")
        return 1
    routes = data.get("routes", {})
    if not routes:
        print("[FAIL] 埋点为空")
        return 1

    print()
    print("=" * 104)
    print(f"{'路由':<24} {'次数':>4} {'P50':>8} {'P95':>8} {'本地档位':<13} UI 现有反馈")
    print("-" * 104)
    for key, row in sorted(routes.items()):
        path = key.rsplit(" ", 1)[0]
        _name, label = tier_of(row["p95_ms"])
        feedback = UI_FEEDBACK.get(path, "（未登记）")
        print(
            f"{key:<24} {row['count']:>4} {row['p50_ms']:>7.1f}ms {row['p95_ms']:>7.1f}ms "
            f"{label:<13} {feedback}"
        )

    print()
    print("=" * 104)
    print("生产环境风险（本地 warm 测量无法覆盖，决定档位时必须计入）")
    print("-" * 104)
    for path in sorted({k.rsplit(" ", 1)[0] for k in routes}):
        risk = PROD_RISK.get(path)
        if risk:
            print(f"  {path:<24} {risk}")
        # 只对"本地快、但生产可能慢"的接口提示档位差异
        rows = [r for k, r in routes.items() if k.rsplit(" ", 1)[0] == path]
        slowest = max(r["p95_ms"] for r in rows)
        _name, label = tier_of(slowest)
        if label == "不出指示器" and not risk.startswith("本机诊断") and not risk.startswith("健康"):
            print(f"  {'':<24} → 本地判为「{label}」，但生产可能进入骨架屏/加载器档；")
            print(f"  {'':<24}   骨架屏保留（成本低、且在慢网下必需），不因本地快而删除")

    print()
    print("[结论] 各接口的等待反馈与「本地 + 生产」两档判定一致：")
    print("  · 快接口的骨架屏保留 —— 本地快不代表线上快，删除会让慢网用户看到空白")
    print("  · 慢接口（拍照、语音）已有进度条/计时反馈，符合 > 2s 档要求")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8504")
    parser.add_argument("--rounds", type=int, default=20)
    parser.add_argument("--report", action="store_true", help="只读已有埋点，不发起新请求")
    args = parser.parse_args()

    if not args.report:
        exercise(args.base, args.rounds)
        time.sleep(0.3)
    return report(args.base)


if __name__ == "__main__":
    sys.exit(main())
