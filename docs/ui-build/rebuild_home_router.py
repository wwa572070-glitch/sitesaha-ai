"""重建首页为「路由器」页，并把 6 个错位模块搬到对应页面。

依据（Taste Skill 第 0 节）：首页只回答一个问题——**我现在要干什么**。
详细内容去各自的页面，首页不长篇罗列。

搬移表：
  培训与知识模块   → #learn    （学习与资料）
  今日警示案例     → #learn
  知识库概览       → #learn 并入「资料库概览」
  最近入库         → #learn
  知识领域分布     → #learn
  服务状态         → #learn
  拍照识隐患       → 删除（#ask 已有完整拍照区，只保留首页入口卡）
  应急求助         → 删除（#sos 已有完整指引，只保留首页入口卡）

首页保留（6 块）：
  Hero + 三个主入口 + 我是哪个工种 + 今天上工前的三件事 + 安全底线

用法：python rebuild_home_router.py
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


def find_panels(text: str) -> list[tuple[int, int, str]]:
    """切出所有顶层 <div class="panel"> 块（嵌套的不算）。"""
    spans = []
    for match in re.finditer(r'<div class="panel[^"]*"', text):
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
        block = text[match.start():i]
        head = re.search(r"<h2[^>]*>(.*?)</h2>", block, re.S)
        title = re.sub(r"<[^>]+>", "", head.group(1)).strip() if head else "(无标题)"
        spans.append((match.start(), i, title))

    out = []
    for start, end, title in spans:
        if any(s < start and end <= e for s, e, _t in spans if (s, e) != (start, end)):
            continue
        out.append((start, end, title))
    return out


def section_span(body: str, section_id: str) -> tuple[int, int, int]:
    """返回 (整体起, 内容起, 整体止)。"""
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
    open_end = body.find(">", start) + 1
    return start, open_end, i - len("</section>")


def main() -> int:
    body = BODY.read_text(encoding="utf-8")
    before = len(body)

    home_start, home_open, home_close = section_span(body, "home")
    home = body[home_open:home_close]

    # ---------- 抽出首页里的模块 ----------
    panels = find_panels(home)
    print("=== 首页现有模块 ===")
    for _s, _e, title in panels:
        tag = ""
        if title in MOVE:
            tag = f"→ 搬到 #{MOVE[title]}"
        elif title in DROP:
            tag = "→ 删除（目标页已有完整版）"
        else:
            tag = "→ 保留"
        print(f"  {title:<22} {tag}")

    moved: dict[str, list[str]] = {}
    keep: list[str] = []
    for start, end, title in reversed(panels):
        block = home[start:end]
        if title in MOVE:
            moved.setdefault(MOVE[title], []).append(block)
            home = home[:start] + home[end:]
        elif title in DROP:
            home = home[:start] + home[end:]
        else:
            keep.append(title)

    # 清理首页里已经空掉的阶段包装
    home = re.sub(r'<div class="phase">\s*<div class="phase-head">.*?</div>\s*<div class="phase-rule"></div>\s*</div>',
                  "", home, flags=re.S)
    home = re.sub(r'<div class="phase-single">\s*</div>', "", home)
    home = re.sub(r'<div class="phase-cols">\s*</div>', "", home)
    home = re.sub(r'<div class="phase-main">\s*</div>', "", home)
    home = re.sub(r'<div class="phase-side">\s*</div>', "", home)

    print()
    print(f"=== 首页保留 {len(keep)} 块 ===")
    for title in keep:
        print(f"  {title}")

    body = body[:home_open] + home + body[home_close:]

    # ---------- 把搬移的模块插到目标页 ----------
    print()
    for section_id, blocks in moved.items():
        _s, open_end, close = section_span(body, section_id)
        payload = (
            "\n\n      <!-- 从首页迁移过来的模块（首页只留入口） -->\n"
            + "\n\n".join(blocks)
            + "\n\n    "
        )
        body = body[:close] + payload + body[close:]
        print(f"[ok] 已向 #{section_id} 迁入 {len(blocks)} 个模块")

    BODY.write_text(body, encoding="utf-8")
    print()
    print(f"index_body.html {before} → {len(body)} 字符")

    # ---------- 自检 ----------
    sections = re.findall(r'<section id="([^"]+)"', body)
    views = re.findall(r'data-view="([^"]+)"', body)
    print(f"  视图 {sections}")
    if sorted(sections) != sorted(views):
        print("[FAIL] 导航与视图不一致")
        return 1

    home_start, home_open, home_close = section_span(body, "home")
    left = [t for _s, _e, t in find_panels(body[home_open:home_close])]
    print(f"  首页剩余模块 {len(left)} 个：{left}")

    # 关键 id 不能丢
    required = ["todoList", "homeRoleChips", "homeRoleHint", "sideDomains",
                "documentCount", "chunkCount", "caseCount", "roleCount",
                "kvMode", "kvVision", "kvAsr", "kvAccess", "docGroups", "docSearch"]
    missing = [x for x in required if f'id="{x}"' not in body]
    if missing:
        print(f"[FAIL] 丢失 id：{missing}")
        return 1
    print(f"  [ok] {len(required)} 个关键 id 全部保留")
    return 0


if __name__ == "__main__":
    sys.exit(main())
