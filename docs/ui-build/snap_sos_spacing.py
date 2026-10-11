"""把 §6 新增样式里的间距吸附到 4 的倍数（第 16 轮 §8 硬规格）。

我把间距比例从 94.2% 拉到了 88.3%，低于规格要求的 ≥90%。
原因是新写的应急样式里有 21 处 px 值不是 4 的倍数。

吸附规则：就近取 4 的倍数。
  6→8  10→12  13→12  14→16  18→20  22→24  30→32  34→36
例外（不吸附，因为吸附会破坏视觉）：
  · 2px 的线宽（时间轴连接线）—— 这是描边不是间距
  · 999px 的胶囊圆角 —— 这是"尽可能圆"的语义值
  这两类不算间距，审计里也要排除。

用法：python snap_sos_spacing.py [--dry-run]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
TIERS = BUILD / "v16_tiers.css"
AUDIT = BUILD / "audit_v16_spec.py"

# 明确的替换表（只作用于 §6 段落）
REPLACEMENTS = [
    ("padding: 20px 22px;", "padding: 20px 24px;"),
    ("gap: 14px;", "gap: 16px;"),
    ("gap: 10px;", "gap: 12px;"),
    ("padding: 16px 14px;", "padding: 16px;"),
    ("gap: 6px;", "gap: 8px;"),
    ("margin: 14px 0 0;", "margin: 16px 0 0;"),
    ("left: 13px;", "left: 12px;"),
    ("top: 30px;", "top: 28px;"),
    ("padding: 13px 14px;", "padding: 12px 16px;"),
    ("right: 18px;", "right: 20px;"),
    ("bottom: 18px;", "bottom: 20px;"),
    ("width: 34px; height: 34px;", "width: 36px; height: 36px;"),
    ("right: 12px; bottom: 12px;", "right: 12px; bottom: 12px;"),
    ("padding: 12px 14px;", "padding: 12px 16px;"),
    ("padding: 14px 12px;", "padding: 12px;"),
    ("gap: 10px;", "gap: 12px;"),
    ("padding: 12px 0;", "padding: 12px 0;"),
    ("margin-top: 18px;", "margin-top: 20px;"),
    ("margin-top: 10px;", "margin-top: 12px;"),
    ("margin-top: 12px;", "margin-top: 12px;"),
    ("margin-bottom: 20px;", "margin-bottom: 20px;"),
    ("margin-top: 8px;", "margin-top: 8px;"),
    ("padding-top: 10px;", "padding-top: 12px;"),
    ("padding: 13px 14px;", "padding: 12px 16px;"),
    ("gap: 14px;", "gap: 16px;"),
    ("width: 40px; height: 40px;", "width: 40px; height: 40px;"),
    ("margin: 0 0 16px 0;", "margin: 0 0 16px 0;"),
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    text = TIERS.read_text(encoding="utf-8")
    marker = "§6 应急处置页"
    index = text.find(marker)
    if index < 0:
        print("[跳过] 找不到 §6 段落")
        return 0
    head, segment = text[:index], text[index:]

    changed = 0
    for old, new in REPLACEMENTS:
        if old == new:
            continue
        count = segment.count(old)
        if count:
            segment = segment.replace(old, new)
            changed += count
    print(f"[ok] §6 段落内替换 {changed} 处")

    # 扫一遍还剩哪些不合规（排除线宽与胶囊圆角）
    props = ("padding", "margin", "gap", "top", "bottom", "left", "right")
    leftover = []
    for match in re.finditer(r"([a-z-]+)\s*:\s*([^;{}]+);", segment):
        prop, value = match.group(1), match.group(2).strip()
        if prop not in props:
            continue
        for number in re.findall(r"(-?\d+(?:\.\d+)?)px", value):
            amount = float(number)
            if amount != 0 and amount % 4 != 0:
                leftover.append(f"{prop}: {value}")
    if leftover:
        print(f"[注意] 仍有 {len(leftover)} 处非 4 倍数：")
        for item in sorted(set(leftover)):
            print(f"   {item}")
    else:
        print("[ok] §6 段落内间距全部落在 4 的倍数上")

    text = head + segment

    # ---- 审计排除线宽与胶囊圆角 ----
    audit = AUDIT.read_text(encoding="utf-8")
    if "border-width" not in audit and "描边不算间距" not in audit:
        print("[跳过] 审计暂未排除描边（如仍报错再处理）")

    if args.dry_run:
        print("（dry-run，未写入）")
        return 0
    TIERS.write_text(text, encoding="utf-8")
    print("[ok] 已写入")
    return 0


if __name__ == "__main__":
    sys.exit(main())
