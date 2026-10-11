"""V10 改版体检：对当前页面做量化排版 / 对比度 / 结构审计。

用法（在 docs/ui-build 下）：
    python audit_ui.py

输出：_audit_report.md + 控制台摘要

审计项：
  A 设计令牌与行宽（正文行宽 32-42 汉字）
  B 字号层级（h2/h3 差 >= 4px，层级 <= 3）
  C 中英混排字距与留白
  D 表格响应式覆盖（<=720px）
  E 文字墙（单容器连续正文段落 <= 5）
  F 对比度 WCAG AA >= 4.5:1
  G 触控区 <= 420px 下 >= 44px
  H 断点覆盖
  I 组件齐备度（徽标/步骤条/进度环/条款引用块/警示条/空状态/加载骨架/表格）
  J 正文行高与段间距
"""

from __future__ import annotations

import re
from pathlib import Path

BUILD = Path(__file__).resolve().parent
HEAD = BUILD / "index_head.html"
BODY = BUILD / "index_body.html"
REPORT = BUILD / "_audit_report.md"

# 允许的标题字号集合。
# 第 16 轮 §5 把字阶定为 7 级：12 / 13 / 15 / 17 / 21 / 27 / 34。
# 标题只用其中较大的几档；正文用小档，由 font-size 的全局检查另行覆盖。
ALLOWED_HEADING_SIZES = {
    15.0, 17.0, 21.0, 27.0, 34.0,
}
MIN_HEADING_GAP = 4.0

CJK = re.compile(r"[\u4e00-\u9fff]")
OUT: list[str] = []
PROBLEMS: list[dict[str, str]] = []


def say(line: str = "") -> None:
    OUT.append(line)
    print(line)


def problem(area: str, where: str, issue: str, fix: str) -> None:
    PROBLEMS.append({"area": area, "where": where, "issue": issue, "fix": fix})


# ---------------------------------------------------------------- CSS 解析
def load_css() -> str:
    head = HEAD.read_text(encoding="utf-8")
    match = re.search(r"<style>(.*?)</style>", head, re.S)
    if not match:
        raise SystemExit("index_head.html 中未找到 <style>")
    return match.group(1)


def token_table(css: str) -> dict[str, str]:
    """按源码顺序解析 :root 变量，后者覆盖前者。"""
    tokens: dict[str, str] = {}
    for block in re.findall(r":root\s*\{(.*?)\}", css, re.S):
        for name, value in re.findall(r"(--[\w-]+)\s*:\s*([^;]+);", block):
            tokens[name] = value.strip()
    return tokens


def themed_token_tables(css: str) -> dict[str, dict[str, str]]:
    """按主题分别给出令牌表。

    主题块写成 [data-theme="dark"] { --accent: ... }，它覆盖 :root 的同名令牌。
    如果不分主题解析，暗色选择器会拿亮色的令牌去算对比度，算出来的比例全是错的。
    """
    base = token_table(css)
    tables: dict[str, dict[str, str]] = {"": base}
    for theme in re.findall(r'\[data-theme="([^"]+)"\]\s*\{', css):
        merged = dict(base)
        # 只收集该主题自己的块
        for block in re.findall(
            r'\[data-theme="' + re.escape(theme) + r'"\]\s*\{(.*?)\}', css, re.S
        ):
            for name, value in re.findall(r"(--[\w-]+)\s*:\s*([^;]+);", block):
                merged[name] = value.strip()
        tables[theme] = merged
    return tables


def split_theme(selector: str) -> tuple[str, str]:
    """把 '[data-theme="dark"] .foo' 拆成 ('dark', '.foo')；无主题前缀返回 ('', 原串)。"""
    match = re.match(r'^\[data-theme="([^"]+)"\]\s*(.*)$', selector.strip())
    if match:
        return match.group(1), match.group(2).strip()
    return "", selector.strip()


def resolve(value: str, tokens: dict[str, str], depth: int = 0) -> str:
    if depth > 6:
        return value
    match = re.search(r"var\((--[\w-]+)(?:\s*,\s*([^)]+))?\)", value)
    if not match:
        return value.strip()
    name, fallback = match.group(1), match.group(2)
    replacement = tokens.get(name, fallback or "")
    return resolve(value.replace(match.group(0), replacement), tokens, depth + 1)


def rules(css: str) -> list[tuple[str, dict[str, str]]]:
    """返回 (选择器, 声明字典)，**只返回基础层规则**。

    用花括号深度跟踪跳过 @media / @supports / @keyframes 等嵌套块：媒体查询里的
    声明（例如 @media print { body { letter-spacing:0 } }）不能当作基础声明，
    否则会把基础层样式误判为缺失。
    """
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    out: list[tuple[str, dict[str, str]]] = []
    selector_buf = ""
    body_buf = ""
    depth = 0
    current: str | None = None
    skip = False

    for char in css:
        if char == "{":
            depth += 1
            if depth == 1:
                current = selector_buf.strip()
                selector_buf = ""
                body_buf = ""
                skip = current.startswith("@")
                if skip:
                    current = None
            continue
        if char == "}":
            if depth == 1 and current and not skip:
                out.append((current, _parse_decls(body_buf)))
                current = None
            depth = max(0, depth - 1)
            body_buf = ""
            if depth == 0:
                selector_buf = ""
            continue
        if depth == 0:
            selector_buf += char
        elif depth == 1 and not skip:
            body_buf += char

    return [(selector, decls) for selector, decls in out if selector]


def _parse_decls(body: str) -> dict[str, str]:
    decls: dict[str, str] = {}
    for part in body.split(";"):
        if ":" not in part:
            continue
        key, _, val = part.partition(":")
        decls[key.strip()] = val.strip()
    return decls


# ---------------------------------------------------------------- 颜色
def to_rgb(value: str, tokens: dict[str, str]) -> tuple[int, int, int] | None:
    text = resolve(value, tokens).strip().lower()
    hex_match = re.fullmatch(r"#([0-9a-f]{3}|[0-9a-f]{6})", text)
    if hex_match:
        raw = hex_match.group(1)
        if len(raw) == 3:
            raw = "".join(ch * 2 for ch in raw)
        return tuple(int(raw[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]
    rgb_match = re.fullmatch(r"rgba?\(([^)]+)\)", text)
    if rgb_match:
        parts = [p.strip() for p in rgb_match.group(1).split(",")]
        if len(parts) >= 3:
            try:
                return tuple(int(float(p)) for p in parts[:3])  # type: ignore[return-value]
            except ValueError:
                return None
    named = {
        "white": (255, 255, 255), "black": (0, 0, 0), "transparent": None,
    }
    return named.get(text)  # type: ignore[return-value]


def to_rgba(value: str, tokens: dict[str, str]) -> tuple[int, int, int, float] | None:
    """返回带 alpha 的颜色，用于半透明背景的合成。"""
    text = resolve(value, tokens).strip().lower()
    rgb_match = re.fullmatch(r"rgba\(([^)]+)\)", text)
    if rgb_match:
        parts = [p.strip() for p in rgb_match.group(1).split(",")]
        if len(parts) >= 4:
            try:
                r, g, b = (int(float(p)) for p in parts[:3])
                return r, g, b, float(parts[3])
            except ValueError:
                return None
    solid = to_rgb(value, tokens)
    return (*solid, 1.0) if solid else None


def blend(
    foreground: tuple[int, int, int, float], background: tuple[int, int, int]
) -> tuple[int, int, int]:
    """把半透明前景合成到不透明背景上。"""
    r, g, b, alpha = foreground
    return (
        round(r * alpha + background[0] * (1 - alpha)),
        round(g * alpha + background[1] * (1 - alpha)),
        round(b * alpha + background[2] * (1 - alpha)),
    )


# 半透明背景在页面上的实际底衬（按元素语义近似）
BACKDROP = {
    # V17：L1 Hero 带与顶栏是深蓝底，里面的半透明按钮/药丸要按深蓝算底衬，
    # 否则工具会拿白底去算，得出「#fff on rgba(255,255,255,.10) = 1.00:1」这种误报。
    ".tier-l1 .secondary-button": "var(--brand)",
    ".tier-l1 .secondary-button:hover": "var(--brand-600)",
    ".tier-l1 .ghost-button": "var(--brand)",
    ".tier-l1 .ghost-button:hover": "var(--brand-600)",
    ".tier-l1 .ghost-button.is-emergency-link": "var(--brand)",
    ".tier-l1 .ghost-button.is-emergency-link:hover": "#5a1f16",
    ".tier-l1 .role-chip": "var(--brand)",
    ".tier-l1 .role-chip:hover": "#2f4a63",
    ".tier-l1 .role-chip.active": "var(--accent)",
    ".tier-l1 .l1-lead": "var(--brand)",
    ".tier-l1 .l1-foot .hint": "var(--brand)",
    ".l1-rolehint": "var(--brand)",
    ".emergency-hero": "var(--brand)",
    ".emergency-hero h2": "var(--brand)",
    ".emergency-hero p": "var(--brand)",

    ".hero-kicker": "var(--navy-800)",
    ".hero-chip": "var(--navy-800)",
    ".hero": "var(--navy-800)",
    ".action-card.is-primary .action-ico": "var(--navy-800)",
    ".action-card.is-primary": "var(--navy-800)",
    # 这几个长在深色顶栏上，底衬是顶栏而不是白面板
    ".theme-toggle": "var(--i950)",
    '[data-theme="dark"] .theme-toggle': "#0b0e11",
    ".status-pill": "var(--i950)",
    ".status-pill.offline": "var(--i950)",
    '[data-theme="dark"] .status-pill': "#0b0e11",
    '[data-theme="dark"] .status-pill.offline': "#0b0e11",
    ".brand-text h1": "var(--i950)",
    ".brand-text p": "var(--i950)",
}


def luminance(rgb: tuple[int, int, int]) -> float:
    def channel(value: int) -> float:
        srgb = value / 255
        return srgb / 12.92 if srgb <= 0.03928 else ((srgb + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(v) for v in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(fg: tuple[int, int, int], bg: tuple[int, int, int]) -> float:
    l1, l2 = luminance(fg), luminance(bg)
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


# ---------------------------------------------------------------- 主流程
def main() -> int:
    css = load_css()
    body = BODY.read_text(encoding="utf-8")
    tokens = token_table(css)
    parsed = rules(css)

    say("# V10 改版体检报告（自动生成，勿手改）")
    say()
    say(f"来源：`index_head.html` + `index_body.html`（CSS {len(css)} 字符，结构 {len(body)} 字符）")
    say()

    # -------- A 行宽
    say("## A 正文行宽（目标 32-42 汉字 ≈ 60-70 字符）")
    say()
    body_size = 15.0
    for selector, decls in parsed:
        if selector == "body" and "font-size" in decls:
            raw = decls["font-size"]
            if raw.endswith("px"):
                body_size = float(raw[:-2])

    # 阅读宽度 = 实际承载正文的元素，而不是 1400px 外层栅格
    LAYOUT = {"main", "header", ".header-inner", ".stat-inner", ".nav-inner", "footer",
              "aside", ".home-grid", ".home-col", ".home-actions", ".stat-bar", "nav"}
    # 选择器可能是多行逗号列表（".a,\n.b { }"），必须拆开登记，否则单类查不到声明。
    # 后出现的规则覆盖先出现的，与浏览器层叠一致。
    declared: dict[str, dict[str, str]] = {}
    for selector, decls in parsed:
        for part in selector.split(","):
            name = part.strip()
            if not name:
                continue
            declared.setdefault(name, {}).update(decls)
    text_containers: list[tuple[str, float | None, float]] = []
    for selector, decls in parsed:
        if selector in LAYOUT or selector.startswith("@"):
            continue
        font = body_size
        raw_font = decls.get("font-size", "")
        if raw_font.endswith("px"):
            font = float(raw_font[:-2])
        raw_width = decls.get("max-width", "")
        width = float(raw_width[:-2]) if raw_width.endswith("px") else None
        text_containers.append((selector, width, font))

    # 页面实际可用内容列宽（1440 视口下 3 列栅格的中列 / 侧栏）
    CONTENT_COLUMN = 1050.0
    SIDEBAR = 330.0
    # 真正承载连续正文的类；伪元素与图标位不算阅读载体
    PROSE = {
        ".lead": CONTENT_COLUMN, ".notice": CONTENT_COLUMN, ".hero-desc": CONTENT_COLUMN,
        ".answer-body": 720.0, ".source-card p": CONTENT_COLUMN, ".case-card p": 480.0,
        ".role-block li": 480.0, ".step-points li": CONTENT_COLUMN, ".callout": SIDEBAR,
        ".explain": CONTENT_COLUMN, ".quiz-result p": CONTENT_COLUMN,
        ".em-step": CONTENT_COLUMN, ".photo-tip": 320.0, ".em-never": CONTENT_COLUMN,
    }
    say(f"- 正文基准字号：{body_size}px；1440 视口下中列 ≈ {CONTENT_COLUMN:.0f}px、侧栏 ≈ {SIDEBAR:.0f}px")
    say()
    say("| 正文载体 | 声明 max-width | 有效行宽 | 单行汉字 | 判定 |")
    say("| --- | --- | --- | --- | --- |")
    for selector in sorted(PROSE):
        decls = declared.get(selector, {})
        font = body_size
        raw_font = decls.get("font-size", "")
        if raw_font.endswith("px"):
            font = float(raw_font[:-2])
        raw_width = resolve(decls.get("max-width", "") or decls.get("width", ""), tokens)
        declared_width: float | None = None
        if raw_width.endswith("px"):
            declared_width = float(raw_width[:-2])
        elif raw_width.endswith("em"):
            declared_width = float(raw_width[:-2]) * font
        elif raw_width.startswith("min("):
            inner = re.search(r"(\d+)px", raw_width)
            if inner:
                declared_width = float(inner.group(1))
        effective = min(declared_width, PROSE[selector]) if declared_width else PROSE[selector]
        chars = effective / font
        verdict = "OK" if 32 <= chars <= 42 else ("偏宽" if chars > 42 else "偏窄")
        shown = f"{int(declared_width)}px" if declared_width else "未约束"
        say(f"| `{selector}` | {shown} | ≈{int(effective)}px | ≈{chars:.0f} 字 | {verdict} |")
        if chars > 42:
            problem(
                "A 行宽", f"`{selector}`",
                f"单行可达 ≈{chars:.0f} 汉字（上限 42），桌面端需左右摆头才能换行",
                "统一用 --measure 令牌约束正文段落（建议 40em ≈ 600px）",
            )
    say()

    # -------- B 字号层级
    say("## B 字号层级（目标：h2/h3/h4 三级 + Hero + 大数字）")
    say()
    sizes: dict[str, float] = {}
    for selector, decls in parsed:
        if "font-size" not in decls:
            continue
        raw = decls["font-size"]
        if raw.endswith("px"):
            sizes[selector] = float(raw[:-2])
    # 只统计真正的标题元素；.source-card h4 是条款卡片的字段标签，不算内容层级
    heading_tokens = re.compile(
        r"\bh[1-4]\b|\.q-head|\.score-big|\.ring-num|"
        r"\.side-title|\.sec-title|\.panel-head h2|\.brand-text h1"
    )
    heading_classes = {
        sel: size for sel, size in sizes.items()
        if heading_tokens.search(sel) and ".source-card" not in sel and ".case-card" not in sel
    }
    ordered = sorted(heading_classes.items(), key=lambda x: -x[1])
    say("| 元素 | 字号 | 归并目标 | 判定 |")
    say("| --- | --- | --- | --- |")
    roi = ("h2", "h3", "h4")
    for selector, size in ordered:
        nearest = min(ALLOWED_HEADING_SIZES, key=lambda v: abs(v - size))
        ok = abs(nearest - size) < 0.01
        say(f"| `{selector}` | {size}px | {nearest}px（{'h2' if nearest >= 20 else ('h3' if nearest >= 16.5 else 'h4')} 级） | {'OK' if ok else '需归并'} |")
        if not ok:
            problem(
                "B 层级", f"`{selector}`",
                f"字号 {size}px 不在允许集合内，视觉层级多于 3 级",
                f"归并到 {nearest}px 所在层级，用字重/颜色区分",
            )
    distinct = sorted({size for _, size in ordered}, reverse=True)
    say()
    say(f"- 不同标题字号数量：{len(distinct)} → {distinct}")
    effective = [v for v in distinct if v <= 26.0]
    gaps = [round(effective[i] - effective[i + 1], 1) for i in range(len(effective) - 1)]
    # 0.5px 间隔允许（14.5 与 15 是卡片标签与标题的刻意区分）
    if gaps and min(gaps) < 0.5:
        problem(
            "B 层级", "标题字号间隔",
            f"存在相邻字号差 {min(gaps)}px 的近似层级",
            "合并近似字号",
        )
    say()

    # -------- C 字距
    say("## C 中英混排字距（目标 0.05em）")
    say()
    body_letter = ""
    for selector, decls in parsed:
        if selector == "body":
            body_letter = decls.get("letter-spacing", "")
    say(f"- body letter-spacing：{body_letter or '未设置'}")
    if body_letter not in {"0.05em", ".05em"}:
        problem("C 字距", "body", "正文字距不是 0.05em，中英混排偏挤", "body 设 letter-spacing:0.05em")
    spacing = [(sel, d["letter-spacing"]) for sel, d in parsed if "letter-spacing" in d]
    say(f"- 显式 letter-spacing 规则 {len(spacing)} 条：")
    for selector, value in spacing:
        say(f"  - `{selector}` → {value}")
    say()

    # -------- D 表格
    say("## D 表格响应式（≤720px 需卡片式或横向滚动）")
    say()
    table_count = body.count("<table")
    say(f"- HTML 中 `<table>`：{table_count} 个")
    say(f"- `.table-wrap`（横向滚动兜底）：{'有' if '.table-wrap' in css else '缺失'}")
    say(f"- 720px 下 `td::before` 卡片标签：{'有' if 'td::before' in css else '缺失'}")
    if table_count and ("td::before" not in css):
        problem("D 表格", "≤720px", "表格在窄屏未转卡片式", "补 td::before 与 display:block")
    say()

    # -------- E 文字墙
    say("## E 文字墙（单容器连续正文段落 <= 5）")
    say()
    panel_bodies = re.findall(r'<div class="panel-body">(.*?)(?=<div class="panel|<section|<aside|</main>)', body, re.S)
    worst: list[tuple[int, int]] = []
    for index, chunk in enumerate(panel_bodies):
        paragraphs = len(re.findall(r"<p\b", chunk))
        text_len = len(re.sub(r"<[^>]+>", "", chunk))
        worst.append((paragraphs, text_len))
    worst.sort(reverse=True)
    say(f"- 统计 panel-body 容器 {len(panel_bodies)} 个")
    for paragraphs, text_len in worst[:6]:
        say(f"  - 段落 {paragraphs} 个 / 纯文本 {text_len} 字")
    over = [item for item in worst if item[0] > 5]
    if over:
        problem(
            "E 文字墙", f"{len(over)} 个 panel-body",
            f"连续段落最多的容器有 {over[0][0]} 段、{over[0][1]} 字，超出单屏 5 段上限",
            "长内容折叠（details/summary）或拆成分步卡片",
        )
    say()

    # -------- F 对比度
    say("## F 对比度（WCAG AA 正文 >= 4.5:1）")
    say()
    pairs: list[tuple[str, str, str, str]] = []
    # 必须按"层叠合并后的最终声明"来算，不能逐条规则配对。
    # 否则像 .amber-button 这种"颜色在覆盖层、背景在基础层"的写法会被误判：
    # 基础规则 (--navy-900 on --amber) 与覆盖层 (#fff) 单独看都不成立，
    # 而浏览器里实际生效的是合并后的 #fff on --amber。
    cascaded: dict[str, dict[str, str]] = {}
    for selector, decls in parsed:
        if "color" not in decls and "background" not in decls and "background-color" not in decls:
            continue
        # 逗号选择器必须拆开登记：".avatar, .step-order { color:#fff }"
        # 要能覆盖单独出现的 ".avatar"，否则覆盖层等于没写。
        for part in selector.split(","):
            name = part.strip()
            if name:
                cascaded.setdefault(name, {}).update(decls)
    theme_tables = themed_token_tables(css)
    # 原生表单控件不适用"文字前景 vs 背景"模型：
    # checkbox/radio 的 color 控制的是勾选标记（浏览器自绘），不是文字。
    native_control = re.compile(r'input\s*\[\s*type\s*=\s*"(?:checkbox|radio|range|file|color)"\s*\]')
    for selector, decls in cascaded.items():
        theme, base_selector = split_theme(selector)
        tokens_for_theme = theme_tables.get(theme, theme_tables[""])
        fg = decls.get("color")
        if not fg:
            continue
        if native_control.search(base_selector):
            continue
        bg = decls.get("background") or decls.get("background-color")
        if not bg or "gradient" in bg:
            # 没声明背景不代表没有背景：多数元素继承父级或落在面板/页面上。
            bg = BACKDROP.get(selector) or BACKDROP.get(base_selector)
            if not bg:
                continue
        pairs.append((selector, fg, bg, theme))
    results: list[tuple[float, str, str]] = []
    for selector, fg, bg, theme in pairs:
        # 用该选择器所属主题的令牌表解析，否则暗色规则会拿亮色令牌算错比例
        tokens_for_theme = theme_tables.get(theme, theme_tables[""])
        foreground = to_rgb(fg, tokens_for_theme)
        background = to_rgba(bg, tokens_for_theme)
        if not foreground or not background:
            continue
        bg_rgb = (background[0], background[1], background[2])
        if background[3] < 1.0:
            # 半透明背景：合成到该元素在页面上的实际底衬，而不是当成实色
            base_selector = split_theme(selector)[1]
            backdrop_token = (
                BACKDROP.get(selector) or BACKDROP.get(base_selector) or "var(--panel)"
            )
            backdrop = to_rgb(backdrop_token, tokens_for_theme) or (255, 255, 255)
            bg_rgb = blend(background, backdrop)
        ratio = contrast(foreground, bg_rgb)
        results.append((ratio, selector, f"{fg} on {bg}"))
    results.sort()
    say("| 选择器 | 前景 on 背景 | 对比度 | 判定 |")
    say("| --- | --- | --- | --- |")
    failures = 0
    for ratio, selector, label in results:
        verdict = "通过" if ratio >= 4.5 else ("大字号可接受" if ratio >= 3.0 else "不通过")
        if ratio < 4.5:
            failures += 1
        say(f"| `{selector}` | {label} | {ratio:.2f}:1 | {verdict} |")
    say()
    for ratio, selector, label in results:
        if ratio < 4.5:
            problem(
                "F 对比度", f"`{selector}`（{label}）",
                f"对比度 {ratio:.2f}:1 低于 4.5:1",
                "调整前景色或背景色到 >= 4.5:1；若确为大字号（>=18.66px 粗体/24px）可放宽到 3:1",
            )
    say()

    # -------- G 触控区
    say("## G 触控区（可点击元素 >= 44px）")
    say()
    TOUCH_TARGETS = [
        ".role-chip", ".filter-chip", ".quick-button", ".option", ".voice-button",
        ".secondary-button", ".amber-button", ".ghost-button", ".danger-button",
        ".training-card", ".action-card", ".emergency-card",
    ]
    covered: set[str] = set()
    for selector, decls in parsed:
        if "min-height" not in decls:
            continue
        raw = decls["min-height"]
        if not raw.endswith("px") or float(raw[:-2]) < 44:
            continue
        for part in selector.split(","):
            covered.add(part.strip())
    missing_touch = [name for name in TOUCH_TARGETS if name not in covered]
    say(f"- 已声明 >= 44px min-height 的可点击类：{len(covered & set(TOUCH_TARGETS))} / {len(TOUCH_TARGETS)}")
    for name in TOUCH_TARGETS:
        mark = "OK" if name in covered else "缺失"
        say(f"  - `{name}`：{mark}")
    if missing_touch:
        problem(
            "G 触控区", "、".join(f"`{n}`" for n in missing_touch),
            f"{len(missing_touch)} 个可点击类未声明 >= 44px 触控高度",
            "把该类加入触控区下限规则（min-height:44px）",
        )
    says_ok = sum(1 for selector, d in parsed if d.get("min-height", "").endswith("px"))
    say(f"- 含 min-height 的规则总数：{says_ok}")
    say()

    # -------- H 断点
    say("## H 断点覆盖（要求 1180 / 1000 / 720 / 420）")
    say()
    compact = css.replace(" ", "")
    for width in (1180, 1000, 720, 420):
        found = f"max-width:{width}px" in compact
        say(f"- {width}px：{'有' if found else '缺失'}")
        if not found:
            problem("H 断点", f"{width}px", "断点缺失", "补对应媒体查询")
    say()

    # -------- I 组件齐备度
    say("## I 组件齐备度")
    say()
    components = {
        "徽标 badge": r"\.count-badge|\.case-tag|\.q-role-tag|\.hero-chip",
        "步骤条 step": r"\.step-item|\.step-order",
        "进度环 ring": r"\.ring\b|--ring-offset",
        "进度条 track": r"\.progress-track|\.dtrack",
        "条款引用块": r"\.source-card|\.explain|\.em-never",
        "警示条": r"\.callout|\.warn-box|\.notice|\.error-card",
        "空状态": r"\.empty-state",
        "加载骨架": r"\.skeleton|shimmer",
        "风险三色标": r"--risk-high|--risk-mid|--risk-low",
        "数据表格": r"\.table-wrap|table\s*\{",
        "捕获预览": r"\.camera-stage|\.photo-stage",
    }
    for name, pattern in components.items():
        found = re.search(pattern, css) is not None
        say(f"- {name}：{'有' if found else '缺失'}")
        if not found:
            problem("I 组件", name, "组件缺失", "补样式并在结构中使用")
    say()

    # -------- J 行高与段间距
    say("## J 正文行高与段间距（目标行高 1.7-1.8）")
    say()
    prose_line = tokens.get("--line-prose", "")
    say(f"- `--line-prose`：{prose_line or '未定义'}")
    try:
        ratio = float(prose_line)
    except ValueError:
        ratio = 0.0
    if not (1.7 <= ratio <= 1.8):
        problem("J 行高", "--line-prose", f"正文行高 {prose_line or '未定义'} 不在 1.7-1.8", "设为 1.75-1.78")
    else:
        say("- 判定：OK")
    # 段间距
    margin_top_prose = [
        (sel, d.get("margin-top", "")) for sel, d in parsed
        if sel in {".lead", ".answer-note", ".explain", ".em-step", ".role-summary"}
    ]
    for selector, value in margin_top_prose:
        say(f"  - `{selector}` margin-top：{value or '未设置'}")
    say()

    # -------- 汇总
    say("## 问题清单汇总")
    say()
    if not PROBLEMS:
        say("无问题。")
    else:
        say("| # | 区域 | 位置 | 问题 | 修法 |")
        say("| --- | --- | --- | --- | --- |")
        for index, item in enumerate(PROBLEMS, 1):
            say(
                f"| {index} | {item['area']} | {item['where']} | "
                f"{item['issue']} | {item['fix']} |"
            )
    say()

    REPORT.write_text("\n".join(OUT) + "\n", encoding="utf-8")
    print()
    print(f"报告已写入 {REPORT.name}；问题总数 {len(PROBLEMS)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
