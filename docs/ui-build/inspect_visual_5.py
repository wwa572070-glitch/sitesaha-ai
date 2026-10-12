"""§5 前置检查：KPI / 案例数据 / 图标（第 21 轮）。

用法：python inspect_visual_5.py
"""

from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

BUILD = Path(__file__).resolve().parent


def main() -> int:
    body = (BUILD / "index_body.html").read_text(encoding="utf-8")
    script_a = (BUILD / "index_script_a.js").read_text(encoding="utf-8")

    print("=" * 78)
    print("一、KPI 区 markup")
    print("=" * 78)
    index = body.find("tier-l2")
    if index < 0:
        index = body.find("kpi")
    print(body[max(0, index - 200): index + 900])

    print()
    print("=" * 78)
    print("二、KPI 渲染逻辑")
    print("=" * 78)
    for keyword in ("kpiGrid", "renderKpi", "kpiValue", "metricValue"):
        position = script_a.find(keyword)
        if position >= 0:
            line = script_a[:position].count("\n") + 1
            print(f"  {keyword}: 行 {line}")

    print()
    print("=" * 78)
    print("三、/api/status 返回的指标字段")
    print("=" * 78)
    try:
        with urllib.request.urlopen("http://127.0.0.1:8504/api/status", timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
        for key, value in data.items():
            if isinstance(value, dict):
                print(f"  {key}: {{{', '.join(list(value)[:6])}}}")
            elif isinstance(value, list):
                print(f"  {key}: [ {len(value)} 项 ]")
            else:
                print(f"  {key}: {value}")
    except Exception as exc:  # noqa: BLE001
        print(f"  失败：{type(exc).__name__}: {exc}")

    print()
    print("=" * 78)
    print("四、/api/cases 第一条案例的字段")
    print("=" * 78)
    try:
        with urllib.request.urlopen("http://127.0.0.1:8504/api/cases", timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
        cases = data.get("cases") if isinstance(data, dict) else data
        print(f"  案例数：{len(cases) if cases else 0}")
        if cases:
            first = cases[0]
            print("  字段：")
            for key, value in first.items():
                shown = str(value)
                print(f"    {key:<20} {shown[:90]}")
    except Exception as exc:  # noqa: BLE001
        print(f"  失败：{type(exc).__name__}: {exc}")

    print()
    print("=" * 78)
    print("五、图标雪碧图里有啥")
    print("=" * 78)
    import re
    symbols = re.findall(r'<symbol[^>]*id="([^"]+)"', body)
    print(f"  {len(symbols)} 个 symbol: {', '.join(symbols)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
