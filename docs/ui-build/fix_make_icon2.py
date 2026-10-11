"""§3.1 收尾：EMERGENCY_DATA 的 icon 改为 symbol id，并修最后一处对勾。

两件事：
  1. EMERGENCY_DATA 里 6 个 icon 字段目前是整段 SVG 字符串，
     而调用点已改成 makeIcon(scene.icon)，需要的是 symbol id。
  2. index_script_b.js 行 2841 的 tick 仍在传 SVG 字符串。

对勾改为不传内容，由 CSS 的 .tick/.untick 呈现：
  .tick 用 ::before 画对勾（或不画），.untick 画空心圆。
  这样 4 个位置的对勾样式统一，也彻底避开 textContent 转义问题。

用法：python fix_make_icon2.py [--dry-run]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
SCRIPT_A = BUILD / "index_script_a.js"
SCRIPT_B = BUILD / "index_script_b.js"

ICON_MAP = {
    "i-firstaid": "i-firstaid",
    "i-fire": "i-fire",
    "i-shock": "i-shock",
    "i-collapse": "i-collapse",
    "i-fall": "i-fall",
    "i-alert": "i-alert",
}

TICK_OLD = (
    'make("span", ok ? "tick" : "untick", ok ? '
    + "'" + '<svg class="ico ico-sm" aria-hidden="true"><use href="#i-check"/></svg> '
    + "' : \"○\")"
)
TICK_NEW = 'make("span", ok ? "tick" : "untick")'


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    text_a = SCRIPT_A.read_text(encoding="utf-8")
    text_b = SCRIPT_B.read_text(encoding="utf-8")
    applied = 0

    # ---- 1) icon 字段改为 symbol id ----
    for symbol in ICON_MAP:
        old = "icon: '" + '<svg class="ico" aria-hidden="true"><use href="#' + symbol + '"/></svg> ' + "'"
        new = "icon: \"" + symbol + "\""
        if old in text_a:
            count = text_a.count(old)
            text_a = text_a.replace(old, new)
            applied += count
            print(f"  [ok] icon → \"{symbol}\"（{count} 处）")
        else:
            print(f"  [跳过] 未匹配 {symbol}")

    # ---- 2) 最后一处对勾 ----
    if TICK_OLD in text_b:
        text_b = text_b.replace(TICK_OLD, TICK_NEW, 1)
        applied += 1
        print("  [ok] b: 培训步骤对勾改为纯 CSS 呈现")
    else:
        print("  [跳过] b 对勾锚点未匹配")

    # ---- 复核 ----
    for name, text in (("a", text_a), ("b", text_b)):
        left = len(re.findall(r"<svg", text))
        print(f"  [复核] {name} 里 <svg 字面量残留：{left} 处")

    for name, text in (("a", text_a), ("b", text_b)):
        if text.count(chr(92)):
            print(f"[FAIL] {name} 含反斜杠")
            return 1
    print("[ok] 无反斜杠")

    if args.dry_run:
        print(f"（dry-run，未写入；{applied} 处）")
        return 0
    SCRIPT_A.write_text(text_a, encoding="utf-8")
    SCRIPT_B.write_text(text_b, encoding="utf-8")
    print(f"[ok] 已写入（{applied} 处）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
