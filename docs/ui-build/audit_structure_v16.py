"""§0.1 结构统计：为第 16 轮改造提供事实基线。

只读，不改任何文件。
统计：视图数、panel 数、h1-h4 分布、图形元素、@keyframes 与 transition 数、
每个区块的标题清单。
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

BUILD = Path(__file__).resolve().parent
BODY = BUILD / "index_body.html"
HEAD = BUILD / "index_head.html"
JS = (BUILD / "index_script_a.js").read_text(encoding="utf-8") + \
     (BUILD / "index_script_b.js").read_text(encoding="utf-8")

VIEWS = ["home", "ask", "sos", "pre", "learn"]


def strip_tags(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", text)).strip()


def main() -> int:
    body = BODY.read_text(encoding="utf-8")
    head = HEAD.read_text(encoding="utf-8")
    css = re.search(r"<style>(.*?)</style>", head, re.S).group(1)

    print("=" * 78)
    print("一、视图与区块")
    print("=" * 78)
    sections = re.findall(r'<section id="([^"]+)"[^>]*class="([^"]*)"', body)
    print(f"  视图数：{len(sections)}  →  {', '.join(s for s, _ in sections)}")
    print(f"  .panel 容器数：{len(re.findall(r'class=\"panel[ \"]', body))}")
    print(f"  .panel-head 数：{body.count('panel-head')}")
    print(f"  .phase 分组数：{len(re.findall(r'class=\"phase\"', body))}")

    print()
    print("=" * 78)
    print("二、标题层级分布（全站）")
    print("=" * 78)
    headings: Counter = Counter()
    for level in (1, 2, 3, 4, 5, 6):
        n = len(re.findall(rf"<h{level}[ >]", body))
        headings[f"h{level}"] = n
    for level, n in headings.items():
        bar = "█" * min(50, n)
        print(f"  {level}: {n:>3}  {bar}")
    total = sum(headings.values())
    print(f"  合计 {total} 个")
    used = [k for k, v in headings.items() if v]
    print(f"  实际用到的层级：{', '.join(used)}  →  {len(used)} 档")

    print()
    print("=" * 78)
    print("三、图形元素（当前）")
    print("=" * 78)
    graphics = {
        "内联 <svg>": len(re.findall(r"<svg[ >]", body)),
        "<canvas>": len(re.findall(r"<canvas[ >]", body)),
        "<img>": len(re.findall(r"<img[ >]", body)),
        "<table>": len(re.findall(r"<table[ >]", body)),
        "进度条 .progress-track": body.count("progress-track"),
        "分布条 .domain-bar": body.count("domain-bar"),
        "步骤 .em-step": body.count("em-step"),
        "复选框 input[checkbox]": len(re.findall(r'type="checkbox"', body)),
    }
    for name, n in graphics.items():
        print(f"  {name:<26} {n}")
    print(f"  → 图表类元素合计：{graphics['内联 <svg>'] + graphics['<canvas>'] + graphics['<table>']}")

    print()
    print("=" * 78)
    print("四、动效")
    print("=" * 78)
    keyframes = re.findall(r"@keyframes\s+([\w-]+)", css)
    print(f"  @keyframes：{len(keyframes)} 个  →  {', '.join(keyframes)}")
    print(f"  transition 声明：{len(re.findall(r'transition\s*:', css))}")
    print(f"  animation 声明：{len(re.findall(r'animation\s*:', css))}")
    print(f"  prefers-reduced-motion 处理：{css.count('prefers-reduced-motion')} 处")
    names = re.findall(r"transition\s*:\s*([^;}]+)", css)
    props = Counter()
    for item in names:
        for prop in re.findall(r"[a-z-]+(?=\s*[\d.])", item):
            props[prop] += 1
    print(f"  过渡属性分布：{dict(props.most_common(8))}")

    print()
    print("=" * 78)
    print("五、每个视图的区块标题清单")
    print("=" * 78)
    # 按 section 切分
    positions = [(m.start(), m.group(1)) for m in re.finditer(r'<section id="([^"]+)"', body)]
    for index, (start, name) in enumerate(positions):
        end = positions[index + 1][0] if index + 1 < len(positions) else len(body)
        seg = body[start:end]
        print(f"\n  ── #{name}  ({len(seg)} 字符) ──")
        for m in re.finditer(r"<h([1-4])[^>]*>(.*?)</h\1>", seg, re.S):
            title = strip_tags(m.group(2))
            if title:
                print(f"     h{m.group(1)}  {title}")
        panels = len(re.findall(r'class="panel[ "]', seg))
        print(f"     （该视图含 {panels} 个 panel）")

    print()
    print("=" * 78)
    print("六、跨视图跳转按钮（IA 未收敛的信号）")
    print("=" * 78)
    jumps = re.findall(r'<button[^>]*>(打开[^<]*|全部[^<]*案例[^<]*|全部[^<]*培训[^<]*|查看[^<]*→)</button>', body)
    for text in jumps:
        print(f"  「{text.strip()}」")
    print(f"  合计 {len(jumps)} 个")
    if not jumps:
        print("  无")

    print()
    print("=" * 78)
    print("七、配置状态（拍照/语音是否可用）")
    print("=" * 78)
    webapp = (BUILD.parent.parent / "webapp.py").read_text(encoding="utf-8")
    for flag in ["vision_configured", "asr_configured", "model_configured"]:
        print(f"  {flag:<22} 在 webapp.py 中出现 {webapp.count(flag)} 次")
    print("  （实际值需请求 /healthz 读取）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
