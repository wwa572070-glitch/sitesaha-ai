"""从现有样式表里实测出设计系统的缺口数据。

design-baseline 自己标注了 3 个 low-confidence 缺口：
  · 没有命名间距令牌 → 实测 padding/margin/gap 的实际取值分布
  · 组件样式未检测到共享路径 → 实测各组件类实际用到的属性
  · 没有动效令牌 → 实测 transition/animation 的时长与缓动

本脚本只读取、只统计，不改任何文件。
用法：python extract_design_gaps.py
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

BUILD = Path(__file__).resolve().parent
FILES = ["index_head.html", "v13_theme.css", "v13_layout.css", "v13_phases.css",
         "v14_theme.css", "v13_dark.css"]


def css_of(name: str) -> str:
    text = (BUILD / name).read_text(encoding="utf-8")
    if name.endswith(".html"):
        match = re.search(r"<style>(.*?)</style>", text, re.S)
        return match.group(1) if match else ""
    return text


def main() -> int:
    css = "\n".join(css_of(name) for name in FILES)
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)

    print("=" * 74)
    print("一、间距实测（px 值分布）")
    print("=" * 74)
    spacing: Counter = Counter()
    for prop in ("padding", "margin", "gap", "row-gap", "column-gap"):
        for match in re.finditer(rf"(?<![\w-]){prop}\s*:\s*([^;}}]+)", css):
            for num in re.findall(r"(\d+(?:\.\d+)?)px", match.group(1)):
                value = float(num)
                if 0 < value <= 64:
                    spacing[value] += 1
    print("  出现次数最多的取值：")
    for value, n in spacing.most_common(22):
        v = int(value) if value == int(value) else value
        flag = "  ← 4 的倍数" if float(v) % 4 == 0 else ""
        print(f"    {str(v) + 'px':>8}  {n:>4} 次{flag}")
    total = sum(spacing.values())
    on_grid = sum(n for v, n in spacing.items() if v % 4 == 0)
    print(f"\n  合计 {total} 处；4 的倍数占 {on_grid / total * 100:.1f}%")

    print()
    print("=" * 74)
    print("二、动效实测（时长与缓动）")
    print("=" * 74)
    durations: Counter = Counter()
    easings: Counter = Counter()
    for match in re.finditer(r"transition\s*:\s*([^;}}]+)", css):
        for d in re.findall(r"(\d+(?:\.\d+)?)(m?s)\b", match.group(1)):
            durations[f"{d[0]}{d[1]}"] += 1
        for e in re.findall(r"\b(linear|ease|ease-in|ease-out|ease-in-out|cubic-bezier\([^)]*\))", match.group(1)):
            easings[e] += 1
    for match in re.finditer(r"animation(?:-duration)?\s*:\s*([^;}}]+)", css):
        for d in re.findall(r"(\d+(?:\.\d+)?)(m?s)\b", match.group(1)):
            durations[f"{d[0]}{d[1]}"] += 1
    print(f"  时长分布：{durations.most_common(10)}")
    print(f"  缓动分布：{easings.most_common(8)}")
    reduced = len(re.findall(r"prefers-reduced-motion", css))
    print(f"  prefers-reduced-motion 处理：{reduced} 处")

    print()
    print("=" * 74)
    print("三、组件基元实测（脚本会创建的组件类）")
    print("=" * 74)
    scripts = "\n".join(
        (BUILD / n).read_text(encoding="utf-8")
        for n in ("index_script_a.js", "index_script_b.js")
    )
    made = set(re.findall(r'make\(\s*"[a-z]+"\s*,\s*"([a-zA-Z][\w -]*)"', scripts))
    # 只看主要组件（排除纯排版类）
    typographic = {"lead", "empty-state", "hit", "count-badge", "badge", "scope",
                   "num", "src", "source-meta", "hot-count", "head-spacer", "head-note"}
    components = sorted(made - typographic)
    print(f"  脚本创建 {len(made)} 个类，其中组件类 {len(components)} 个")
    for cls in components[:40]:
        # 找该类的样式规则数
        n = len(re.findall(rf"\.{re.escape(cls.split()[0])}(?![\w-])", css))
        print(f"    .{cls:<28} 样式规则 {n} 条")

    print()
    print("=" * 74)
    print("四、字号实测（当前实际使用的档位）")
    print("=" * 74)
    sizes = Counter(re.findall(r"font-size\s*:\s*([\d.]+)px", css))
    for value, n in sorted(sizes.items(), key=lambda kv: float(kv[0])):
        print(f"    {value + 'px':>8}  {n:>4} 次")
    tokens = re.findall(r"--fs-[\w-]+\s*:\s*([\d.]+)px", css)
    if tokens:
        print(f"  已定义的 --fs-* 令牌：{sorted(set(tokens), key=float)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
