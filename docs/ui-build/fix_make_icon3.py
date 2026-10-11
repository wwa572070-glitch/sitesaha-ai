"""§3.1 收尾 2：修括号错位 + 把剩下的 innerHTML 图标改成 makeIcon。

问题 1：把 make("h4","",…) 换成 iconText(…) 时，原来 make() 的右括号留下了，
       变成 appendChild(iconText("i-alert", "常见风险"))) —— 多一个 )。
问题 2：仍有 6 处用 innerHTML 传 SVG 字符串。虽然 innerHTML 能正常渲染，
        但它绕过了 makeIcon 的统一路径，属于同一类隐患，一并收敛：
          · step-order / tick：纯图标 → replaceChildren(makeIcon(...))
          · themeToggle / recordButton / voiceButton：图标 + 文本 → 用 iconText 片段
          · 复制文本里的警告前缀：那里是纯文本拼接，图标无意义，去掉图标

用法：python fix_make_icon3.py [--dry-run]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
SCRIPT_A = BUILD / "index_script_a.js"
SCRIPT_B = BUILD / "index_script_b.js"

DQ = chr(34)
SQ = chr(39)


def ico(symbol: str, cls: str = "ico") -> str:
    return SQ + '<svg class=' + DQ + cls + DQ + ' aria-hidden=' + DQ + 'true' + DQ + '><use href=' + DQ + '#' + symbol + DQ + '/></svg> ' + SQ


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    text_a = SCRIPT_A.read_text(encoding="utf-8")
    text_b = SCRIPT_B.read_text(encoding="utf-8")
    applied = 0

    # ---------- 1) 修多余的右括号 ----------
    for note, bad, good in [
        ("常见风险", 'appendChild(iconText("i-alert", "常见风险")));', 'appendChild(iconText("i-alert", "常见风险"));'),
        ("必守规矩", 'appendChild(iconText("i-check", "必守规矩")));', 'appendChild(iconText("i-check", "必守规矩"));'),
        ("典型违规", 'appendChild(iconText("i-close", "典型违规")));', 'appendChild(iconText("i-close", "典型违规"));'),
        ("防护用品", 'appendChild(iconText("i-helmet", "防护用品")));', 'appendChild(iconText("i-helmet", "防护用品"));'),
    ]:
        if bad in text_a:
            text_a = text_a.replace(bad, good, 1)
            applied += 1
            print(f"  [ok] 修括号：{note}")
        elif good in text_a:
            print(f"  [跳过] {note} 括号已正确")
        else:
            print(f"  [警告] {note} 未匹配")

    # ---------- 2) step-order 图标 ----------
    old = 'item.querySelector(".step-order").innerHTML = ' + ico("i-check", "ico ico-sm") + ';'
    new = 'item.querySelector(".step-order").replaceChildren(makeIcon("i-check", "ico ico-sm"));'
    if old in text_a:
        text_a = text_a.replace(old, new, 1)
        applied += 1
        print("  [ok] a: step-order 图标改走 makeIcon")

    # ---------- 3) 主题按钮 ----------
    old = 'button.innerHTML = theme === ' + DQ + 'dark' + DQ + ' ? ' + ico("i-clock") + ' + ' + DQ + ' 白天' + DQ + ' : ' + ico("i-clock") + ' + ' + DQ + ' 夜间' + DQ + ';'
    new = ('button.replaceChildren(iconText("i-clock", theme === ' + DQ + 'dark' + DQ
           + ' ? ' + DQ + '白天' + DQ + ' : ' + DQ + '夜间' + DQ + '));')
    if old in text_a:
        text_a = text_a.replace(old, new, 1)
        applied += 1
        print("  [ok] a: 主题按钮改走 iconText")
    else:
        print("  [跳过] a: 主题按钮锚点未匹配")

    # ---------- 4) 录音按钮 ----------
    old = ('recordButton.innerHTML = serverAsrReady ? ' + ico("i-mic")
           + ' + ' + DQ + '录音提问（最长 60 秒）' + DQ + ' : ' + ico("i-mic")
           + ' + ' + DQ + '录音提问' + DQ + ';')
    new = ('recordButton.replaceChildren(iconText("i-mic", serverAsrReady'
           + ' ? ' + DQ + '录音提问（最长 60 秒）' + DQ + ' : ' + DQ + '录音提问' + DQ + '));')
    if old in text_b:
        text_b = text_b.replace(old, new, 1)
        applied += 1
        print("  [ok] b: 录音按钮改走 iconText")
    else:
        print("  [跳过] b: 录音按钮锚点未匹配")

    # ---------- 5) 浏览器识别进行中 ----------
    old = 'voiceButton.innerHTML = ' + ico("i-mic") + ' + ' + DQ + '正在听…' + DQ + ';'
    new = 'voiceButton.replaceChildren(iconText("i-mic", "正在听…"));'
    if old in text_b:
        text_b = text_b.replace(old, new, 1)
        applied += 1
        print("  [ok] b: 识别中状态改走 iconText")
    else:
        print("  [跳过] b: 识别中状态锚点未匹配")

    # ---------- 6) 复制文本里的警告前缀：那是纯文本，图标无意义，去掉 ----------
    old = "text += NL2 + " + ico("i-alert", "ico ico-sm") + " + warning;"
    new = 'text += NL2 + ' + DQ + '⚠ ' + DQ + ' + warning;'
    if old in text_b:
        text_b = text_b.replace(old, new, 1)
        applied += 1
        print("  [ok] b: 复制文本的警告前缀改回纯文本符号（该处不是 DOM）")
    else:
        print("  [跳过] b: 复制文本锚点未匹配")

    # ---------- 复核 ----------
    import re
    for name, text in (("a", text_a), ("b", text_b)):
        hits = [m.group(0) for m in re.finditer(r"<svg", text)]
        print(f"  [复核] {name} 里 <svg 残留 {len(hits)} 处")
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
