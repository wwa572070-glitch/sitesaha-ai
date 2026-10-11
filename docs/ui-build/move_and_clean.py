"""搬迁 + 清理，一次做完，逐块判断（不用贪婪正则）。

与上一版的区别：
  上一版用 r'<div class="phase">.*?</div>\\s*</div>' 这样的正则删空阶段，
  非贪婪匹配跨过了有内容的阶段，把首页 3 个模块一起删了（丢 6 个 id）。
  这一版改成：按 div 深度配对切出每个 phase 块，只在块内**确实没有 panel / id** 时才删。

用法：python move_and_clean.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
BODY = BUILD / "index_body.html"

MOVE = {
    "培训与知识模块": "learn",
    "今日警示案例": "learn",
    "知识库概览": "learn",
    "最近入库": "learn",
    "知识领域分布": "learn",
    "服务状态": "learn",
}
DROP = ["拍照识隐患", "应急求助"]


def div_blocks(text: str, opening: str) -> list[tuple[int, int, str]]:
    """按 div 深度配对，切出所有以 opening 开头的 <div> 块。"""
    out = []
    for match in re.finditer(re.escape(opening), text):
        depth = 0
        i = match.start()
        while i < len(text):
            nxt = re.search(r"<(/?)div\b[^>]*>", text[i:])
            if not nxt:
                break
            depth += -1 if nxt.group(1) == "/" else 1
            i += nxt.end()
            if depth == 0:
                break
        out.append((match.start(), i, text[match.start():i]))
    return out


def top_panels(text: str) -> list[tuple[int, int, str]]:
    spans = []
    for start, end, block in div_blocks(text, '<div class="panel'):
        head = re.search(r"<h2[^>]*>(.*?)</h2>", block, re.S)
        title = re.sub(r"<[^>]+>", "", head.group(1)).strip() if head else "(无标题)"
        spans.append((start, end, title))
    # 去掉嵌套在别的 panel 里的
    return [
        (s, e, t) for s, e, t in spans
        if not any(s2 < s and e <= e2 for s2, e2, _t in spans if (s2, e2) != (s, e))
    ]


def section_span(body: str, section_id: str) -> tuple[int, int, int]:
    start = body.find(f'<section id="{section_id}"')
    if start < 0:
        raise SystemExit(f"找不到 #{section_id}")
    depth = 0
    i = start
    while i < len(body):
        nxt = re.search(r"<(/?)section\b[^>]*>", body[i:])
        if not nxt:
            break
        depth += -1 if nxt.group(1) == "/" else 1
        i += nxt.end()
        if depth == 0:
            break
    return start, body.find(">", start) + 1, i - len("</section>")


def main() -> int:
    body = BODY.read_text(encoding="utf-8")
    before = len(body)
    ids_before = set(re.findall(r'id="([^"]+)"', body))

    _hs, home_open, home_close = section_span(body, "home")
    home = body[home_open:home_close]

    # ---------- 1) 抽出要搬 / 要删的模块 ----------
    panels = top_panels(home)
    print("=== 首页模块处理 ===")
    moved: dict[str, list[str]] = {}
    for start, end, title in reversed(panels):
        block = home[start:end]
        if title in MOVE:
            moved.setdefault(MOVE[title], []).append(block)
            home = home[:start] + home[end:]
            print(f"  搬运  {title:<20} → #{MOVE[title]}")
        elif title in DROP:
            home = home[:start] + home[end:]
            print(f"  删除  {title:<20} （目标页已有完整版）")
        else:
            print(f"  保留  {title}")

    # ---------- 2) 逐块判断 phase 是否为空 ----------
    removed = 0
    for start, end, block in reversed(div_blocks(home, '<div class="phase"')):
        # 块内是否还有实质内容：panel 或任何 id 或任何文本
        text_only = re.sub(r"<[^>]+>", "", block)
        text_only = re.sub(r"class=\"phase-(title|desc|no)\"[^>]*>", "", text_only)
        has_panel = 'class="panel' in block
        has_id = bool(re.search(r'\sid="', block))
        body_text = re.sub(r"\s+", "", re.sub(r"<[^>]+>", "", re.sub(
            r'<div class="phase-head">.*?</div>', "", block, flags=re.S)))
        if has_panel or has_id or body_text:
            continue
        home = home[:start] + home[end:]
        removed += 1
    print(f"\n  删除空阶段块 {removed} 个")

    body = body[:home_open] + home + body[home_close:]

    # ---------- 3) 搬到目标页 ----------
    for section_id, blocks in moved.items():
        _s, _open, close = section_span(body, section_id)
        payload = (
            "\n\n      <!-- 从首页迁移：首页只留入口 -->\n"
            + "\n\n".join(blocks)
            + "\n\n    "
        )
        body = body[:close] + payload + body[close:]

    BODY.write_text(body, encoding="utf-8")

    # ---------- 4) 自检：一个 id 都不能丢 ----------
    ids_after = set(re.findall(r'id="([^"]+)"', body))
    lost = sorted(ids_before - ids_after)
    print()
    print(f"index_body.html {before} → {len(body)} 字符")
    print(f"  id {len(ids_before)} → {len(ids_after)}；丢失 {lost if lost else '无'}")

    _hs, home_open, home_close = section_span(body, "home")
    home_now = body[home_open:home_close]
    keep = [t for _s, _e, t in top_panels(home_now)]
    print(f"  首页剩余模块 {len(keep)} 个：{keep}")
    print(f"  首页剩余阶段标签 {len(re.findall(r'phase-title', home_now))} 个")

    sections = re.findall(r'<section id="([^"]+)"', body)
    views = re.findall(r'data-view="([^"]+)"', body)
    if sorted(sections) != sorted(views):
        print(f"  [FAIL] 导航与视图不一致")
        return 1
    if lost:
        print(f"  [FAIL] 丢了 id，需要回滚")
        return 1
    print("  [ok] 无 id 丢失，导航与视图一致")
    return 0


if __name__ == "__main__":
    sys.exit(main())
