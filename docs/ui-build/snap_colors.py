"""把近似重复的颜色合并到统一色阶。

现状：119 个十六进制颜色，其中大量是"差 1~3 个 RGB 值"的近似灰
（例如 #e5e7eb / #e6e8ec / #e4e6ea），肉眼完全分不出，
但会让设计系统看起来毫无章法，也让后续改色无从下手。

做法：按感知距离（加权 RGB）把颜色合并到聚类中心，
聚类阈值内的颜色统一取出现次数最多的那个值。

用法：python snap_colors.py [--dry-run] [--threshold 12]
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

BUILD = Path(__file__).resolve().parent
HEAD = BUILD / "index_head.html"


def rgb(hexv: str) -> tuple[int, int, int]:
    h = hexv.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def distance(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    """加权 RGB 距离：人眼对绿色最敏感，蓝色最不敏感。"""
    dr, dg, db = a[0] - b[0], a[1] - b[1], a[2] - b[2]
    return (2 * dr * dr + 4 * dg * dg + 3 * db * db) ** 0.5


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--threshold", type=float, default=12.0)
    args = parser.parse_args()

    head = HEAD.read_text(encoding="utf-8")
    match = re.search(r"<style>(.*?)</style>", head, re.S)
    if not match:
        print("[FAIL] 找不到 <style>")
        return 1
    css = match.group(1)

    counts = Counter(x.lower() for x in re.findall(r"#[0-9a-fA-F]{6}\b", css))
    print(f"改前：{len(counts)} 个颜色，共出现 {sum(counts.values())} 次")

    # 令牌里定义的值是刻意选的调色板，必须原样保留，
    # 否则会把 --canvas、--green-700 这类语义色吸附走，等于破坏设计系统。
    protected: set[str] = set()
    for block in re.findall(r":root\s*\{(.*?)\}", css, re.S):
        for value in re.findall(r"--[\w-]+\s*:\s*(#[0-9a-fA-F]{6})\b", block):
            protected.add(value.lower())
    print(f"受保护令牌色 {len(protected)} 个：{sorted(protected)}")

    # 只把"非令牌色"吸附到最近的"令牌色"
    palette = sorted(protected)
    mapping: dict[str, str] = {}
    for color in counts:
        if color in protected:
            mapping[color] = color
            continue
        target = None
        best = args.threshold
        for candidate in palette:
            d = distance(rgb(color), rgb(candidate))
            if d <= best:
                best = d
                target = candidate
        mapping[color] = target or color

    merged = sum(1 for k, v in mapping.items() if k != v)
    leftover = len({v for v in mapping.values()})
    print(f"阈值 {args.threshold:g}：{len(counts)} → {leftover + merged - merged} 个色值"
          f"（合并 {merged} 个到令牌色）")

    if merged:
        print("\n合并明细（前 20 组）：")
        shown = 0
        for color, target in sorted(mapping.items(), key=lambda kv: -counts[kv[0]]):
            if color == target:
                continue
            print(f"  {color}  →  {target}   （原出现 {counts[color]} 次）")
            shown += 1
            if shown >= 20:
                break
        if merged > shown:
            print(f"  …… 另有 {merged - shown} 组")

    if args.dry_run:
        print("\n（dry-run，未写入）")
        return 0

    def repl(m: re.Match[str]) -> str:
        raw = m.group(0)
        return mapping.get(raw.lower(), raw)

    css = re.sub(r"#[0-9a-fA-F]{6}\b", repl, css)
    HEAD.write_text(head[: match.start(1)] + css + head[match.end(1) :], encoding="utf-8")

    after = len({x.lower() for x in re.findall(r"#[0-9a-fA-F]{6}\b", css)})
    print(f"\n[ok] 已写入，颜色 {len(counts)} → {after} 个；index_head.html {len(head)} 字符")
    return 0


if __name__ == "__main__":
    sys.exit(main())
