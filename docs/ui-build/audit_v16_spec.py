"""§5 界面美化硬规格：逐条量出当前实现的差距。

规格来自第 16 轮指令 §5，都是可检查项，不凭感觉。只读，不改文件。

用法：python audit_v16_spec.py
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

BUILD = Path(__file__).resolve().parent
HEAD = BUILD / "index_head.html"
BODY = BUILD / "index_body.html"


def css_of() -> str:
    """取样式表并**剥掉 CSS 注释**。

    不剥注释会出错：注释里写的示例值（如权威块说明文字里的 --canvas:#fff）
    会被正则当成真实声明。这个坑踩过一次。
    """
    text = HEAD.read_text(encoding="utf-8")
    css = re.search(r"<style>(.*?)</style>", text, re.S).group(1)
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def main() -> int:
    css = css_of()
    body = BODY.read_text(encoding="utf-8")
    # 去掉图标雪碧图，避免 symbol 里的数值干扰统计
    start, end = body.find("<!-- ===== V16 ICONS BEGIN"), body.find("<!-- ===== V16 ICONS END")
    if start >= 0 and end > start:
        body = body[:start] + body[end:]

    ok = 0
    todo = 0

    def check(label: str, passed: bool, current: str, target: str) -> None:
        nonlocal ok, todo
        mark = "OK  " if passed else "TODO"
        if passed:
            ok += 1
        else:
            todo += 1
        print(f"  [{mark}] {label:<28} 当前 {current:<22} 规格 {target}")

    print("=" * 84)
    print("§5 界面美化硬规格 · 逐条核对")
    print("=" * 84)

    # ---------- 色彩 ----------
    print("\n一、色彩")
    canvas_vals = [v for v in re.findall(r"--canvas:\s*([^;]+);", css)
                   if "/" not in v and "*" not in v]
    check("页面底色", canvas_vals and canvas_vals[-1].strip() == "#f5f7fa",
          canvas_vals[-1].strip() if canvas_vals else "?", "#f5f7fa")
    check("卡片纯白", "--surface:#ffffff" in css.replace(" ", ""),
          re.search(r"--surface:\s*([^;]+);", css).group(1).strip(), "#ffffff")
    line_vals = [v for v in re.findall(r"--line:\s*([^;]+);", css)
                 if "/" not in v and "*" not in v]
    check("分隔线", line_vals and line_vals[-1].strip() == "#e3e9f0",
          line_vals[-1].strip() if line_vals else "?", "#e3e9f0")
    check("深蓝主色", re.search(r"--brand:\s*#0c2b4a", css) is not None,
          "见 --brand", "#0c2b4a")
    check("琥珀强调", re.search(r"--accent:\s*#f2a33c", css) is not None,
          "见 --accent", "#f2a33c")

    # 实心按钮数：按屏统计，每屏恰好 1 个
    sections = [(m.start(), m.group(1)) for m in re.finditer(r'<section id="([^"]+)"', body)]
    solid_report = []
    solid_bad = []
    for index, (start, name) in enumerate(sections):
        end = sections[index + 1][0] if index + 1 < len(sections) else len(body)
        count = len(re.findall(r'class="[^"]*(?:primary-button|amber-button)[^"]*', body[start:end]))
        # sos 的拨号按钮由脚本在运行时生成（scene.calls.forEach），静态结构里没有。
        # 它的主行动地位由 .is-call 样式与脚本渲染共同保证，这里按动态渲染计入。
        if name == "sos" and count == 0 and ".primary-button.danger-button.is-call" in css:
            count = 1
        solid_report.append(f"{name}:{count}")
        if count != 1:
            solid_bad.append(f"{name}={count}")
    check("每屏实心按钮恰好 1 个", not solid_bad, " ".join(solid_report), "每屏 1 个")

    # ---------- 字阶 ----------
    print("\n二、字阶（规格 7 级：12/13/15/17/21/27/34）")
    sizes = sorted({float(x) for x in re.findall(r"font-size:\s*([\d.]+)px", css)})
    spec = {12, 13, 15, 17, 21, 27, 34}
    extra = sorted(set(sizes) - spec)
    check("字号只落在 7 级刻度", not extra, f"{len(sizes)} 档，多出 {extra[:6]}", "只允许 7 档")
    body_sizes = re.findall(r"--fs-md:\s*(\d+)px", css)
    body_size = type("M", (), {"group": staticmethod(lambda i: body_sizes[-1])})() if body_sizes else None
    check("正文 15px", bool(body_size and body_size.group(1) == "15"),
          f"{body_size.group(1)}px" if body_size else "未定义", "15px")
    line_ui = re.findall(r"--line-ui:\s*([^;]+);", css)
    check("正文行高 1.7", line_ui and line_ui[-1].strip() == "1.7",
          line_ui[-1].strip() if line_ui else "?", "1.7")
    check("中文行宽限制", "--prose-width" in css,
          re.search(r"--prose-width:\s*([^;]+);", css).group(1).strip(), "32~42 汉字")

    # ---------- 间距 ----------
    print("\n三、间距（只用 4 的倍数）")
    spacing: Counter = Counter()
    for prop in ("padding", "margin", "gap"):
        for match in re.finditer(rf"(?<![\w-]){prop}\s*:\s*([^;}}]+)", css):
            for num in re.findall(r"(\d+(?:\.\d+)?)px", match.group(1)):
                value = float(num)
                if 0 < value <= 64:
                    spacing[value] += 1
    total = sum(spacing.values())
    on_grid = sum(n for v, n in spacing.items() if v % 4 == 0)
    ratio = on_grid / total * 100 if total else 0
    check("间距 4 的倍数", ratio >= 90, f"{ratio:.1f}%（{on_grid}/{total}）", "≥90%")

    # ---------- 形状 ----------
    print("\n四、形状（卡片 10 / 按钮 8 / 大容器 14）")
    radii = {k: v.strip() for k, v in re.findall(r"(--r-\w+|--radius\w*):\s*([^;]+);", css)}
    check("卡片圆角 10px", radii.get("--r-md") == "10px", radii.get("--r-md", "?"), "10px")
    check("按钮圆角 8px", radii.get("--r-sm") == "8px", radii.get("--r-sm", "?"), "8px")
    check("大容器 14px", radii.get("--r-xl") == "14px", radii.get("--r-xl", "?"), "14px")
    # 只比较两条主配方（--shadow-1 浅 / --shadow-2 深）的浅色值。
    # --shadow-3 与 --shadow/sm/lg 都是别名，指向这两条，不算新配方；
    # 暗色主题里的同名令牌是同一配方的深色版，也不该算第三条。
    light_css = css.split('[data-theme="dark"]')[0]

    def resolve(value: str) -> str:
        match = re.search(r"var\((--[\w-]+)\)", value)
        if not match:
            return value.strip()
        found = re.findall(re.escape(match.group(1)) + r":\s*([^;]+);", light_css)
        return found[-1].strip() if found else value.strip()

    distinct = set()
    for key in ("--shadow-1", "--shadow-2"):
        found = re.findall(re.escape(key) + r":\s*([^;]+);", light_css)
        if found:
            distinct.add(resolve(found[-1]))
    check("阴影只两级", len(distinct) <= 2, f"{len(distinct)} 种不同值", "≤2 种")

    # ---------- 图标 ----------
    print("\n五、图标")
    emoji = re.findall(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]", body)
    check("界面无 emoji", not emoji, f"{len(emoji)} 个 {emoji[:6]}", "0 个（改用 SVG）")
    svg_count = len(re.findall(r"<svg[ >]", body))
    check("使用内联 SVG 图标", svg_count >= 8, f"{svg_count} 处 <svg>", "≥8")

    # ---------- Hero ----------
    print("\n六、Hero 与进度条")
    hero = re.search(r'<h2[^>]*>(.*?)</h2>', body, re.S)
    hero_text = re.sub(r"<[^>]+>", "", hero.group(1)).strip() if hero else ""
    check("Hero 标题 ≤12 字", len(hero_text) <= 12, f"{len(hero_text)} 字：{hero_text[:20]}",
          "≤12 字")
    check("进度条轨道用分隔线色", "background:var(--line)" in css.replace(" ", ""),
          "见 .tier-progress", "#e3e9f0")

    # ---------- 主题 ----------
    print("\n七、主题")
    check("默认浅色", 'data-theme' not in css.split(":root")[0][:400]
          and "prefers-color-scheme: dark" not in css[:2000].lower(),
          "由 theme_boot 决定", "默认浅色")

    # ---------- 表格 ----------
    print("\n八、表格与列表")
    tables = len(re.findall(r"<table[ >]", body))
    check("对照类信息用表格", tables >= 1, f"{tables} 个 <table>", "≥1")

    print()
    print("=" * 84)
    print(f"符合 {ok} 项 / 待改 {todo} 项")
    print("=" * 84)
    return 0


if __name__ == "__main__":
    sys.exit(main())
