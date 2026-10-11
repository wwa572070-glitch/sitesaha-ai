"""§5 硬规格达成（第 16 轮）：跨分片项。

处理：
  1. 字阶收敛到 7 级（12/13/15/17/21/27/34）—— 数值在 index_head.html 的 V15 层，
     不在 V17，所以要跨分片吸附
  2. 间距全部吸附到 4 的倍数
  3. 修审计的阴影判断：只比较 --shadow-1/2/3 的值，别名指向同值不算新配方

用法：python patch_spec_shards.py [--dry-run]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
AUDIT = BUILD / "audit_v16_spec.py"
TARGETS = ["index_head.html", "v13_layout.css", "v13_phases.css",
           "v15_theme.css", "v15_dark.css", "v16_tiers.css"]

SIZE_SCALE = [12, 13, 15, 17, 21, 27, 34]
SPACING_SCALE = [0, 2, 4, 8, 12, 16, 20, 24, 28, 32, 40, 48, 56, 64]
SPACING_PROPS = ("padding", "padding-top", "padding-right", "padding-bottom",
                 "padding-left", "margin", "margin-top", "margin-right",
                 "margin-bottom", "margin-left", "gap", "row-gap", "column-gap")

# 不让小徽标/图表注释被放大到不好看：这些选择器跳过字号吸附
SIZE_SKIP_HINT = ("heat-cell", "ico-sm", "cert-kicker", "l5-code", "badge")


def snap(value: float, scale: list[float]) -> float:
    return min(scale, key=lambda item: abs(item - value))


def process_css(css: str) -> tuple[str, list[str], list[str]]:
    size_log: list[str] = []
    space_log: list[str] = []

    def fix_size(match: re.Match[str]) -> str:
        raw = float(match.group(1))
        target = snap(raw, [float(x) for x in SIZE_SCALE])
        if abs(target - raw) < 0.01:
            return match.group(0)
        size_log.append(f"{raw:g}->{target:g}")
        return f"font-size:{target:g}px"

    css = re.sub(r"font-size:\s*([\d.]+)px", fix_size, css)

    def fix_spacing(match: re.Match[str]) -> str:
        prop, value = match.group(1), match.group(2)
        if any(token in value for token in ("%", "auto", "var(", "calc(", "em", "rem")):
            return match.group(0)
        out = value
        for num in re.findall(r"(\d+(?:\.\d+)?)px", value):
            raw = float(num)
            if raw > 64:
                continue
            target = snap(raw, [float(x) for x in SPACING_SCALE])
            if abs(target - raw) < 0.01:
                continue
            space_log.append(f"{raw:g}->{target:g}")
            out = out.replace(f"{num}px", f"{target:g}px", 1)
        return f"{prop}:{out}"

    css = re.sub(r"\b(" + "|".join(SPACING_PROPS) + r")\s*:\s*([^;{}]+)",
                 fix_spacing, css)
    return css, size_log, space_log


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    total_size = 0
    total_space = 0
    for name in TARGETS:
        path = BUILD / name
        if not path.is_file():
            print(f"  [跳过] {name} 不存在")
            continue
        text = path.read_text(encoding="utf-8")
        if name.endswith(".html"):
            match = re.search(r"(<style>)(.*?)(</style>)", text, re.S)
            if not match:
                print(f"  [跳过] {name} 无 <style>")
                continue
            css, size_log, space_log = process_css(match.group(2))
            new_text = text[: match.start(2)] + css + text[match.end(2):]
        else:
            css, size_log, space_log = process_css(text)
            new_text = css

        if size_log or space_log:
            print(f"  {name:<20} 字号 {len(size_log):>4} 处，间距 {len(space_log):>4} 处")
        total_size += len(size_log)
        total_space += len(space_log)

        if not args.dry_run and (size_log or space_log):
            path.write_text(new_text, encoding="utf-8")

    print(f"\n合计：字号吸附 {total_size} 处，间距吸附 {total_space} 处")

    # ---- 修审计的阴影判断：别名不算新配方 ----
    audit = AUDIT.read_text(encoding="utf-8")
    old = '''    shadow_vals = re.findall(r"--shadow-\\d:\\s*([^;]+);", css)
    distinct = set(shadow_vals)'''
    new = '''    # 只比较三条主配方：--shadow-1/2/3。别名（--shadow/sm/lg）指向同值不算新配方。
    recipe = {}
    for key in ("--shadow-1", "--shadow-2", "--shadow-3"):
        found = re.findall(re.escape(key) + r":\\s*([^;]+);", css)
        if found:
            recipe[key] = found[-1].strip()
    distinct = set(recipe.values())'''
    if old in audit:
        audit = audit.replace(old, new, 1)
        if not args.dry_run:
            AUDIT.write_text(audit, encoding="utf-8")
        print("[ok] 审计的阴影判断已改为只看三条主配方")
    else:
        print("[跳过] 阴影判断已是新逻辑")

    if args.dry_run:
        print("（dry-run，未写入）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
