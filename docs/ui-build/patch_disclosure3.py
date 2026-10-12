"""§3 补完：把 pre 与 learn 压到 6 屏内（第 20 轮 P0）。

上一轮折叠后仍未达标：
  pre   6.2 屏（目标 ≤6）
  learn 7.2 屏（目标 ≤6）

本次再收两块：

learn（已折叠：标准库 / 在线模型 / 知识库状态 / 合规说明）
  + 真实事故 / 隐患案例    —— 参考库，不是每次都要看
  + 学习积分与培训记录      —— 记录类，次要

pre
  + 当班清单里的「常规项」组 —— 默认收起，主任务是「当班必查」
  + 「我的导入」为空时不占位

做法：learn 用 details 包裹 panel；pre 的清单分组由 JS 渲染，
      在渲染函数里给非必查组套 details。

用法：python patch_disclosure3.py [--dry-run]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
BODY = BUILD / "index_body.html"
SCRIPT_B = BUILD / "index_script_b.js"

TAG = re.compile(r"<(/?)(div)\b[^>]*?(/?)>")


def block_containing(html: str, needle: str, open_marker: str):
    index = html.find(needle)
    if index < 0:
        return None
    start = html.rfind(open_marker, 0, index)
    if start < 0:
        return None
    depth = 0
    position = start
    while position < len(html):
        match = TAG.search(html, position)
        if not match:
            break
        position = match.end()
        if match.group(1) == "/":
            depth -= 1
            if depth == 0:
                return start, match.end()
        elif match.group(3) != "/":
            depth += 1
    return None


def wrap(html: str, span, summary: str, hint: str) -> str:
    start, end = span
    hint_html = f'<span class="disclosure-hint">{hint}</span>' if hint else ""
    return (
        html[:start]
        + '<details class="disclosure">\n'
        + f'  <summary>{summary}{hint_html}</summary>\n'
        + '  <div class="disclosure-body">\n' + html[start:end] + '\n  </div>\n'
        + '</details>'
        + html[end:]
    )


BODY_TARGETS = [
    ("真实事故 / 隐患案例", "案例库", "6 例 · 含分类筛选"),
    ("学习积分与培训记录", "学习积分与培训记录", "积分 / 记录单"),
]

# pre 清单分组：非必查组套 details
GROUP_OLD = '''        var bucket = make("section", "check-group");
        var head = make("div", "check-group-head");
        head.appendChild(make("b", "check-group-title", group.title));
        head.appendChild(make("span", "check-group-note", group.note));
        bucket.appendChild(head);'''

GROUP_NEW = '''        /* 只有「当班必查」默认展开；常规项与我的导入收进 details，
           避免手机端一屏看不到重点（第 20 轮 §3） */
        var collapsible = group.key !== "required" && group.items.length > 0;
        var bucket;
        if (collapsible) {
          var box = make("details", "disclosure check-group-more");
          var summary = make("summary", "", group.title + "（" + group.items.length + " 条）");
          summary.appendChild(make("span", "disclosure-hint", group.note));
          box.appendChild(summary);
          bucket = make("div", "disclosure-body");
          box.appendChild(bucket);
          host.appendChild(box);
        } else {
          bucket = make("section", "check-group");
          var head = make("div", "check-group-head");
          head.appendChild(make("b", "check-group-title", group.title));
          head.appendChild(make("span", "check-group-note", group.note));
          bucket.appendChild(head);
        }'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    applied = 0
    body = BODY.read_text(encoding="utf-8")
    script = SCRIPT_B.read_text(encoding="utf-8")

    # ---- learn 两处 ----
    for needle, summary, hint in BODY_TARGETS:
        if f"<summary>{summary}" in body:
            print(f"  [跳过] {summary} 已折叠")
            continue
        span = block_containing(body, needle, '<div class="panel"')
        if not span:
            print(f"  [跳过] 找不到「{needle}」")
            continue
        size = span[1] - span[0]
        body = wrap(body, span, summary, hint)
        applied += 1
        print(f"  [ok] {summary} 已折叠（原块 {size} 字符）")

    # ---- pre 清单分组 ----
    if "check-group-more" not in script:
        old = "\n\n".join(GROUP_OLD.split("\n"))
        new = "\n\n".join(GROUP_NEW.split("\n"))
        if old in script:
            script = script.replace(old, new, 1)
            applied += 1
            print("  [ok] pre 清单：非必查组收进 details")
        else:
            print("  [跳过] pre 清单分组锚点未匹配")
    else:
        print("  [跳过] pre 清单分组已改")

    if body.count(chr(92)):
        print("[FAIL] body 含反斜杠")
        return 1
    if script.count(chr(92)):
        print("[FAIL] script 含反斜杠")
        return 1
    print("[ok] 无反斜杠")

    if args.dry_run:
        print(f"（dry-run，未写入；{applied} 处）")
        return 0
    BODY.write_text(body, encoding="utf-8")
    SCRIPT_B.write_text(script, encoding="utf-8")
    print(f"[ok] 已写入（{applied} 处）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
