"""修「规范依据」区倒出原始条文（第 16 轮线上乱码的真正原因）。

真正的问题（上次修错了地方）：
  前端 sourceBlock() 用
      card.appendChild(make("p", "", source.content))
  把**整段检索原文**倒出来。JGJ59 标准里有大量评分表，于是页面上出现：

      物从人的正上方
      通过，扣10 分
      起重机吊具载运人员，扣10 分
      10
      8
      高处
      作业

  5 条来源合计一两千字符的原始条文，把答案淹没了。
  上次我修的是「模型失败时的回退答案」，没修这里。

三处修复：
  1. 清理：剔除纯数字行、评分用语行、过短碎片
  2. 截断：每条只留 180 字预览，不再整段倒出
  3. 折叠：整个依据区收进 <details>，默认收起，需要时再展开

实现约束：分片禁止反斜杠，所以正则里不用 \\s \\d，改用字符类与 String.fromCharCode。

用法：python fix_source_block.py [--dry-run]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
SCRIPT_B = BUILD / "index_script_b.js"
TIERS = BUILD / "v16_tiers.css"

CLEANER = '''    /* ==================================================================
       规范依据的正文清理
       ------------------------------------------------------------------
       检索到的原文来自标准 PDF，含大量评分表碎片与页码：
         「物从人的正上方」「通过，扣10 分」「10」「8」「高处」「作业」
       直接倒出来会淹没答案，所以先清理再截断。

       注意：分片禁止反斜杠，正则一律用字符类/fromCharCode 拼。
       ================================================================== */
    var RE_ONLY_DIGITS = new RegExp("^[0-9]+$");
    var RE_LEAD_DIGITS = new RegExp("^[0-9]{1,4}[ 、.．)）]");
    var RE_SCORE = new RegExp("扣[ " + String.fromCharCode(12288) + "]*[0-9]");
    var RE_GETSCORE = new RegExp("(应得|实得|评分)[ " +
      String.fromCharCode(12288) + "]*分");
    var RE_SPACES = new RegExp("[" + String.fromCharCode(9, 10, 13, 32, 12288) +
      "]+", "g");

    function cleanSourceText(text) {
      var raw = String(text == null ? "" : text);
      var kept = [];
      raw.split(String.fromCharCode(10)).forEach(function (line) {
        var item = line.replace(RE_SPACES, " ").trim();
        if (!item) return;
        if (RE_ONLY_DIGITS.test(item)) return;          /* 页码或评分列 */
        if (RE_SCORE.test(item)) return;                /* 扣X分 */
        if (RE_GETSCORE.test(item)) return;             /* 应得分 */
        if (RE_LEAD_DIGITS.test(item) && item.length < 12) return;
        if (item.length < 6) return;                    /* 过短碎片 */
        kept.push(item);
      });
      var joined = kept.join(" ").replace(RE_SPACES, " ").trim();
      if (joined.length > 180) {
        joined = joined.slice(0, 180) + "…";
      }
      return joined;
    }

'''

OLD_RENDER = '''        block.appendChild(make("div", "src-title", "规范 / 知识依据（" + sources.length + " 条）"));

        var list = make("div", "source-list");

        sources.forEach(function (source, index) {

          var card = make("article", "source-card");

          card.appendChild(make("h4", "", "依据 [" + (index + 1) + "]：" + (source.title || "")));

          if (source.heading) card.appendChild(make("div", "source-meta", source.heading));

          if (source.content) card.appendChild(make("p", "", source.content));

          card.appendChild(make("div", "source-meta",

            "来源：" + (source.source || "") + " " + (source.version || "")

            + (source.category ? " · " + source.category : "")));

          list.appendChild(card);

        });

        block.appendChild(list);'''

NEW_RENDER = '''        /* 依据区收进 details：默认收起，避免原始条文淹没答案 */
        var details = make("details", "src-details");
        details.appendChild(make("summary", "src-title",
          "规范 / 知识依据（" + sources.length + " 条，点击展开）"));

        var list = make("div", "source-list");

        sources.forEach(function (source, index) {

          var card = make("article", "source-card");

          card.appendChild(make("h4", "", "依据 [" + (index + 1) + "]：" + (source.title || "")));

          if (source.heading) card.appendChild(make("div", "source-meta", source.heading));

          /* 清理后再显示：只给一段可读的预览，不再整段倒出条文 */
          var preview = cleanSourceText(source.content);
          if (preview) {
            card.appendChild(make("p", "source-excerpt", preview));
          } else {
            card.appendChild(make("p", "source-excerpt is-empty",
              "这一条检索到的主要是标准评分表，文字不适合直接阅读，已省略。"));
          }

          card.appendChild(make("div", "source-meta",

            "来源：" + (source.source || "") + " " + (source.version || "")

            + (source.category ? " · " + source.category : "")));

          list.appendChild(card);

        });

        details.appendChild(list);
        block.appendChild(details);'''

CSS = """

/* ==========================================================================
   规范依据区（§16 线上乱码修复）
   --------------------------------------------------------------------------
   原来把整段检索原文倒出来，JGJ59 的评分表碎片淹没了答案。
   现在收进 details 默认收起，正文只给清理后的预览。
   ========================================================================== */
.src-details { margin-top: 4px; }
.src-details > summary {
  cursor: pointer; list-style: none; display: flex; align-items: center; gap: 8px;
}
.src-details > summary::-webkit-details-marker { display: none; }
.src-details > summary::before {
  content: ""; width: 0; height: 0; flex: 0 0 auto;
  border-left: 5px solid currentColor;
  border-top: 4px solid transparent; border-bottom: 4px solid transparent;
  transition: transform .15s ease;
}
.src-details[open] > summary::before { transform: rotate(90deg); }
.source-excerpt {
  font-size: var(--fs-sm); line-height: 1.75; color: var(--i600);
  max-width: 42em;
}
.source-excerpt.is-empty { color: var(--i400); font-style: normal; }
.source-list { margin-top: 12px; }
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    applied = 0
    script = SCRIPT_B.read_text(encoding="utf-8")
    tiers = TIERS.read_text(encoding="utf-8")

    if "function cleanSourceText" not in script:
        anchor = "    function sourceBlock(answer) {"
        if anchor not in script:
            print("[FAIL] 找不到 sourceBlock")
            return 1
        script = script.replace(anchor, CLEANER + anchor, 1)
        applied += 1
        print("[ok] 新增 cleanSourceText 清理函数")
    else:
        print("[跳过] 清理函数已存在")

    if "src-details" not in script:
        if OLD_RENDER not in script:
            print("[跳过] 渲染锚点未匹配（可能已改）")
        else:
            script = script.replace(OLD_RENDER, NEW_RENDER, 1)
            applied += 1
            print("[ok] 依据区改为折叠 + 清理预览")
    else:
        print("[跳过] 依据区已改")

    if "线上乱码修复" not in tiers:
        tiers = tiers.rstrip() + CSS
        applied += 1
        print("[ok] 样式已加入")

    if script.count(chr(92)):
        print(f"[FAIL] 分片含 {script.count(chr(92))} 个反斜杠（硬约束）")
        return 1
    print("[ok] 无反斜杠")

    if args.dry_run:
        print(f"（dry-run，未写入；{applied} 处）")
        return 0
    SCRIPT_B.write_text(script, encoding="utf-8")
    TIERS.write_text(tiers, encoding="utf-8")
    print(f"[ok] 已写入（{applied} 处）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
