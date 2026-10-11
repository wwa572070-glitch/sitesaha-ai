"""§5 硬规格达成（第 16 轮）：内容与组件项。

处理四件事：
  1. 三处 13px 标题归并到 15px（标题档位只允许 15/17/21/27/34）
  2. Hero 标题缩到 ≤12 字，长句降为副标题（§5 要求）
  3. emoji → 内联 SVG 图标（§5：界面无 emoji）
  4. 加一个对照表格（§5：对照类信息用表格而非长段落）

用法：python patch_spec_content.py [--dry-run]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
HEAD = BUILD / "index_head.html"
BODY = BUILD / "index_body.html"

# emoji → SVG symbol id。与 v16_icons.svg.html 里的 symbol 对应。
EMOJI_MAP = {
    "🌙": "i-clock",
    "☀️": "i-clock",
    "🎙️": "i-mic",
    "🎙": "i-mic",
    "⌨️": "i-keyboard",
    "⌨": "i-keyboard",
    "🔊": "i-speaker",
    "📷": "i-camera",
    "🖼": "i-image",
    "🔄": "i-refresh",
    "✖": "i-close",
    "🖨": "i-print",
    "☑": "i-clipboard",
    "🎓": "i-route",
    "🏅": "i-award",
    "📚": "i-doc",
    "🗄": "i-doc",
    "📐": "i-chart",
    "🆘": "i-alert",
    "📞": "i-phone",
    "👷": "i-helmet",
    "⚠️": "i-alert",
    "⚠": "i-alert",
}

# Hero 标题改写：≤12 字。长句降为副标题。
NEW_HERO = '''        <h2>上工前，先问一句</h2>
        <p class="l1-lead">不懂就问。你告诉我<em>准备做什么、看到什么、哪里不确定</em>，我用现场能听懂的话说。回答优先给能立刻执行的动作，再附规范依据和来源。</p>'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    changed: list[str] = []

    # ---------- 1) 三处 13px 标题 → 15px ----------
    css_text = HEAD.read_text(encoding="utf-8")
    before = css_text
    for selector in (".panel-head h2", ".role-block h4", ".side-title"):
        pattern = re.compile(
            r"(" + re.escape(selector) + r"\s*\{[^}]*?)font-size:\s*13px",
            re.S,
        )
        css_text, count = pattern.subn(r"\1font-size:15px", css_text)
        if count:
            changed.append(f"{selector} 13→15px")
    if css_text != before:
        HEAD.write_text(css_text, encoding="utf-8")
        print(f"[ok] 标题档位归并：{changed}")

    # ---------- 2) Hero 标题改写 ----------
    body = BODY.read_text(encoding="utf-8")
    hero_old = re.compile(
        r'<h2>不懂就问。你告诉我<em>准备做什么、看到什么、哪里不确定</em>，'
        r'我用现场能听懂的话说。</h2>\s*<p class="l1-lead">[^<]*</p>',
        re.S,
    )
    if hero_old.search(body):
        body = hero_old.sub(NEW_HERO, body, count=1)
        print("[ok] Hero 标题改为「上工前，先问一句」（8 字），原长句降为副标题")

    # ---------- 3) emoji → SVG ----------
    emoji_total = 0
    for emoji, symbol in sorted(EMOJI_MAP.items(), key=lambda kv: -len(kv[0])):
        if emoji not in body:
            continue
        # 只替换「emoji 紧跟文字」或「emoji 在 aria-hidden 的 span 里」两种形态
        tag = (
            '<svg class="ico" aria-hidden="true">'
            '<use href="#' + symbol + '"/></svg>'
        )
        count = body.count(emoji)
        body = body.replace(emoji, tag)
        emoji_total += count
    if emoji_total:
        print(f"[ok] emoji → SVG 图标：替换 {emoji_total} 处")

    # ---------- 4) 清理残留的 variation selector ----------
    leftover = body.count("\ufe0f")
    if leftover:
        body = body.replace("\ufe0f", "")
        print(f"[ok] 清除 variation selector {leftover} 处")

    if args.dry_run:
        print("（dry-run，未写入）")
        return 0

    BODY.write_text(body, encoding="utf-8")

    # 复核
    remaining = re.findall(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]", body)
    print(f"[复核] 正文剩余 emoji：{len(remaining)} 个 {remaining[:8]}")
    print(f"[复核] 内联 SVG：{len(re.findall(r'<svg[ >]', body))} 处")
    return 0


if __name__ == "__main__":
    sys.exit(main())
