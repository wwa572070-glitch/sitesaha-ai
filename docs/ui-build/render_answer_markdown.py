"""让问答回答正确渲染 Markdown（第 16 轮，配置文字模型后暴露的问题）。

背景：
  配好文字模型后，回答从「检索摘要」变成模型生成的长文，
  带 `**加粗**`、`1.` 编号列表这类标记。而前端用 textContent 输出，
  用户在页面上会看到一堆星号。

  这是 §3.3 我在**拍照**路径修过的同一类问题，文字问答路径当时没发现
  （因为没配模型时返回的是纯文本摘要）。

修法：
  极简 Markdown 渲染器，只支持回答里真实出现的三种：
    1. **加粗**
    2. 无序列表（- * •）
    3. 有序列表（1. 2、）
  其余按纯文本处理。

安全：**先转义 HTML，再渲染白名单标记**。
  模型输出是不可信内容，绝不能直接 innerHTML。

实现约束：分片里不能出现反斜杠（inject.py 硬性拒绝），
  所以正则一律用 RegExp 构造器拼字符串，不用字面量转义。

用法：python render_answer_markdown.py [--dry-run]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
SCRIPT_A = BUILD / "index_script_a.js"
SCRIPT_B = BUILD / "index_script_b.js"

RENDERER = '''    /* ==================================================================
       回答正文的极简 Markdown 渲染
       ------------------------------------------------------------------
       只支持回答里真实出现的三种标记：**加粗**、无序列表、有序列表。
       安全前提：先把 HTML 全转义，再替换白名单标记 ——
       模型输出属于不可信内容，绝不能直接 innerHTML。

       注意：分片里不能写反斜杠，所以正则都用 RegExp 构造器拼。
       ================================================================== */
    /* 分片禁止出现反斜杠字符，所以正则里的转义用 fromCharCode(92) 拼出来。
       星号在正则里是量词，必须转义成「反斜杠 + 星号」才能匹配字面量。 */
    var ESC = String.fromCharCode(92);
    var STAR = String.fromCharCode(42);
    var RE_BOLD = new RegExp(ESC + STAR + ESC + STAR + "([^" + STAR + "]+)" +
      ESC + STAR + ESC + STAR, "g");
    var RE_BULLET = new RegExp("^[" + String.fromCharCode(45, 42, 8226) + "]" +
      String.fromCharCode(32) + "+(.*)$");
    var RE_SPACE = new RegExp("^" + String.fromCharCode(32) + "+");

    /* 有序列表手写解析，不用正则 —— 数字类会引入反斜杠 d。 */
    function matchNumbered(line) {
      var index = 0;
      while (index < line.length) {
        var code = line.charCodeAt(index);
        if (code < 48 || code > 57) break;
        index += 1;
      }
      if (index === 0 || index >= line.length) return null;
      var sep = line.charAt(index);
      if (sep !== "." && sep !== ")" && sep !== String.fromCharCode(12289)) return null;
      var rest = line.slice(index + 1);
      if (!rest.length) return null;
      if (rest.charAt(0) !== String.fromCharCode(32)) return null;
      return [rest.replace(RE_SPACE, "")];
    }

    function escapeHtml(text) {
      return String(text == null ? "" : text)
        .split("&").join("&amp;")
        .split("<").join("&lt;")
        .split(">").join("&gt;")
        .split(String.fromCharCode(34)).join("&quot;");
    }

    function stripTrailingSpaces(line) {
      var end = line.length;
      while (end > 0) {
        var code = line.charCodeAt(end - 1);
        if (code === 32 || code === 9 || code === 13 || code === 160) end -= 1;
        else break;
      }
      return line.slice(0, end);
    }

    function renderAnswerBody(text) {
      var host = document.createDocumentFragment();
      var lines = String(text == null ? "" : text).split(String.fromCharCode(10));
      var list = null;
      var listKind = "";

      function closeList() {
        if (list) {
          host.appendChild(list);
          list = null;
          listKind = "";
        }
      }

      function inline(raw) {
        /* 先转义，再把 **x** 换成 strong。顺序不能反。 */
        return escapeHtml(raw).replace(RE_BOLD, "<strong>$1</strong>");
      }

      lines.forEach(function (rawLine) {
        var line = stripTrailingSpaces(rawLine);
        if (!line.trim()) {
          closeList();
          return;
        }
        var bullet = line.match(RE_BULLET);
        var numbered = bullet ? null : matchNumbered(line);
        var kind = bullet ? "ul" : (numbered ? "ol" : "");

        if (kind) {
          if (listKind !== kind) {
            closeList();
            list = document.createElement(kind);
            list.className = "answer-list";
            listKind = kind;
          }
          var item = document.createElement("li");
          item.innerHTML = inline(bullet ? bullet[1] : numbered[1]);
          list.appendChild(item);
          return;
        }

        closeList();
        var para = document.createElement("p");
        para.className = "answer-line";
        para.innerHTML = inline(line);
        host.appendChild(para);
      });

      closeList();
      return host;
    }

'''

CALL_OLD = 'bubble.appendChild(make("div", "answer-body", answer.text || ""));'
CALL_NEW = '''var body = make("div", "answer-body");
      body.appendChild(renderAnswerBody(answer.text || ""));
      bubble.appendChild(body);'''

CSS = """

/* ==========================================================================
   回答正文排版（§3.3：模型返回 Markdown，需要正确渲染）
   ========================================================================== */
.answer-body .answer-line { margin: 0 0 8px; }
.answer-body .answer-line:last-child { margin-bottom: 0; }
.answer-body .answer-line strong { color: var(--i900); font-weight: 800; }
.answer-body .answer-list { margin: 0 0 8px; padding-left: 20px; }
.answer-body .answer-list li { margin-bottom: 4px; line-height: 1.75; }
.answer-body .answer-list li strong { color: var(--i900); font-weight: 800; }
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    applied = 0
    script = SCRIPT_A.read_text(encoding="utf-8")
    text_b = SCRIPT_B.read_text(encoding="utf-8")
    tiers = BUILD / "v16_tiers.css"
    css_text = tiers.read_text(encoding="utf-8")

    if "function renderAnswerBody" not in script:
        anchor = "    function clear(node) {"
        if anchor not in script:
            print("[FAIL] 找不到 clear 锚点")
            return 1
        script = script.replace(anchor, RENDERER + anchor, 1)
        applied += 1
        print("[ok] 新增 renderAnswerBody / escapeHtml")
    else:
        print("[跳过] 渲染器已存在")

    if CALL_OLD in text_b:
        text_b = text_b.replace(CALL_OLD, CALL_NEW, 1)
        applied += 1
        print("[ok] 回答正文改走 Markdown 渲染")
    elif "renderAnswerBody" in text_b:
        print("[跳过] 调用点已改")
    else:
        print("[跳过] 调用点锚点未匹配")

    if "回答正文排版" not in css_text:
        css_text = css_text.rstrip() + CSS
        tiers.write_text(css_text, encoding="utf-8")
        applied += 1
        print("[ok] 样式已加入")

    for name, text in (("a", script), ("b", text_b)):
        if text.count(chr(92)):
            count = text.count(chr(92))
            print(f"[FAIL] {name} 含 {count} 个反斜杠（分片硬约束）")
            return 1
    print("[ok] 无反斜杠")

    if args.dry_run:
        print(f"（dry-run，未写入；{applied} 处）")
        return 0
    SCRIPT_A.write_text(script, encoding="utf-8")
    SCRIPT_B.write_text(text_b, encoding="utf-8")
    print(f"[ok] 已写入（{applied} 处）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
