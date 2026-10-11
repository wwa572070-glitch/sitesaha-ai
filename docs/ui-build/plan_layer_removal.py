"""在删除 V13/V14 层之前，算出 V15 必须补齐的令牌清单。

方法：
  1) 按当前层叠顺序算出亮色、暗色两套最终令牌表
  2) 只保留 V15 两层，再算一遍
  3) 两套结果做差 —— 有差异的令牌就是 V15 必须补的定义

只读，不改任何文件。
用法：python plan_layer_removal.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
BASE = "index_head.html"

CURRENT_LAYERS = [
    "v13_theme.css", "v14_theme.css", "v13_phases.css", "v13_layout.css",
    "v13_dark.css", "v15_theme.css", "v15_dark.css",
]
KEPT_LAYERS = ["v15_theme.css", "v15_dark.css", "v13_phases.css", "v13_layout.css"]

DECL = re.compile(r"(--[\w-]+)\s*:\s*([^;]+);")
MARKERS = {
    "v13_theme.css": ("/* ===== V13 THEME BEGIN", "/* ===== V13 THEME END"),
    "v14_theme.css": ("/* ===== V14 THEME BEGIN", "/* ===== V14 THEME END"),
    "v15_theme.css": ("/* ===== V15 THEME BEGIN", "/* ===== V15 THEME END"),
    "v13_phases.css": ("/* ===== V13 PHASES BEGIN", "/* ===== V13 PHASES END"),
    "v13_layout.css": ("/* ===== V13 LAYOUT BEGIN", "/* ===== V13 LAYOUT END"),
    "v13_dark.css": ("/* ===== V13 DARK BEGIN", "/* ===== V13 DARK END"),
    "v15_dark.css": ("/* ===== V15 DARK BEGIN", "/* ===== V15 DARK END"),
}


def base_css() -> str:
    text = (BUILD / BASE).read_text(encoding="utf-8")
    return re.search(r"<style>(.*?)</style>", text, re.S).group(1)


def layer_css(name: str) -> str:
    path = BUILD / name
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def scoped_tokens(css: str, scope: str) -> dict[str, str]:
    out: dict[str, str] = {}
    pattern = re.escape(scope) + r"\s*\{(.*?)\}"
    for block in re.findall(pattern, css, re.S):
        for name, value in DECL.findall(block):
            out[name] = " ".join(value.split())
    return out


def resolve(value: str, tokens: dict[str, str], depth: int = 0) -> str:
    if depth > 8:
        return value
    match = re.search(r"var\((--[\w-]+)(?:\s*,\s*([^)]+))?\)", value)
    if not match:
        return value.strip()
    replacement = tokens.get(match.group(1), match.group(2) or "")
    return resolve(value.replace(match.group(0), replacement), tokens, depth + 1)


def build(tokens_layers: list[str], theme: str) -> dict[str, str]:
    """按层顺序算出一套令牌（theme 为空=亮色，'dark'=暗色作用域）。"""
    tokens: dict[str, str] = {}
    scope = ":root" if not theme else f'[data-theme="{theme}"]'
    # 基础层只取亮色 :root（它没有暗色作用域）
    base = scoped_tokens(base_css(), ":root")
    tokens.update(base)
    for name in tokens_layers:
        css = layer_css(name)
        sel = scope if name.endswith("_dark.css") else ":root"
        tokens.update(scoped_tokens(css, sel))
    return tokens


def main() -> int:
    for theme, label in (("", "亮色"), ("dark", "暗色")):
        now = build(CURRENT_LAYERS, theme)
        after = build(KEPT_LAYERS, theme)
        missing = {k: v for k, v in now.items() if k not in after}
        changed = {k for k in now if k in after and now[k] != after[k]}
        print(f"=== {label}主题 ===")
        print(f"  当前令牌 {len(now)} 个 → 只留 V15 后 {len(after)} 个")
        print(f"  会丢失定义：{len(missing)} 个")
        for key in sorted(missing)[:24]:
            print(f"      {key:<22} 当前 {now[key]}")
        if len(missing) > 24:
            print(f"      …… 另有 {len(missing) - 24} 个")
        print(f"  值会改变：{len(changed)} 个 {sorted(changed)[:10]}")
        print()

    # 汇总：两层都缺的令牌必须补
    now_l, after_l = build(CURRENT_LAYERS, ""), build(KEPT_LAYERS, "")
    now_d, after_d = build(CURRENT_LAYERS, "dark"), build(KEPT_LAYERS, "dark")
    need_light = sorted(set(now_l) - set(after_l))
    need_dark = sorted(set(now_d) - set(after_d))
    print("=" * 70)
    print(f"必须在 V15 亮色层补齐：{len(need_light)} 个")
    print("  " + ", ".join(need_light))
    print(f"必须在 V15 暗色层补齐：{len(need_dark)} 个")
    print("  " + ", ".join(need_dark))
    both = sorted(set(need_light) & set(need_dark))
    print(f"\n两层都要补：{len(both)} 个")
    print("  " + ", ".join(both))
    return 0


if __name__ == "__main__":
    sys.exit(main())
