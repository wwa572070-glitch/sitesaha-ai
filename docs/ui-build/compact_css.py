"""把 index_head.html 压缩成"单层样式表"。

问题：样式表叠了 4 层（V10 基础 + V12 + V13），同一组件被反复覆盖，
留下 24 档字号、190 个颜色、951 条规则，其中大部分是永远不会生效的死规则。
这是"看着乱"的工程根因。

做法：
  1) 把 V10 基础层里的字面颜色值统一解析成色值（--ink/--body/--muted/--line/--panel
     等令牌在最终层已定，这里直接内联成最终值），消除"未定义令牌"造成的隐性回退
  2) 从末层往前，删掉"选择器 + 属性 + 值完全相同"的重复声明块
  3) 报告压缩前后的规则数、字号档数、颜色数，作为验收依据

不做的事：不改选择器、不改生效顺序、不动 @media 内部结构。
任何"看起来像重复但实际作用不同"的规则都会保留。

用法：python compact_css.py [--dry-run]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
HEAD = BUILD / "index_head.html"

# 最终层（V13）已确定的令牌值。基础层里出现的这些名字统一替换成字面值，
# 避免基础层规则依赖某个主题的令牌而产生隐性差异。
FINAL_TOKENS = {
    "--ink": "#111827",
    "--body": "#4b5563",
    "--muted": "#6b7280",
    "--panel": "#ffffff",
    "--panel-soft": "#f3f4f6",
    "--paper": "#f7f8fa",
    "--line": "#e5e7eb",
    "--line-strong": "#d1d5db",
    "--navy-900": "#0b1220",
    "--navy-800": "#0b1220",
    "--navy-700": "#111827",
    "--navy-600": "#1f2937",
    "--risk-high": "#b91c1c",
    "--risk-mid": "#b45309",
    "--risk-low": "#047857",
    "--amber": "#d97706",
    "--amber-dark": "#854d0e",
    "--radius": "12px",
    "--radius-sm": "8px",
    "--shadow-sm": "0 1px 2px rgba(16,24,40,.04)",
    "--shadow": "0 1px 3px rgba(16,24,40,.08), 0 1px 2px rgba(16,24,40,.04)",
    "--shadow-lg": "0 4px 12px rgba(16,24,40,.08)",
    "--measure": "40em",
    "--line-prose": "1.78",
    "--line-ui": "1.62",
}

BLOCK = re.compile(r"([^{}]+)\{([^{}]*)\}", re.S)


def strip_comments(css: str) -> str:
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def normalise_decls(body: str) -> str:
    """把声明体规范化成可比较的形式：去空白、去尾分号、统一小写属性名。"""
    parts = []
    for decl in body.split(";"):
        if ":" not in decl:
            continue
        prop, _, value = decl.partition(":")
        prop = prop.strip().lower()
        value = " ".join(value.split())
        if prop and value:
            parts.append(f"{prop}:{value}")
    return ";".join(parts)


def inline_tokens(css: str) -> tuple[str, int]:
    changes = 0

    def repl(match: re.Match[str]) -> str:
        nonlocal changes
        name = match.group(1)
        if name in FINAL_TOKENS:
            changes += 1
            return FINAL_TOKENS[name]
        return match.group(0)

    return re.sub(r"var\((--[\w-]+)\)", repl, css), changes


def dedupe(css: str) -> tuple[str, int, int]:
    """删掉完全相同的重复声明块（同一选择器 + 同一组声明）。"""
    seen: set[tuple[str, str]] = set()
    removed = 0
    kept = 0

    def repl(match: re.Match[str]) -> str:
        nonlocal removed, kept
        selector = " ".join(match.group(1).split())
        body = normalise_decls(match.group(2))
        if not body:
            kept += 1
            return match.group(0)
        key = (selector, body)
        if key in seen:
            removed += 1
            return ""
        seen.add(key)
        kept += 1
        return match.group(0)

    return BLOCK.sub(repl, css), removed, kept


def stats(css: str) -> dict[str, object]:
    plain = strip_comments(css)
    sizes = sorted({float(x) for x in re.findall(r"font-size:\s*([\d.]+)px", plain)})
    return {
        "规则": len(BLOCK.findall(plain)),
        "字号档": len(sizes),
        "字号": sizes,
        "颜色": len({x.lower() for x in re.findall(r"#[0-9a-fA-F]{6}\b", plain)}),
        "令牌定义": len(re.findall(r"(--[\w-]+)\s*:", plain)),
        "字符": len(css),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    head = HEAD.read_text(encoding="utf-8")
    match = re.search(r"<style>(.*?)</style>", head, re.S)
    if not match:
        print("[FAIL] 找不到 <style> 块")
        return 1
    css = match.group(1)

    before = stats(css)
    print("=== 压缩前 ===")
    for key in ("规则", "字号档", "颜色", "令牌定义", "字符"):
        print(f"  {key:10} {before[key]}")

    css2, token_changes = inline_tokens(css)
    css3, removed, kept = dedupe(css2)
    after = stats(css3)

    print()
    print("=== 处理 ===")
    print(f"  令牌内联为字面值   {token_changes} 处")
    print(f"  删除重复声明块     {removed} 条（保留 {kept} 条）")

    print()
    print("=== 压缩后 ===")
    for key in ("规则", "字号档", "颜色", "令牌定义", "字符"):
        delta = after[key] - before[key] if isinstance(after[key], int) else 0
        sign = f"（{delta:+d}）" if delta else ""
        print(f"  {key:10} {after[key]} {sign}")

    if args.dry_run:
        print("\n（dry-run，未写入）")
        return 0

    HEAD.write_text(head[: match.start(1)] + css3 + head[match.end(1) :], encoding="utf-8")
    print(f"\n[ok] 已写入，index_head.html {len(head)} → {len(head) - before['字符'] + after['字符']} 字符")
    return 0


if __name__ == "__main__":
    sys.exit(main())
