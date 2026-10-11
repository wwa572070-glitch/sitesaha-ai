"""把基础层写死的浅色背景/边框换成设计令牌，让暗色主题能统一接管。

根因：基础层有 38 处 background 写成了 #fff / #fbfcfe 这类字面值，
它们不随 :root 令牌变化，所以暗色主题下仍是浅底，
而文字颜色已经变成浅色 → 浅字压浅底，内容看不见（"三件事"标题就是这样消失的）。

做法：把这些字面值替换为语义令牌（--panel / --panel-soft / --line），
再在各主题的 :root 里定义令牌值。这样只需维护一套规则。

用法：python tokenize_surfaces.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
HEAD = BUILD / "index_head.html"
BEGIN = "/* ===== V12 THEME BEGIN ====="

# 只替换基础层（V12 之前）的写死浅色。
# 键是原字面值，值是语义令牌。
SURFACE_TOKENS = {
    "#ffffff": "--panel",
    "#fff": "--panel",
    "#fbfcfe": "--panel-soft",
    "#fafcfe": "--panel-soft",
    "#f8fafc": "--panel-soft",
    "#f6f9fd": "--panel-soft",
    "#ffe4e0": "--line",
    "#ffd9d3": "--line",
    "#eef4fb": "--line",
}

PROPERTIES = ("background", "background-color", "border-color", "border-top-color",
              "border-left-color", "border-bottom-color", "border-right-color")


def tokenize(css: str) -> tuple[str, int]:
    changes = 0

    def replace_decl(match: re.Match[str]) -> str:
        nonlocal changes
        prop = match.group(1)
        value = match.group(2)
        stripped = value.strip().lower()
        # 保留关键帧、渐变、以及带 !important 的写法不动
        if "gradient" in stripped or "url(" in stripped or "inherit" in stripped:
            return match.group(0)
        if stripped not in SURFACE_TOKENS:
            return match.group(0)
        changes += 1
        return f"{prop}:var({SURFACE_TOKENS[stripped]})"

    pattern = re.compile(
        r"\b(" + "|".join(re.escape(p) for p in PROPERTIES) + r")\s*:\s*([^;}]+)",
        re.I,
    )
    return pattern.sub(replace_decl, css), changes


def main() -> int:
    head = HEAD.read_text(encoding="utf-8")
    if BEGIN not in head:
        print("[FAIL] 找不到 V12 分界标记")
        return 1

    base, rest = head.split(BEGIN, 1)
    base_new, changes = tokenize(base)
    print(f"[ok] 基础层替换 {changes} 处写死颜色为令牌")

    HEAD.write_text(base_new + BEGIN + rest, encoding="utf-8")
    print(f"index_head.html：{len(head)} → {len(base_new) + len(BEGIN) + len(rest)} 字符")

    leftover = re.findall(
        r"\bbackground(?:-color)?\s*:\s*(#f{3,6}|#ffffff)\b", base_new, re.I
    )
    if leftover:
        print(f"[注意] 基础层仍有 {len(leftover)} 处白色背景未替换：{set(leftover)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
