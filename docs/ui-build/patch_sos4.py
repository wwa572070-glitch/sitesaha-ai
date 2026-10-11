"""§6 收尾 3：SOS 浮动按钮的交互与审计白名单。

两个问题：
  1. sosFab 是 <a href="?view=sos">，直接跳会让浏览器整页刷新，
     而不是走 SPA 的 showView 切换。绑定 click 阻止默认行为并调用 showView。
  2. audit_bindings 把「自身负责跳转的链接」列为需绑定；sosFab 走
     href 兜底（JS 未加载时仍可用），需要加进白名单并写明理由。

用法：python patch_sos4.py [--dry-run]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
SCRIPT_B = BUILD / "index_script_b.js"
AUDIT = BUILD / "audit_bindings.py"

BIND = '''    /* §6 全站 SOS 浮动按钮：优先走 SPA 切换，避免整页刷新；
       href="?view=sos" 作为 JS 未加载时的兜底。 */
    (function bindSosFab() {
      var fab = $("sosFab");
      if (!fab) return;
      fab.addEventListener("click", function (event) {
        if (event && event.preventDefault) event.preventDefault();
        showView("sos");
      });
    })();

'''

ANCHOR = "    if (recordButton) {"

ALLOW_OLD = '''    "call120": "纯 tel: 链接，由 href 处理",'''

ALLOW_NEW = '''    "call120": "纯 tel: 链接，由 href 处理",
    "sosFab": "有 click 绑定走 SPA 切换，href 作为 JS 未加载时的兜底",'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    applied = 0
    script = SCRIPT_B.read_text(encoding="utf-8")
    audit = AUDIT.read_text(encoding="utf-8")

    if "function bindSosFab" not in script:
        if ANCHOR not in script:
            print("[FAIL] 找不到绑定锚点")
            return 1
        script = script.replace(ANCHOR, BIND + ANCHOR, 1)
        applied += 1
        print("[ok] sosFab 已绑定 showView('sos')")
    else:
        print("[跳过] sosFab 已绑定")

    if '"sosFab"' not in audit:
        if ALLOW_OLD in audit:
            audit = audit.replace(ALLOW_OLD, ALLOW_NEW, 1)
            applied += 1
            print("[ok] audit_bindings 白名单已加 sosFab（附理由）")
        else:
            print("[跳过] 白名单锚点未匹配")
    else:
        print("[跳过] 白名单已含 sosFab")

    if script.count(chr(92)):
        print("[FAIL] 引入反斜杠")
        return 1
    print("[ok] 无反斜杠")

    if args.dry_run:
        print(f"（dry-run，未写入；{applied} 处）")
        return 0
    SCRIPT_B.write_text(script, encoding="utf-8")
    AUDIT.write_text(audit, encoding="utf-8")
    print(f"[ok] 已写入（{applied} 处）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
