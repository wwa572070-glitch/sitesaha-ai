"""审计现有信息架构：每个视图、每个模块、脚本挂钩点。

按 Taste Skill 第 11.B 节的要求做 redesign 前的现状盘点：
  · 信息架构：页面树、导航、关键路径
  · 内容块：存在什么、哪些在起作用
  · 需要保留的：ID、数据属性、脚本挂钩（动了就功能回归）
  · 需要淘汰的：重复模块、死链、无意义装饰

用法：python audit_ia.py
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

BUILD = Path(__file__).resolve().parent
BODY = BUILD / "index_body.html"
VOID = {"input", "img", "br", "meta", "hr", "source", "link"}


def blocks(text: str, tag: str):
    """以标签深度配对切出所有 <tag ...>…</tag>。"""
    out = []
    for match in re.finditer(rf"<{tag}\b[^>]*>", text):
        depth = 0
        i = match.start()
        while i < len(text):
            nxt = re.search(rf"<(/?){tag}\b[^>]*>", text[i:])
            if not nxt:
                break
            depth += -1 if nxt.group(1) == "/" else 1
            i += nxt.end()
            if depth == 0:
                break
        out.append((match.start(), i, text[match.start():i]))
    return out


def main() -> int:
    body = BODY.read_text(encoding="utf-8")

    print("=" * 78)
    print("一、导航与视图")
    print("=" * 78)
    tabs = re.findall(r'data-view="([^"]+)"[^>]*>(.*?)</button>', body, re.S)
    sections = re.findall(r'<section id="([^"]+)"[^>]*class="([^"]*)"', body)
    print(f"  导航项 {len(tabs)} 个 / 视图 {len(sections)} 个")
    for index, (view, label) in enumerate(tabs, 1):
        clean = re.sub(r"<[^>]+>", "", label).strip()
        print(f"   {index}. {view:<12} 「{clean}」")

    print()
    print("=" * 78)
    print("二、每个视图的内容块")
    print("=" * 78)
    for start, end, chunk in blocks(body, "section"):
        ident = re.search(r'id="([^"]+)"', chunk)
        if not ident:
            continue
        name = ident.group(1)
        panels = blocks(chunk, "div")
        titled = []
        for _s, _e, block in panels:
            if 'class="panel"' not in block[:80]:
                continue
            head = re.search(r"<h2[^>]*>(.*?)</h2>", block, re.S)
            title = re.sub(r"<[^>]+>", "", head.group(1)).strip() if head else "(无标题)"
            titled.append((title, len(block)))
        ids = re.findall(r'id="([^"]+)"', chunk)
        print(f"\n  ▸ #{name}   {len(chunk)} 字符, {len(titled)} 个模块, {len(ids)} 个 id")
        for title, size in titled:
            print(f"      · {title[:40]:<42} {size:>6}")

    print()
    print("=" * 78)
    print("三、脚本挂钩点（动了就会功能回归）")
    print("=" * 78)
    scripts = "\n".join(
        (BUILD / name).read_text(encoding="utf-8")
        for name in ("index_script_a.js", "index_script_b.js")
    )
    body_ids = set(re.findall(r'id="([^"]+)"', body))
    script_ids = set(re.findall(r'\$\("([^"]+)"\)', scripts))
    print(f"  结构里的 id {len(body_ids)} 个；脚本引用 {len(script_ids)} 个")
    missing = sorted(script_ids - body_ids)
    print(f"  脚本引用但结构里没有：{missing if missing else '无'}")
    unused = sorted(body_ids - script_ids)
    print(f"  结构里有但脚本不用：{len(unused)} 个")

    print()
    print("  视图相关的脚本分支：")
    for name in ("showView", "data-view", "dataset.view", "location.hash"):
        hits = len(re.findall(re.escape(name), scripts))
        print(f"    {name:<16} {hits} 处")

    print()
    print("=" * 78)
    print("四、data-* 挂钩（点击跳转等）")
    print("=" * 78)
    attrs = Counter(re.findall(r"(data-[a-z-]+)=", body))
    for attr, n in attrs.most_common():
        print(f"  {attr:<18} {n} 处")

    print()
    print("=" * 78)
    print("五、脚本里引用的视图名（改视图名必须同步）")
    print("=" * 78)
    views = sorted({v for v, _ in tabs})
    for view in views:
        hits = len(re.findall(rf'["\']{re.escape(view)}["\']', scripts))
        print(f"  {view:<14} 脚本里出现 {hits} 次")
    return 0


if __name__ == "__main__":
    sys.exit(main())
