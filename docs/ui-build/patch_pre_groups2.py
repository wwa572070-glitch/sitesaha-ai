"""pre 清单分组折叠（用正则跨空白匹配，避免空行格式问题）。

只有「当班必查」默认展开；其余组收进 details。

用法：python patch_pre_groups2.py [--dry-run]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
SCRIPT_B = BUILD / "index_script_b.js"

PATTERN = re.compile(
    r'var bucket = make\("section", "check-group"\);\s*'
    r'var head = make\("div", "check-group-head"\);\s*'
    r'head\.appendChild\(make\("b", "check-group-title", group\.title\)\);\s*'
    r'head\.appendChild\(make\("span", "check-group-note", group\.note\)\);\s*'
    r'bucket\.appendChild\(head\);'
)

REPLACEMENT = '''/* 只有「当班必查」默认展开；常规项与我的导入收进 details，
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
        }'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    text = SCRIPT_B.read_text(encoding="utf-8")
    if "check-group-more" in text:
        print("[跳过] 已改")
        return 0

    matches = list(PATTERN.finditer(text))
    print(f"[信息] 正则匹配到 {len(matches)} 处")
    if len(matches) != 1:
        print("[FAIL] 匹配数不是 1，中止以免改错")
        return 1

    text = PATTERN.sub(REPLACEMENT, text, count=1)
    print("[ok] 非必查组已收进 details")

    # 空组分支修正
    empty = re.compile(r"host\.appendChild\(bucket\);\s*return;\s*\}")
    if empty.search(text):
        text = empty.sub(
            "if (box) box.appendChild(bucket);\n\n          return;\n\n        }",
            text, count=1,
        )
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
