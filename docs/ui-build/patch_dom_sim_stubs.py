"""给 DOM 模拟器的 document 桩补两个方法，并加 §3.1 的防回归断言。

问题：模拟器缺 document.createDocumentFragment 与 createElementNS，
而页面的 makeIcon()/iconText() 用它们建图标节点。
模拟器本该像浏览器一样提供这些 —— 补齐它，而不是让页面绕开标准 API。

同时加断言（§13 要求）：
  document.body.innerText 不得包含 "<svg"、"<use"、"undefined"、"NaN"

用法：python patch_dom_sim_stubs.py [--dry-run]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
SIM = BUILD / "run_dom_sim.js"

OLD_DOC = '''  createElement: (tag) => makeElement(tag),
  createTextNode: (text) => ({ nodeType: 3, textContent: String(text) }),'''

NEW_DOC = '''  createElement: (tag) => makeElement(tag),
  // 页面用 createElementNS 建 SVG 图标节点；浏览器里一定有，模拟器也要有。
  createElementNS: (ns, tag) => makeElement(tag),
  // makeIcon 的「图标 + 文字」片段用 DocumentFragment；
  // 用一个 appendChild 会聚合子节点的普通对象来模拟即可。
  createDocumentFragment: () => ({
    nodeType: 11,
    childNodes: [],
    appendChild(child) { this.childNodes.push(child); return child; },
    get textContent() {
      return this.childNodes.map((n) => n.textContent || "").join("");
    },
  }),
  createTextNode: (text) => ({ nodeType: 3, textContent: String(text) }),'''

ASSERT_ANCHOR = '''  console.log("\\nDOM simulation: OK");'''

ASSERT_NEW = '''  // §13 防回归：页面上不得出现被转义成文本的标签，或未填充的占位值
  const visibleText = documentStub.body
    ? String(documentStub.body.innerText || documentStub.body.textContent || "")
    : "";
  const forbidden = ["<svg", "<use", "undefined", "NaN", "Expecting value"];
  const leaked = forbidden.filter((token) => visibleText.indexOf(token) >= 0);
  if (leaked.length) {
    console.error("[FAIL] 页面可见文本里出现不该出现的内容：" + leaked.join("、"));
    const at = visibleText.indexOf(leaked[0]);
    console.error("  上下文: " + JSON.stringify(visibleText.slice(Math.max(0, at - 40), at + 80)));
    process.exit(1);
  }
  console.log("可见文本检查: OK（无 <svg / <use / undefined / NaN / Expecting value）");

  console.log("\\nDOM simulation: OK");'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    text = SIM.read_text(encoding="utf-8")
    changed = 0

    if "createDocumentFragment" not in text:
        if OLD_DOC not in text:
            print("[FAIL] 找不到 document 桩锚点")
            return 1
        text = text.replace(OLD_DOC, NEW_DOC, 1)
        changed += 1
        print("[ok] 补 createElementNS 与 createDocumentFragment")
    else:
        print("[跳过] 桩已补齐")

    if "可见文本检查" not in text:
        if ASSERT_ANCHOR not in text:
            print("[FAIL] 找不到 DOM simulation OK 锚点")
            return 1
        text = text.replace(ASSERT_ANCHOR, ASSERT_NEW, 1)
        changed += 1
        print("[ok] 加防回归断言（innerText 不得含 <svg / <use / undefined / NaN）")
    else:
        print("[跳过] 断言已存在")

    if args.dry_run:
        print(f"（dry-run，未写入；{changed} 处）")
        return 0
    SIM.write_text(text, encoding="utf-8")
    print(f"[ok] 已写入（{changed} 处）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
