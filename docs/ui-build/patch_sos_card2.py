"""§4 应急卡：拨号吸底 + 打印绑定（第 20 轮，改用文件脚本避免引号问题）。

上一版用 PowerShell 内联命令，反斜杠被当转义插入分片，导致 JS 语法错误。
本脚本纯文件操作，先回滚损坏的分片再重新应用。

用法：python patch_sos_card2.py [--dry-run]
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
APP = BUILD.parent.parent
BODY = BUILD / "index_body.html"
SCRIPT_B = BUILD / "index_script_b.js"
TIERS = BUILD / "v16_tiers.css"
GIT = r"C:\Program Files\Git\cmd\git.exe"

OLD_BLOCK = '''          <div class="em-calls">

            <a id="call120" class="danger-button" href="tel:120"><svg class="ico" aria-hidden="true"><use href="#i-phone"/></svg> 拨打 120 急救</a>

            <a id="call119" class="danger-button" href="tel:119"><svg class="ico" aria-hidden="true"><use href="#i-phone"/></svg> 拨打 119 火警 / 救援</a>

          </div>'''

NEW_BLOCK = '''          <div class="em-call-bar" id="emCallBar">

            <a id="call120" class="call-button is-medical" href="tel:120"><svg class="ico" aria-hidden="true"><use href="#i-phone"/></svg> 120 急救</a>

            <a id="call119" class="call-button is-fire" href="tel:119"><svg class="ico" aria-hidden="true"><use href="#i-phone"/></svg> 119 火警</a>

            <button id="sosPrint" class="call-button is-print" type="button"><svg class="ico" aria-hidden="true"><use href="#i-print"/></svg> 打印这张卡</button>

          </div>'''

PRINT_BIND = '''    /* §4 应急卡打印（第 20 轮） */
    (function bindSosPrint() {
      var button = $("sosPrint");
      if (!button) return;
      button.addEventListener("click", function () { window.print(); });
    })();

'''

CSS_FILE = BUILD / "_sos_card.css"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    # ---- 1) 回滚上一版损坏的脚本分片 ----
    result = subprocess.run([GIT, "checkout", "--", "docs/ui-build/index_script_b.js"],
                            cwd=str(APP), capture_output=True, text=True,
                            encoding="utf-8", errors="replace")
    if result.returncode == 0:
        print("  [ok] 已回滚 index_script_b.js（清除上一版插入的反斜杠）")
    else:
        print(f"  [注意] 回滚返回 {result.returncode}")

    applied = 0
    body = BODY.read_text(encoding="utf-8")
    script = SCRIPT_B.read_text(encoding="utf-8")
    tiers = TIERS.read_text(encoding="utf-8")

    # ---- 2) 拨号块 ----
    if "em-call-bar" in body:
        print("  [跳过] 拨号条已改")
    elif OLD_BLOCK in body:
        body = body.replace(OLD_BLOCK, NEW_BLOCK, 1)
        applied += 1
        print("  [ok] 拨号条改为吸底 + 119 橙红 + 打印按钮")
    else:
        print("  [FAIL] 拨号块锚点未匹配")

    # ---- 3) 打印绑定 ----
    if "bindSosPrint" in script:
        print("  [跳过] 打印已绑定")
    else:
        anchor = "    (function bindSosFab() {"
        if anchor in script:
            script = script.replace(anchor, PRINT_BIND + anchor, 1)
            applied += 1
            print("  [ok] 打印按钮已绑定")
        else:
            print("  [FAIL] 找不到 bindSosFab 锚点")

    # ---- 4) 样式 ----
    css_path = BUILD / "patch_sos_card.py"
    if css_path.is_file():
        css_source = css_path.read_text(encoding="utf-8")
        start = css_source.find('CSS = """')
        end = css_source.find('"""', start + 10)
        if start >= 0 and end > 0:
            css = css_source[start + len('CSS = """'):end]
            if "§4 应急页收口" not in tiers:
                tiers = tiers.rstrip() + css
                applied += 1
                print("  [ok] 样式与打印样式已加入")

    # ---- 复核 ----
    for name, text in (("body", body), ("script", script)):
        count = text.count(chr(92))
        if count:
            print(f"  [FAIL] {name} 含 {count} 个反斜杠")
            return 1
    print("  [ok] 分片无反斜杠")

    if args.dry_run:
        print(f"（dry-run，未写入；{applied} 处）")
        return 0
    BODY.write_text(body, encoding="utf-8")
    SCRIPT_B.write_text(script, encoding="utf-8")
    TIERS.write_text(tiers, encoding="utf-8")
    print(f"[ok] 已写入（{applied} 处）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
