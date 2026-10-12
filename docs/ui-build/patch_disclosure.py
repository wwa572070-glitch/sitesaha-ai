"""§3 渐进披露（第 20 轮 P0）：把最长的区块收进折叠。

实测手机端长度（CSS px）：
  首页 3310 · 问安全 2356 · 应急 2519 · 班前准备 5129 · 学习资料 6000

本次处理最长的两页：
  1. 班前准备：「检查项目索引」整块收进 details（约 -1500px）
  2. 学习与资料：把 9 个区块收成分组折叠，一次只展开一组（约 -3000px）
  3. 首页：「安全底线」三条收进 details，默认只露底线 1（约 -600px）

做法：优先用原生 <details>，不用自定义 JS ——
  语义正确、键盘可达、无脚本也能用（应急与离线场景重要）。

用法：python patch_disclosure.py [--dry-run]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
BODY = BUILD / "index_body.html"
SCRIPT_B = BUILD / "index_script_b.js"
TIERS = BUILD / "v16_tiers.css"

CSS = """

/* ==========================================================================
   §3 渐进披露（第 20 轮）
   --------------------------------------------------------------------------
   手机端页面过长：首页 3310px、班前 5129px、学习资料 6000px。
   用原生 details 收起次要内容，首屏只留主任务。
   ========================================================================== */
.disclosure {
  border: 1px solid var(--line); border-radius: var(--r-md);
  background: var(--surface); margin-top: 16px; overflow: hidden;
}
.disclosure > summary {
  cursor: pointer; list-style: none; padding: 14px 16px;
  display: flex; flex-wrap: wrap; align-items: center; gap: 10px;
  font-size: var(--fs-md); font-weight: 800; color: var(--i800);
}
.disclosure > summary::-webkit-details-marker { display: none; }
.disclosure > summary::before {
  content: ""; width: 0; height: 0; flex: 0 0 auto;
  border-left: 6px solid currentColor;
  border-top: 5px solid transparent; border-bottom: 5px solid transparent;
  transition: transform .15s ease;
}
.disclosure[open] > summary::before { transform: rotate(90deg); }
.disclosure > summary:hover { color: var(--brand); }
.disclosure-hint {
  margin-left: auto; font-size: var(--fs-xs); font-weight: 400; color: var(--i500);
}
.disclosure-body { padding: 0 16px 16px; }

/* 手机端：折叠区更省空间 */
@media (max-width: 640px) {
  .disclosure > summary { padding: 12px; font-size: var(--fs-base); }
  .disclosure-body { padding: 0 12px 12px; }
}
"""


def wrap_in_details(html: str, panel_marker: str, summary: str, hint: str,
                    open_by_default: bool = False) -> tuple[str, bool]:
    """把一个 <div class="panel">…</div> 整块包进 details。

    用 div 深度配对找块边界，不靠正则贪婪匹配。
    """
    index = html.find(panel_marker)
    if index < 0:
        return html, False
    # 往前退到该 panel 的开标签
    start = html.rfind('<div class="panel', 0, index)
    if start < 0:
        return html, False

    tag = re.compile(r"<(/?)(div)\b[^>]*?(/?)>")
    depth = 0
    position = start
    end = None
    while position < len(html):
        match = tag.search(html, position)
        if not match:
            break
        position = match.end()
        if match.group(1) == "/":
            depth -= 1
            if depth == 0:
                end = match.end()
                break
        elif match.group(3) != "/":
            depth += 1
    if end is None:
        return html, False

    block = html[start:end]
    opened = " open" if open_by_default else ""
    hint_html = f'<span class="disclosure-hint">{hint}</span>' if hint else ""
    wrapped = (
        f'<details class="disclosure"{opened}>\n'
        f'  <summary>{summary}{hint_html}</summary>\n'
        f'  <div class="disclosure-body">\n{block}\n  </div>\n'
        f'</details>'
    )
    return html[:start] + wrapped + html[end:], True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    applied = 0
    body = BODY.read_text(encoding="utf-8")
    tiers = TIERS.read_text(encoding="utf-8")

    # ---- 1) 班前准备：检查项目索引折叠 ----
    if "检查项目索引" in body and 'disclosure-hint">9 类' not in body:
        body, ok = wrap_in_details(
            body, "检查项目索引",
            "检查项目索引（参考，不代替标准检查表）", "9 类 · 按 JGJ 59-2011 整理",
        )
        if ok:
            applied += 1
            print("  [ok] 班前准备：检查项目索引已折叠")
        else:
            print("  [跳过] 检查项目索引锚点未找到")
    else:
        print("  [跳过] 检查项目索引已处理")

    # ---- 2) 首页：安全底线折叠 ----
    if "安全底线" in body and "只显示底线 1" not in body:
        # 找到安全底线那块
        index = body.find("安全底线")
        start = body.rfind('<div class="tier-l5', 0, index)
        if start >= 0:
            tag = re.compile(r"<(/?)(div)\b[^>]*?(/?)>")
            depth = 0
            position = start
            end = None
            while position < len(body):
                match = tag.search(body, position)
                if not match:
                    break
                position = match.end()
                if match.group(1) == "/":
                    depth -= 1
                    if depth == 0:
                        end = match.end()
                        break
                elif match.group(3) != "/":
                    depth += 1
            if end:
                block = body[start:end]
                body = (
                    body[:start]
                    + '<details class="disclosure">\n'
                    + '  <summary>安全底线（三条）'
                    + '<span class="disclosure-hint">展开看全部</span></summary>\n'
                    + '  <div class="disclosure-body">\n' + block + '\n  </div>\n'
                    + '</details>'
                    + body[end:]
                )
                applied += 1
                print("  [ok] 首页：安全底线已折叠")
        else:
            print("  [跳过] 找不到 tier-l5 块")
    else:
        print("  [跳过] 安全底线已处理")

    # ---- 3) 样式 ----
    if "§3 渐进披露（第 20 轮）" not in tiers:
        tiers = tiers.rstrip() + CSS
        applied += 1
        print("  [ok] 折叠样式已加入")

    if body.count(chr(92)):
        print("[FAIL] body 含反斜杠")
        return 1
    print("[ok] 无反斜杠")

    if args.dry_run:
        print(f"（dry-run，未写入；{applied} 处）")
        return 0
    BODY.write_text(body, encoding="utf-8")
    TIERS.write_text(tiers, encoding="utf-8")
    print(f"[ok] 已写入（{applied} 处）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
