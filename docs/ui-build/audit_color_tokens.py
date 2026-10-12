"""审查：找出与现有设计变量完全同值的硬编码颜色（第 21 轮阶段一）。

为什么做这个：
  项目定义了 111 个设计变量，但 v15_theme / v15_dark / v16_tiers 里有 161 处
  硬编码十六进制颜色。其中一部分的值与某个变量**完全相同** ——
  这类替换是零风险的（视觉不变），改完后续调色只需动一处。

本脚本只做审查与报告，不改文件。

用法：python audit_color_tokens.py
"""

from __future__ import annotations

import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

BUILD = Path(__file__).resolve().parent
PALETTE = BUILD / "v17_palette.css"
LAYERS = ["v13_phases.css", "v13_layout.css", "v15_theme.css",
          "v15_dark.css", "v16_tiers.css"]


def load_tokens() -> dict[str, str]:
    """读取调色板定义的变量 → 值（小写）。"""
    tokens: dict[str, str] = {}
    text = PALETTE.read_text(encoding="utf-8")
    for match in re.finditer(r"(--[a-z0-9-]+)\s*:\s*(#[0-9a-fA-F]{3,8})", text):
        tokens[match.group(1)] = match.group(2).lower()
    return tokens


def invert(tokens: dict[str, str]) -> dict[str, list[str]]:
    """值 → 变量名列表。"""
    out: dict[str, list[str]] = defaultdict(list)
    for name, value in tokens.items():
        out[value].append(name)
    return out


def main() -> int:
    tokens = load_tokens()
    by_value = invert(tokens)

    print("=" * 76)
    print(f"设计变量 {len(tokens)} 个，对应 {len(by_value)} 个不同颜色值")
    print("=" * 76)

    total = 0
    replaceable = 0
    per_file: dict[str, list[tuple[int, str, list[str]]]] = defaultdict(list)
    counts: Counter[str] = Counter()

    for name in LAYERS:
        path = BUILD / name
        if not path.is_file():
            continue
        for line_no, line in enumerate(path.read_text(encoding="utf-8").split("\n"), 1):
            for match in re.finditer(r"#[0-9a-fA-F]{6}\b", line):
                value = match.group(0).lower()
                total += 1
                counts[value] += 1
                if value in by_value:
                    replaceable += 1
                    per_file[name].append((line_no, value, by_value[value]))

    print()
    print(f"分片里的硬编码颜色：{total} 处")
    print(f"其中**与某个变量完全同值**（可零风险替换）：{replaceable} 处 "
          f"（{round(replaceable / max(total, 1) * 100)}%）")
    print()

    print("=" * 76)
    print("可替换的按文件分布")
    print("=" * 76)
    for name, items in sorted(per_file.items(), key=lambda x: -len(x[1])):
        print(f"  {name:<20} {len(items):>3} 处")

    print()
    print("=" * 76)
    print("出现最多的可替换颜色（前 12）")
    print("=" * 76)
    print(f"  {'颜色':<12}{'次数':>5}   对应变量")
    print("  " + "-" * 60)
    suggested: dict[str, str] = {}
    for value, count in counts.most_common():
        if value not in by_value:
            continue
        names = by_value[value]
        # 优先选语义化的名字（brand/line/surface/risk 优先于 iNNN）
        preferred = sorted(
            names,
            key=lambda n: (0 if any(k in n for k in ("brand", "line", "surface",
                                                     "canvas", "accent", "risk"))
                           else 1, len(n)),
        )[0]
        suggested[value] = preferred
        print(f"  {value:<12}{count:>5}   {preferred}   (候选: {', '.join(names[:3])})")
        if len(suggested) >= 12:
            break

    print()
    print("=" * 76)
    print("结论")
    print("=" * 76)
    print(f"  {replaceable} 处可以零风险替换成变量引用，视觉完全不变。")
    print("  剩余硬编码需要人工判断语义（可能是刻意的独立色值）。")
    print()
    print("  建议：先只替换「出现次数 >= 2」且语义明确的部分，")
    print("        一次性替换 161 处风险太高，容易造成视觉回归。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
