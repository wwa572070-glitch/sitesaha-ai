"""修正上一步把正则插进语句中间的问题（第 16 轮）。

事故：我用「找 RE_SPACES 那一行的换行」当插入点，
      但那条语句跨两行，结果新正则被插进了语句中间：
        var RE_SPACES = new RegExp("[" + String.fromCharCode(...) +
        var RE_LEAD_PUNCT = ...      <-- 插在这里，语法坏了
          "]+", "g");

修法：把这两行挪到 RE_SPACES 整条语句之后。

用法：python fix_regex_placement.py [--dry-run]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
SCRIPT_B = BUILD / "index_script_b.js"

BROKEN = '''    var RE_SPACES = new RegExp("[" + String.fromCharCode(9, 10, 13, 32, 12288) +
    var RE_LEAD_PUNCT = new RegExp("^[" + String.fromCharCode(65292, 12289, 65307, 65306, 12290) + "]+");
    var RE_ENDS_PUNCT = new RegExp("[" + String.fromCharCode(12290, 65307, 65281, 65311) + "]$");
      "]+", "g");'''

FIXED = '''    var RE_SPACES = new RegExp("[" + String.fromCharCode(9, 10, 13, 32, 12288) +
      "]+", "g");
    var RE_LEAD_PUNCT = new RegExp("^[" + String.fromCharCode(65292, 12289, 65307, 65306, 12290) + "]+");
    var RE_ENDS_PUNCT = new RegExp("[" + String.fromCharCode(12290, 65307, 65281, 65311) + "]$");'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    text = SCRIPT_B.read_text(encoding="utf-8")
    if BROKEN not in text:
        print("[跳过] 未找到损坏片段（可能已修）")
        return 0

    text = text.replace(BROKEN, FIXED, 1)
    print("[ok] 正则已挪到 RE_SPACES 语句之后")

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
