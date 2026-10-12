"""精修依据清理：断句残留与起首标点（第 16 轮线上乱码收尾）。

实测清理后还剩两处瑕疵：
  依据 [2] 剩「物从人的正上方 未按规定设置爬梯或爬梯的强度、构造不符合规范要求，」
           —— 断句碎片拼在一起，不成句
  依据 [3] 开头是「，单台起重机所承受的荷载应符合专项施工方」
           —— 以标点起头，且末尾断了

两处修法：
  1. 剥掉起首的标点（，、；：。）
  2. 清理后如果内容太短或明显不成句（没有句号/分号结尾，且长度不足），
     直接显示「这一条主要是评分表，已省略」，不硬凑

用法：python refine_source_clean.py [--dry-run]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
SCRIPT_B = BUILD / "index_script_b.js"

OLD = '''      var joined = kept.join(" ").replace(RE_SPACES, " ").trim();
      if (joined.length > 180) {
        joined = joined.slice(0, 180) + "…";
      }
      return joined;
    }'''

NEW = '''      var joined = kept.join(" ").replace(RE_SPACES, " ").trim();

      /* 剥掉起首标点：标准片段常从「，单台起重机…」这种半句开始 */
      joined = joined.replace(RE_LEAD_PUNCT, "").trim();

      /* 不成句的残片不如不给：长度不足、或没有句读收尾，就返回空，
         由调用方显示「主要是评分表，已省略」 */
      var hasEnd = RE_ENDS_PUNCT.test(joined);
      if (joined.length < 24 || (!hasEnd && joined.length < 60)) {
        return "";
      }

      if (joined.length > 180) {
        joined = joined.slice(0, 180) + "…";
      }
      return joined;
    }'''

REGEX_ADD = '''    var RE_LEAD_PUNCT = new RegExp("^[" + String.fromCharCode(65292, 12289, 65307, 65306, 12290) + "]+");
    var RE_ENDS_PUNCT = new RegExp("[" + String.fromCharCode(12290, 65307, 65281, 65311) + "]$");
'''

ANCHOR = '    var RE_SPACES = new RegExp("[" + String.fromCharCode(9, 10, 13, 32, 12288) +'


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    text = SCRIPT_B.read_text(encoding="utf-8")
    applied = 0

    if "RE_LEAD_PUNCT" not in text:
        index = text.find(ANCHOR)
        if index < 0:
            print("[FAIL] 找不到 RE_SPACES 锚点")
            return 1
        # 插在 RE_SPACES 那一段之后（找到该行结束）
        line_end = text.find("\n", index)
        text = text[: line_end + 1] + REGEX_ADD + text[line_end + 1:]
        applied += 1
        print("[ok] 新增起首标点与句尾标点正则")
    else:
        print("[跳过] 正则已存在")

    if "不成句的残片不如不给" not in text:
        if OLD in text:
            text = text.replace(OLD, NEW, 1)
            applied += 1
            print("[ok] 清理函数加起首标点剥离 + 成句判定")
        else:
            print("[跳过] 清理函数锚点未匹配")
    else:
        print("[跳过] 清理函数已改")

    if text.count(chr(92)):
        print(f"[FAIL] 分片含 {text.count(chr(92))} 个反斜杠")
        return 1
    print("[ok] 无反斜杠")

    if args.dry_run:
        print(f"（dry-run，未写入；{applied} 处）")
        return 0
    SCRIPT_B.write_text(text, encoding="utf-8")
    print(f"[ok] 已写入（{applied} 处）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
