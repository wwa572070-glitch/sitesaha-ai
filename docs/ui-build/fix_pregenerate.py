"""修复 bindPreGenerate 的引号丢失（PowerShell 内联脚本剥掉了字符串引号）。

同时把 sos 拨号按钮的类名口径补进审计。

用法：python fix_pregenerate.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
SCRIPT_B = BUILD / "index_script_b.js"
AUDIT = BUILD / "audit_v16_spec.py"

BROKEN_START = "    /* 班前准备主行动"
BROKEN_END = "    if (recordButton) {"

FIXED = '''    /* 班前准备主行动：把「生成当班清单」接到索引区。
       当班条件输入（天气、作业类型）将在 §8 接入，当前先按全量清单对照。 */
    (function bindPreGenerate() {
      var button = $("preGenerate");
      if (!button) return;
      button.addEventListener("click", function () {
        var host = $("inspectionChecks");
        if (host && host.scrollIntoView) {
          host.scrollIntoView({ behavior: "smooth", block: "start" });
        }
        var notice = $("asrNotice");
        if (notice) {
          notice.hidden = false;
          notice.textContent = "下方是标准检查项目索引。当班条件输入功能正在接入，当前先按全量清单对照。";
        }
      });
    })();

'''


def main() -> int:
    text = SCRIPT_B.read_text(encoding="utf-8")
    start = text.find(BROKEN_START)
    if start < 0:
        print("[跳过] 未找到待修的绑定块（可能已修好）")
    else:
        end = text.find(BROKEN_END, start)
        if end < 0:
            print("[FAIL] 找不到绑定块结束位置")
            return 1
        text = text[:start] + FIXED + text[end:]
        print("[ok] bindPreGenerate 已用正确引号重写")

    if text.count(chr(92)):
        print(f"[FAIL] 含反斜杠 {text.count(chr(92))} 处")
        return 1
    SCRIPT_B.write_text(text, encoding="utf-8")
    print("[ok] 无反斜杠，已写入")

    # 审计：把 is-call 计入实心按钮口径
    audit = AUDIT.read_text(encoding="utf-8")
    old = r"r'class=\"(?:primary-button|amber-button)'"
    new = r"r'class=\"(?:primary-button|amber-button)[^\"]*is-call|class=\"(?:primary-button|amber-button)'"
    if "is-call" not in audit:
        audit = audit.replace(
            "r'class=\"(?:primary-button|amber-button)'",
            "r'class=\"[^\"]*(?:primary-button|amber-button)[^\"]*'",
        )
        AUDIT.write_text(audit, encoding="utf-8")
        print("[ok] 审计的按钮口径已改为匹配含这些类的任意组合")
    return 0


if __name__ == "__main__":
    sys.exit(main())
