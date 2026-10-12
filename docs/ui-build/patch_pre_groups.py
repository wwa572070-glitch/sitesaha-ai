"""pre 清单分组折叠（第 20 轮 §3，按实际代码修正锚点）。

只有「当班必查」默认展开；「常规项」与「我的导入」收进 details。

用法：python patch_pre_groups.py [--dry-run]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
SCRIPT_B = BUILD / "index_script_b.js"


def blank(text: str) -> str:
    return "\n\n".join(text.split("\n"))


OLD = blank('''        var bucket = make("section", "check-group");
        var head = make("div", "check-group-head");
        head.appendChild(make("b", "check-group-title", group.title));
        head.appendChild(make("span", "check-group-note", group.note));
        bucket.appendChild(head);''')

NEW = blank('''        /* 只有「当班必查」默认展开；常规项与我的导入收进 details，
           否则手机端一屏看不到重点（第 20 轮 §3） */
        var collapsible = group.key !== "required";
        var bucket;
        var box = null;
        if (collapsible) {
          box = make("details", "disclosure check-group-more");
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
        }''')


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    text = SCRIPT_B.read_text(encoding="utf-8")
    if "check-group-more" in text:
        print("[跳过] 已改")
        return 0
    if OLD not in text:
        print("[FAIL] 锚点仍未匹配")
        return 1

    text = text.replace(OLD, NEW, 1)
    print("[ok] pre 清单：非必查组收进 details")

    # 空组分支原来用 host.appendChild(bucket)，现在 bucket 在 box 里，
    # 需要改成挂 box（否则空组会挂到 host 外面）
    empty_old = blank('''          host.appendChild(bucket);
          return;
        }''')
    empty_new = blank('''          if (box) box.appendChild(bucket);
          return;
        }''')
    if empty_old in text:
        text = text.replace(empty_old, empty_new, 1)
        print("[ok] 空组分支改为挂到 details 内")

    if text.count(chr(92)):
        print("[FAIL] 含反斜杠")
        return 1
    print("[ok] 无反斜杠")

    if args.dry_run:
        print("（dry-run，未写入）")
        return 0
    SCRIPT_B.write_text(text, encoding="utf-8")
    print("[ok] 已写入")
    return 0


if __name__ == "__main__":
    sys.exit(main())
