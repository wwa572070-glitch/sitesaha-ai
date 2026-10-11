"""§3.1 修复：新增 makeIcon()，替换所有把 SVG 当文本传的调用点。

根因：make(tag, className, value) 用 textContent，而多处调用点传的是 HTML 字符串，
于是 <svg> 被转义成可见文本。实测在工种专项的四个小标题上看到了源码。

修法（用户已确认方案一）：
  新增 makeIcon(symbolId, className) —— 用 createElementNS 建真实的 svg/use 节点。
  make() 保持只处理纯文本，契约变清晰，从此不可能再犯。

替换清单（实测扫出 10 处）：
  a: 工种专项四个小标题（常见风险/必守规矩/典型违规/防护用品）
     步骤完成对勾
  b: 案例快选按钮、警告条、拨打按钮、朗读按钮
     应急 6 张卡的类型图标（scene.icon）
     处置步骤头部的 scene.icon

用法：python fix_make_icon.py [--dry-run]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
SCRIPT_A = BUILD / "index_script_a.js"
SCRIPT_B = BUILD / "index_script_b.js"

SQ = chr(39)
DQ = chr(34)

# ---------- 新函数：插在 make() 之后 ----------
MAKE_ANCHOR = '''    function clear(node) {
      if (node) node.replaceChildren();
      return node;
    }'''

MAKE_ICON = '''    /* 建一个真实的 svg/use 图标节点。
       为什么单独一个函数：make() 用 textContent，传 HTML 字符串会被转义成
       可见文本（页面上直接显示 <svg ...>）。图标必须走这里，契约才清楚。 */
    function makeIcon(symbolId, className) {
      var NS = "http://www.w3.org/2000/svg";
      var svg = document.createElementNS(NS, "svg");
      svg.setAttribute("class", className || "ico");
      svg.setAttribute("aria-hidden", "true");
      var use = document.createElementNS(NS, "use");
      use.setAttribute("href", "#" + symbolId);
      svg.appendChild(use);
      return svg;
    }

    /* 图标 + 文字的片段：返回 DocumentFragment，便于 appendChild 一次挂上 */
    function iconText(symbolId, text, className) {
      var frag = document.createDocumentFragment();
      frag.appendChild(makeIcon(symbolId, className));
      frag.appendChild(document.createTextNode(" " + text));
      return frag;
    }

    function clear(node) {
      if (node) node.replaceChildren();
      return node;
    }'''

# ---------- a 里的替换 ----------
A_EDITS = [
    # 四个小标题：原来是 make("h4", "", '<svg…>文字') + appendChild
    (
        "make(\"h4\", \"\", '" + '<svg class="ico" aria-hidden="true"><use href="#i-alert"/></svg> '
        + "' + \"常见风险\"",
        'iconText("i-alert", "常见风险")',
    ),
    (
        "make(\"h4\", \"\", '" + '<svg class="ico" aria-hidden="true"><use href="#i-check"/></svg> '
        + "' + \"必守规矩\"",
        'iconText("i-check", "必守规矩")',
    ),
    (
        "make(\"h4\", \"\", '" + '<svg class="ico" aria-hidden="true"><use href="#i-close"/></svg> '
        + "' + \"典型违规\"",
        'iconText("i-close", "典型违规")',
    ),
    (
        "make(\"h4\", \"\", '" + '<svg class="ico" aria-hidden="true"><use href="#i-helmet"/></svg> '
        + "' + \"防护用品\"",
        'iconText("i-helmet", "防护用品")',
    ),
]

# ---------- b 里的替换 ----------
B_EDITS = [
    (
        "make(\"button\", \"quick-button\", '"
        + '<svg class="ico" aria-hidden="true"><use href="#i-doc"/></svg> '
        + "' + (item.title || \"案例\"))",
        'makeButtonWithIcon("quick-button", "i-doc", item.title || "案例")',
    ),
    (
        "make(\"button\", \"secondary-button\", '"
        + '<svg class="ico" aria-hidden="true"><use href="#i-speaker"/></svg> '
        + "' + \"朗读处置步骤\")",
        'makeButtonWithIcon("secondary-button", "i-speaker", "朗读处置步骤")',
    ),
    (
        "make(\"a\", \"primary-button danger-button is-call\", phone === \"120\" ? '"
        + '<svg class="ico" aria-hidden="true"><use href="#i-phone"/></svg> '
        + "' + \"拨打 120 急救\" : '"
        + '<svg class="ico" aria-hidden="true"><use href="#i-phone"/></svg> '
        + "' + \"拨打 119 火警 / 救援\")",
        'makeButtonWithIcon("primary-button danger-button is-call", "i-phone", '
        'phone === "120" ? "拨打 120 急救" : "拨打 119 火警 / 救援")',
    ),
]

# 警告条：make("div","warn-box", '<svg…>' + warning)
WARN_OLD = (
    "make(\"div\", \"warn-box\", '"
    + '<svg class="ico ico-sm" aria-hidden="true"><use href="#i-alert"/></svg> '
    + "' + warning)"
)
WARN_NEW = 'makeIconText("div", "warn-box", "i-alert", "ico ico-sm", warning)'

# 应急卡图标：make("span", "em-ico", scene.icon)
EM_ICON_OLD = 'make("span", "em-ico", scene.icon)'
EM_ICON_NEW = 'makeIcon(scene.icon, "ico ico-xl")'

# 处置步骤头部：make("span", "", scene.icon + " " + scene.label)
STEP_HEAD_OLD = 'make("span", "", scene.icon + " " + scene.label)'
STEP_HEAD_NEW = 'iconText(scene.icon, scene.label)'

# step-order 对勾
TICK_OLD = 'ok ? \'' + '<svg class="ico ico-sm" aria-hidden="true"><use href="#i-check"/></svg> ' + '\' : "○"'
TICK_NEW = 'ok ? "" : "○"'

# ---------- 需要新增的两个组合辅助函数 ----------
HELPERS = '''    /* make() 的图标版：建 div/button 并把「图标 + 文字」一次性挂上 */
    function makeIconText(tag, className, symbolId, iconClass, text) {
      var node = make(tag, className);
      node.appendChild(makeIcon(symbolId, iconClass));
      node.appendChild(document.createTextNode(" " + text));
      return node;
    }

    function makeButtonWithIcon(className, symbolId, text) {
      var button = make("button", className);
      button.type = "button";
      button.appendChild(makeIcon(symbolId));
      button.appendChild(document.createTextNode(" " + text));
      return button;
    }

'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    text_a = SCRIPT_A.read_text(encoding="utf-8")
    text_b = SCRIPT_B.read_text(encoding="utf-8")
    applied = 0

    # ---- 1) 插入 makeIcon / iconText ----
    if "function makeIcon" not in text_a:
        if MAKE_ANCHOR not in text_a:
            print("[FAIL] 找不到 clear() 锚点")
            return 1
        text_a = text_a.replace(MAKE_ANCHOR, MAKE_ICON, 1)
        applied += 1
        print("[ok] 插入 makeIcon() 与 iconText()")
    else:
        print("[跳过] makeIcon 已存在")

    # ---- 2) 插入组合辅助（放 b 里，因为它服务于 b 的调用点）----
    if "function makeButtonWithIcon" not in text_b:
        anchor = "    function clear(node) {"
        if anchor in text_b:
            text_b = text_b.replace(anchor, HELPERS + anchor, 1)
            applied += 1
            print("[ok] 插入 makeIconText() 与 makeButtonWithIcon()（b）")
        else:
            print("[警告] b 里找不到 clear() 锚点，改用 a 末尾插入")
            text_a = text_a.replace(MAKE_ANCHOR, HELPERS + MAKE_ANCHOR, 1)
            applied += 1
    else:
        print("[跳过] makeButtonWithIcon 已存在")

    # ---- 3) 逐条替换 ----
    for old, new in A_EDITS:
        if old in text_a:
            text_a = text_a.replace(old, new, 1)
            applied += 1
            print(f"  [ok] a: {new[:44]}")
        else:
            print(f"  [跳过] a 锚点未匹配：{old[:52]}")

    for old, new in B_EDITS + [
        (WARN_OLD, WARN_NEW),
        (EM_ICON_OLD, EM_ICON_NEW),
        (STEP_HEAD_OLD, STEP_HEAD_NEW),
    ]:
        if old in text_b:
            text_b = text_b.replace(old, new, 1)
            applied += 1
            print(f"  [ok] b: {new[:52]}")
        else:
            print(f"  [跳过] b 锚点未匹配：{old[:56]}")

    # 对勾在 a
    if TICK_OLD in text_a:
        text_a = text_a.replace(TICK_OLD, TICK_NEW, 1)
        applied += 1
        print("  [ok] a: 步骤完成对勾改由 CSS 呈现")
    else:
        print("  [跳过] a 对勾锚点未匹配")

    # ---- 4) 复核：还有没有残留 ----
    for name, text in (("a", text_a), ("b", text_b)):
        left = len(re.findall(r"make\([^)]*<svg", text))
        print(f"  [复核] {name} 里 make() 传 SVG 的残留：{left} 处")

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
