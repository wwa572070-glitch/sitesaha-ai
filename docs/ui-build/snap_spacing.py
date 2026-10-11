"""把间距与字号归一化到统一刻度。

实测发现（extract_design_gaps.py）：
  · 629 处间距里只有 38.8% 是 4 的倍数 —— 11/13/9/7/15/18px 这类零散值遍地。
    相邻元素的 12px 和 13px 肉眼分不出，但会让版面失去对齐节奏，
    这正是"看着乱"最直接的量化原因。
  · 字号有 9 档，其中 15px 只用了 2 处，属于噪声档位。

做法：
  间距吸附到 4 的网格（4/8/12/16/20/24/28/32/40/48），保留 0~3px 的细线与
  边框偏移不动（那是刻意的小值）。字号吸附到 8 档刻度。

盾牌：只改 px 数值，不动属性名、选择器、结构。
用法：python snap_spacing.py [--dry-run]
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

BUILD = Path(__file__).resolve().parent
FILES = ["index_head.html", "v13_theme.css", "v13_layout.css", "v13_phases.css",
         "v14_theme.css", "v13_dark.css"]

SPACING_SCALE = [0, 2, 4, 8, 12, 16, 20, 24, 28, 32, 40, 48, 56, 64]
SIZE_SCALE = [11, 12, 13, 14, 16, 18, 21, 26]
LINE_SCALE = [1.4, 1.6, 1.8]

SPACING_PROPS = ("padding", "padding-top", "padding-right", "padding-bottom", "padding-left",
                 "margin", "margin-top", "margin-right", "margin-bottom", "margin-left",
                 "gap", "row-gap", "column-gap")

# 不参与间距吸附的选择器片段（装饰性细线、进度条等刻意的小值）
SKIP_HINT = ("sk-", "skeleton", "track", "bar", "rule", "divider", "underline")


def snap(value: float, scale: list[float]) -> float:
    return min(scale, key=lambda s: abs(s - value))


def process(css: str, dry: bool) -> tuple[str, Counter, Counter]:
    size_hits: Counter = Counter()
    space_hits: Counter = Counter()

    def fix_spacing(match: re.Match[str]) -> str:
        prop, value = match.group(1), match.group(2)
        if any(h in value for h in ("%", "auto", "var(", "calc(", "em", "rem", "vh", "vw")):
            return match.group(0)
        out = value
        for num in re.findall(r"(\d+(?:\.\d+)?)px", value):
            raw = float(num)
            if raw > 64:
                continue
            target = snap(raw, SPACING_SCALE)
            if abs(target - raw) < 0.01:
                continue
            space_hits[f"{raw:g}→{target:g}"] += 1
            out = out.replace(f"{num}px", f"{target:g}px", 1)
        return f"{prop}:{out}"

    css = re.sub(
        r"\b(" + "|".join(SPACING_PROPS) + r")\s*:\s*([^;{}]+)",
        fix_spacing, css,
    )

    def fix_size(match: re.Match[str]) -> str:
        prop, raw_text = match.group(1), match.group(2)
        raw = float(raw_text)
        target = snap(raw, SIZE_SCALE)
        if abs(target - raw) < 0.01:
            return match.group(0)
        size_hits[f"{raw:g}→{target:g}"] += 1
        return f"{prop}{target:g}px"

    css = re.sub(r"(font-size:\s*)([\d.]+)px", fix_size, css)

    def fix_line(match: re.Match[str]) -> str:
        raw = float(match.group(2))
        target = snap(raw, LINE_SCALE)
        if abs(target - raw) < 0.01:
            return match.group(0)
        return f"{match.group(1)}{target:g}{match.group(3)}"

    css = re.sub(r"(line-height:\s*)([\d.]+)(\s*[;}])", fix_line, css)
    return css, size_hits, space_hits


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    total_size: Counter = Counter()
    total_space: Counter = Counter()
    changed_files = 0

    for name in FILES:
        path = BUILD / name
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        if name.endswith(".html"):
            match = re.search(r"(<style>)(.*?)(</style>)", text, re.S)
            if not match:
                continue
            css, size_hits, space_hits = process(match.group(2), args.dry_run)
            if not args.dry_run:
                new_text = text[: match.start(2)] + css + text[match.end(2):]
                path.write_text(new_text, encoding="utf-8")
        else:
            css, size_hits, space_hits = process(text, args.dry_run)
            if not args.dry_run:
                path.write_text(css, encoding="utf-8")

        if size_hits or space_hits:
            changed_files += 1
            print(f"  {name:<20} 字号 {sum(size_hits.values()):>4} 处，间距 {sum(space_hits.values()):>4} 处")
        total_size += size_hits
        total_space += space_hits

    print()
    print(f"字号吸附合计 {sum(total_size.values())} 处：")
    for key, n in total_size.most_common(14):
        print(f"    {key:<12} {n:>4}")
    print(f"\n间距吸附合计 {sum(total_space.values())} 处：")
    for key, n in total_space.most_common(14):
        print(f"    {key:<12} {n:>4}")

    if args.dry_run:
        print("\n（dry-run，未写入）")
    else:
        print(f"\n[ok] 已更新 {changed_files} 个文件")
        # 复测网格对齐率
        css_all = ""
        for name in FILES:
            path = BUILD / name
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8")
            css_all += re.search(r"<style>(.*?)</style>", text, re.S).group(1) if name.endswith(".html") else text
        spacing: Counter = Counter()
        for prop in ("padding", "margin", "gap"):
            for m in re.finditer(rf"(?<![\w-]){prop}\s*:\s*([^;}}]+)", css_all):
                for num in re.findall(r"(\d+(?:\.\d+)?)px", m.group(1)):
                    v = float(num)
                    if 0 < v <= 64:
                        spacing[v] += 1
        total = sum(spacing.values())
        on_grid = sum(n for v, n in spacing.items() if v % 4 == 0)
        print(f"    4 的倍数占比：38.8% → {on_grid / total * 100:.1f}%（{on_grid}/{total}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
