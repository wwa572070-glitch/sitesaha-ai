"""信息架构重组：把 7 个页面按「用户意图」重排为 5 个，并把错位的模块移回各自页面。

新架构（按意图分，不按功能分）：
  ① 首页        我现在要干什么      Hero + 三入口 + 工种 + 三件事
  ② 问安全      我不确定，想问/拍   原 #assistant
  ③ 应急处置    出事了怎么办       原 #emergency（重命名）
  ④ 班前准备    上工前确认什么     原 #checklist
  ⑤ 学习与资料  我要学 / 我要查     #training + #library 合并

改名对照（视图名在脚本里引用极少，成本低）：
  assistant → ask        （脚本引用 5 处，需同步）
  emergency → sos        （脚本引用 0 处）
  checklist → pre        （脚本引用 1 处，需同步）
  training  → learn      （脚本引用 0 处）
  library   → （并入 learn）
  home      → home       （不变，脚本引用 1 处）

用法：python restructure_ia.py [--dry-run]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
BODY = BUILD / "index_body.html"
SCRIPTS = [BUILD / "index_script_a.js", BUILD / "index_script_b.js"]

RENAMES = {
    "assistant": "ask",
    "emergency": "sos",
    "checklist": "pre",
    "training": "learn",
}

TABS = [
    ("home", "首页"),
    ("ask", "问安全"),
    ("sos", "应急处置"),
    ("pre", "班前准备"),
    ("learn", "学习与资料"),
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    body = BODY.read_text(encoding="utf-8")

    # ---------- 1) 视图改名 ----------
    changes = []
    for old, new in RENAMES.items():
        pattern = re.compile(rf'(<section id="){re.escape(old)}(")')
        body, n = pattern.subn(rf"\g<1>{new}\g<2>", body)
        if n:
            changes.append(f"section#{old} → #{new}（{n} 处）")
        pattern2 = re.compile(rf'(data-view="){re.escape(old)}(")')
        body, n2 = pattern2.subn(rf"\g<1>{new}\g<2>", body)
        if n2:
            changes.append(f'data-view="{old}" → "{new}"（{n2} 处）')
        pattern3 = re.compile(rf'(data-goto="){re.escape(old)}(")')
        body, n3 = pattern3.subn(rf"\g<1>{new}\g<2>", body)
        if n3:
            changes.append(f'data-goto="{old}" → "{new}"（{n3} 处）')

    print("=== 视图改名 ===")
    for line in changes:
        print("  " + line)

    # ---------- 2) 重建导航 ----------
    # 注意：<nav> 上没有 class，用 <nav\b 匹配
    nav_pattern = re.compile(r"(<nav\b[^>]*>.*?</nav>)", re.S)
    nav_match = nav_pattern.search(body)
    if not nav_match:
        print("[FAIL] 找不到 <nav>")
        return 1

    # 去掉 emoji 图标：按 Taste Skill 3.D，emoji 默认不用，
    # 导航用纯文字标签更沉稳，也少一层视觉噪声。
    buttons = []
    for view, label in TABS:
        cls = "nav-button emergency-tab" if view == "sos" else "nav-button"
        if view == "home":
            cls += " active"
        buttons.append(f'      <button class="{cls}" data-view="{view}">{label}</button>')
    new_nav = (
        '<nav aria-label="主导航">\n'
        '    <div class="nav-inner">\n'
        + "\n".join(buttons)
        + "\n    </div>\n  </nav>"
    )
    body = body[: nav_match.start(1)] + new_nav + body[nav_match.end(1):]
    print()
    print(f"=== 导航重建：7 项 → {len(TABS)} 项（去掉 emoji 图标）===")
    for view, label in TABS:
        print(f"  {view:<8} {label}")

    # ---------- 3) 视图 class 修正（只有 home 是 active）----------
    for view in [v for v, _ in TABS]:
        want = "view active" if view == "home" else "view"
        body = re.sub(
            rf'(<section id="{view}"[^>]*class=")[^"]*(")',
            rf"\g<1>{want}\g<2>",
            body,
        )

    if args.dry_run:
        print("\n（dry-run，未写入）")
        return 0

    BODY.write_text(body, encoding="utf-8")
    print(f"\n[ok] index_body.html 已写入，{len(body)} 字符")

    # ---------- 4) 同步脚本里的视图名 ----------
    print()
    print("=== 同步脚本里的视图名 ===")
    for path in SCRIPTS:
        text = path.read_text(encoding="utf-8")
        hits = 0
        for old, new in RENAMES.items():
            for quote in ('"', "'"):
                needle = f"{quote}{old}{quote}"
                if needle in text:
                    count = text.count(needle)
                    text = text.replace(needle, f"{quote}{new}{quote}")
                    hits += count
                    print(f"  {path.name}: {needle} → {quote}{new}{quote}（{count} 处）")
        if hits:
            path.write_text(text, encoding="utf-8")

    # ---------- 5) 自检 ----------
    print()
    print("=== 自检 ===")
    body = BODY.read_text(encoding="utf-8")
    sections = re.findall(r'<section id="([^"]+)"', body)
    views = re.findall(r'data-view="([^"]+)"', body)
    print(f"  视图 {len(sections)} 个：{sections}")
    print(f"  导航 {len(views)} 项：{views}")
    if sorted(sections) != sorted(views):
        print(f"  [FAIL] 导航与视图不一致：仅视图 {set(sections) - set(views)}；仅导航 {set(views) - set(sections)}")
        return 1
    print("  [ok] 导航与视图一一对应")
    return 0


if __name__ == "__main__":
    sys.exit(main())
