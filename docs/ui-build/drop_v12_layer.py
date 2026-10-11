"""删除已被 V13 取代的 V12 样式层。

V12 层是上一轮配色（靛蓝/琥珀）的产物，V13 已重新定义了同一批令牌与组件，
但 V12 仍然留在样式表里 —— 它的 190 个颜色值、一半字号档、大量组件规则
全部是"写了但永远被覆盖"的死代码，却仍在抬高设计系统的表面复杂度。

层序会变成：V10 基础 → V13 设计系统 → V13 布局 → V13 暗色

用法：python drop_v12_layer.py [--dry-run]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
HEAD = BUILD / "index_head.html"

DROP = [
    ("/* ===== V12 THEME BEGIN =====", "/* ===== V12 THEME END ===== */", "V12 视觉层"),
    ("/* ===== V12 DARK BEGIN =====", "/* ===== V12 DARK END ===== */", "V12 暗色"),
    ("/* ===== V13 PHASES BEGIN =====", "/* ===== V13 PHASES END ===== */", "V13 流程阶段（已并入布局层）"),
]


def blocks(css: str) -> list[tuple[str, str]]:
    return [(m.group(1), m.group(2)) for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", css, re.S)]


def normalise(body: str) -> str:
    parts = []
    for decl in body.split(";"):
        if ":" not in decl:
            continue
        prop, _, value = decl.partition(":")
        prop, value = prop.strip().lower(), " ".join(value.split())
        if prop and value:
            parts.append(f"{prop}:{value}")
    return ";".join(parts)


def measure(css: str) -> dict[str, int]:
    plain = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    return {
        "规则": len(blocks(plain)),
        "字号档": len({float(x) for x in re.findall(r"font-size:\s*([\d.]+)px", plain)}),
        "颜色": len({x.lower() for x in re.findall(r"#[0-9a-fA-F]{6}\b", plain)}),
        "字符": len(css),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    head = HEAD.read_text(encoding="utf-8")
    match = re.search(r"<style>(.*?)</style>", head, re.S)
    if not match:
        print("[FAIL] 找不到 <style>")
        return 1
    css = match.group(1)

    before = measure(css)
    print("=== 删除前 ===")
    for key, value in before.items():
        print(f"  {key:8} {value}")

    for begin, end, label in DROP:
        pattern = re.compile(re.escape(begin) + r".*?" + re.escape(end) + r"\n?", re.S)
        css, count = pattern.subn("", css)
        print(f"  {'删除' if count else '未找到'}：{label}（{count} 处）")

    # 删掉 V12 后，再清一遍因此暴露出来的完全重复块
    seen: set[tuple[str, str]] = set()
    removed = 0

    def dedupe(match: re.Match[str]) -> str:
        nonlocal removed
        selector = " ".join(match.group(1).split())
        body = normalise(match.group(2))
        if not body:
            return match.group(0)
        key = (selector, body)
        if key in seen:
            removed += 1
            return ""
        seen.add(key)
        return match.group(0)

    css = re.sub(r"([^{}]+)\{([^{}]*)\}", dedupe, css, flags=re.S)
    print(f"  删除重复声明块：{removed} 条")

    after = measure(css)
    print()
    print("=== 删除后 ===")
    for key in before:
        delta = after[key] - before[key]
        sign = f"（{delta:+d}）" if delta else ""
        print(f"  {key:8} {after[key]} {sign}")

    if args.dry_run:
        print("\n（dry-run，未写入）")
        return 0

    HEAD.write_text(head[: match.start(1)] + css + head[match.end(1) :], encoding="utf-8")
    print(f"\n[ok] 已写入，index_head.html {len(head)} → {len(head) - before['字符'] + after['字符']} 字符")
    return 0


if __name__ == "__main__":
    sys.exit(main())
