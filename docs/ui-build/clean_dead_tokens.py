"""清理基础层里的死令牌定义，让设计基线提取只看到真实生效的值。

问题（design-baseline 提取不准的根因）：
  index_head.html 的基础层是 V10 时代留下的，里面定义了一整套旧令牌
  （--navy-800: #0c2b4a、--amber: #f2a33c、--radius: 10px …）。
  V13/V14 层后来重定义了同名令牌，最终生效的是新值，
  但基础层的声明仍在文件里，于是提取器按文件顺序取到旧值 —— 所以草稿里
  primary 是 #123a61、圆角是 10px/7px，全都不对。

做法：
  1) 按注入顺序（基础层 → V13 → V13phases → V13layout → V14 → 暗色）算出每个令牌的最终值
  2) 删掉"基础层里定义了、但被后续层覆盖成不同值"的令牌声明
  3) 保留只在基础层定义（后续层没重定义）的令牌 —— 它们仍在生效

用法：python clean_dead_tokens.py [--dry-run]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
HEAD = BUILD / "index_head.html"

LAYER_FILES = [
    "v13_theme.css",
    "v13_phases.css",
    "v13_layout.css",
    "v14_theme.css",
    "v13_dark.css",
]

DECL = re.compile(r"(--[\w-]+)\s*:\s*([^;]+);")


def tokens_in(css: str, scope: str = ":root") -> dict[str, str]:
    """取某个作用域里的令牌定义（scope 为 ':root' 或 '[data-theme="dark"]'）。"""
    out: dict[str, str] = {}
    for block in re.findall(re.escape(scope) + r"\s*\{(.*?)\}", css, re.S):
        for name, value in DECL.findall(block):
            out[name] = " ".join(value.split())
    return out


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

    # 基础层 = 第一个 V13 标记之前的部分
    marker = css.find("/* ===== V13 THEME BEGIN")
    if marker < 0:
        print("[FAIL] 找不到 V13 起点，无法区分基础层")
        return 1
    base, layers_css = css[:marker], css[marker:]

    base_tokens = tokens_in(base)
    print(f"基础层定义令牌 {len(base_tokens)} 个")

    # 依次叠加后续层，得到最终值
    final: dict[str, str] = dict(base_tokens)
    for name in LAYER_FILES:
        path = BUILD / name
        if not path.is_file():
            continue
        file_css = path.read_text(encoding="utf-8")
        for key, value in tokens_in(file_css).items():
            final[key] = value
    print(f"叠加后续层后，最终生效令牌 {len(final)} 个")

    # 死定义 = 基础层里有、但最终值不同
    dead = {k: v for k, v in base_tokens.items() if k in final and final[k] != v}
    alive = {k: v for k, v in base_tokens.items() if k not in dead}
    print()
    print(f"基础层死定义（被覆盖成别的值）：{len(dead)} 个")
    for key in sorted(dead)[:20]:
        print(f"    {key:<22} 基础层 {dead[key]:<24} → 最终 {final[key]}")
    if len(dead) > 20:
        print(f"    …… 另有 {len(dead) - 20} 个")
    print()
    print(f"基础层仍生效的令牌：{len(alive)} 个")

    if not dead:
        print("\n没有死定义，无需清理")
        return 0

    # 从基础层的 :root 块里删掉死定义
    removed = 0

    def strip_dead(block_match: re.Match[str]) -> str:
        nonlocal removed
        body = block_match.group(1)
        lines = []
        for decl in body.split(";"):
            m = re.match(r"\s*(--[\w-]+)\s*:", decl)
            if m and m.group(1) in dead:
                removed += 1
                continue
            lines.append(decl)
        return ":root {" + ";".join(lines) + "}"

    base_new = re.sub(r":root\s*\{(.*?)\}", strip_dead, base, flags=re.S)
    print(f"\n从基础层删除死令牌声明 {removed} 条")

    if args.dry_run:
        print("（dry-run，未写入）")
        return 0

    head_new = head[: match.start(1)] + base_new + layers_css + head[match.end(1):]
    HEAD.write_text(head_new, encoding="utf-8")
    print(f"index_head.html {len(head)} → {len(head_new)} 字符")

    # 自检：最终令牌值不能变
    css2 = re.search(r"<style>(.*?)</style>", head_new, re.S).group(1)
    marker2 = css2.find("/* ===== V13 THEME BEGIN")
    base2 = css2[:marker2]
    final2 = dict(tokens_in(base2))
    for name in LAYER_FILES:
        path = BUILD / name
        if path.is_file():
            final2.update(tokens_in(path.read_text(encoding="utf-8")))
    changed = {k for k in final if final.get(k) != final2.get(k)}
    if changed:
        print(f"[FAIL] 清理改变了最终令牌值：{sorted(changed)[:10]}")
        return 1
    print(f"[ok] 最终令牌值未变（{len(final)} 个），仅删除了被覆盖的死定义")
    return 0


if __name__ == "__main__":
    sys.exit(main())
