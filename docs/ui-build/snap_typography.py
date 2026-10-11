"""把字号与行高收敛到统一刻度。

现状：24 档字号（11.0 / 11.5 / 12.0 / 12.5 / 13.0 …），
其中 14 与 14.5、15 与 15.5 这类差异肉眼几乎不可见，
却让"视觉层级"从 3~4 级膨胀到 20 多级 —— 这是页面显乱的重要原因。

做法：把字号吸附到 8 档刻度，行高吸附到 3 档，字重保持原样。
V13 层里的显式字号是刻意设定的，同样按刻度校验后保留。

刻度：11 / 12 / 13 / 14 / 16 / 18 / 21 / 26
行高：1.4 / 1.6 / 1.8

用法：python snap_typography.py [--dry-run]
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

BUILD = Path(__file__).resolve().parent
HEAD = BUILD / "index_head.html"

SIZE_SCALE = [11, 12, 13, 14, 16, 18, 21, 26]
LINE_SCALE = [1.4, 1.6, 1.8]

# 图标字号不参与刻度：品牌方块、行动卡图标这类是图形尺寸，不是排版层级
ICON_SELECTORS = (".brand-mark", ".action-ico", ".logo-mark")

V13_MARK = "/* ===== V13 THEME BEGIN ====="


def snap(value: float, scale: list[float]) -> float:
    return min(scale, key=lambda s: abs(s - value))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--file", action="append", default=[],
                        help="要处理的文件（可重复）；默认处理 index_head.html")
    args = parser.parse_args()

    targets = [BUILD / name for name in args.file] if args.file else [HEAD]

    for target in targets:
        if not target.is_file():
            print(f"[FAIL] 找不到 {target.name}")
            return 1
        head = target.read_text(encoding="utf-8")
        if target is HEAD:
            match = re.search(r"<style>(.*?)</style>", head, re.S)
            if not match:
                print("[FAIL] 找不到 <style>")
                return 1
            css = match.group(1)
            span = (match.start(1), match.end(1))
        else:
            css = head
            span = (0, len(head))

        before_sizes = Counter(re.findall(r"font-size:\s*([\d.]+)px", css))
        before_lines = Counter(re.findall(r"line-height:\s*([\d.]+)\s*[;}]", css))
        print(f"--- {target.name}：改前字号 {len(before_sizes)} 档，行高 {len(before_lines)} 档")

        size_hits = 0

        def fix_size(match: re.Match[str]) -> str:
            nonlocal size_hits
            # 图标类选择器不参与刻度
            line = match.group(0)
            if any(sel in line for sel in ICON_SELECTORS):
                return line
            raw = float(match.group(2))
            snapped = snap(raw, SIZE_SCALE)
            if abs(snapped - raw) < 0.01:
                return match.group(0)
            size_hits += 1
            return f"{match.group(1)}{snapped:g}px"

        css = re.sub(r"(font-size:\s*)([\d.]+)px", fix_size, css)

        line_hits = 0

        def fix_line(match: re.Match[str]) -> str:
            nonlocal line_hits
            raw = float(match.group(2))
            snapped = snap(raw, LINE_SCALE)
            if abs(snapped - raw) < 0.01:
                return match.group(0)
            line_hits += 1
            return f"{match.group(1)}{snapped:g}"

        css = re.sub(r"(line-height:\s*)([\d.]+)(\s*[;}])", lambda m: fix_line(m) + m.group(3), css)

        after_sizes = Counter(re.findall(r"font-size:\s*([\d.]+)px", css))
        print(f"    字号吸附 {size_hits} 处 → {len(after_sizes)} 档")
        print(f"    行高吸附 {line_hits} 处 → {len(set(re.findall(r'line-height:\s*([\d.]+)', css)))} 档")

        if args.dry_run:
            continue
        target.write_text(head[: span[0]] + css + head[span[1] :], encoding="utf-8")
        print(f"    [ok] 已写入 {target.name}")

    if args.dry_run:
        print("\n（dry-run，未写入）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
