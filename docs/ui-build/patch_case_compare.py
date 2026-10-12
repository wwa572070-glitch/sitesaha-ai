"""§5-3 案例卡改造为 ✗/✓ 对照（第 21 轮）。

现有 caseCard() 是平铺段落：
    事故 / 隐患经过：…
    主要致险因素：…
    后果与影响：…
    防控要点：…

改成左右对照（桌面双栏 / 移动端上下）：
    ✗ 错误做法        ← item.what_happened（真实经过）
      ↳ 为什么危险     ← item.why_dangerous（真实致险因素）
    ✓ 正确做法        ← item.lesson（真实防控要点）
      结果            ← item.consequence

严格约束：
  · 只用案例里已有的字段，**不编造**法规条文、事故数据或标准编号
  · 图标 + 标签 + 文字共同表意，不单纯依赖红绿
  · 保留 compact 分支（首页每日案例用）

用法：python patch_case_compare.py [--dry-run]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
SCRIPT_A = BUILD / "index_script_a.js"
TIERS = BUILD / "v16_tiers.css"

OLD = '''    function caseCard(item, compact) {
      var card = make("article", "case-card");
      card.dataset.category = item.category || "";
      card.appendChild(make("span", "case-tag", item.category || "未分类"));
      card.appendChild(make("h3", "", item.title || ""));
      var pairs = [
        ["事故 / 隐患经过", item.what_happened],
        ["主要致险因素", item.why_dangerous],
      ];
      pairs.forEach(function (pair) {
        if (!pair[1]) return;
        var p = make("p");
        p.appendChild(make("span", "case-label", pair[0] + "："));
        p.appendChild(document.createTextNode(pair[1]));
        card.appendChild(p);
      });
      if (!compact) {
        var detail = make("div", "case-detail");
        if (item.consequence) {
          var p1 = make("p");
          p1.appendChild(make("span", "case-label", "后果与影响："));
          p1.appendChild(document.createTextNode(item.consequence));
          detail.appendChild(p1);
        }
        if (item.lesson) detail.appendChild(make("p", "case-lesson", "防控要点：" + item.lesson));
        detail.appendChild(make("div", "case-source", "来源：" + (item.source_name || "未标注") + " · " + (item.date || "")));
        card.appendChild(detail);
      }
      return card;
    }'''

NEW = '''    /* ==================================================================
       §5-3 案例对照卡（第 21 轮）
       ------------------------------------------------------------------
       左「✗ 错误做法」= 真实经过 + 真实致险因素
       右「✓ 正确做法」= 真实防控要点（+ 结果）

       只用案例里已有的字段，不编造条文、数据或标准号。
       图标 + 标签 + 文字共同表意，不单纯依赖红绿。
       ================================================================== */
    function caseCompare(item) {
      var grid = make("div", "case-compare");

      /* ---- 左：错误做法 ---- */
      var wrong = make("section", "case-side is-wrong");
      var wrongHead = make("div", "case-side-head");
      wrongHead.appendChild(makeIcon("i-close", "ico ico-sm"));
      wrongHead.appendChild(make("b", "", "错误做法"));
      wrong.appendChild(wrongHead);

      if (item.what_happened) {
        wrong.appendChild(make("p", "case-side-body", item.what_happened));
      }
      if (item.why_dangerous) {
        var why = make("div", "case-why");
        why.appendChild(makeIcon("i-alert", "ico ico-sm"));
        var whyText = make("span");
        whyText.appendChild(make("b", "", "为什么危险："));
        whyText.appendChild(document.createTextNode(item.why_dangerous));
        why.appendChild(whyText);
        wrong.appendChild(why);
      }
      grid.appendChild(wrong);

      /* ---- 右：正确做法 ---- */
      var right = make("section", "case-side is-right");
      var rightHead = make("div", "case-side-head");
      rightHead.appendChild(makeIcon("i-check", "ico ico-sm"));
      rightHead.appendChild(make("b", "", "正确做法"));
      right.appendChild(rightHead);

      if (item.lesson) {
        right.appendChild(make("p", "case-side-body", item.lesson));
      } else {
        /* 没有防控要点就不硬编 —— 如实说明 */
        right.appendChild(make("p", "case-side-body is-empty",
          "这条通报没有给出防控要点，请以现场安全交底和适用规范为准。"));
      }
      if (item.consequence) {
        var outcome = make("div", "case-outcome");
        outcome.appendChild(make("b", "", "结果："));
        outcome.appendChild(document.createTextNode(item.consequence));
        right.appendChild(outcome);
      }
      grid.appendChild(right);

      return grid;
    }

    function caseCard(item, compact) {
      var card = make("article", "case-card");
      card.dataset.category = item.category || "";
      card.appendChild(make("span", "case-tag", item.category || "未分类"));
      card.appendChild(make("h3", "", item.title || ""));
      card.appendChild(caseCompare(item));
      if (!compact) {
        card.appendChild(make("div", "case-source",
          "来源：" + (item.source_name || "未标注") + " · " + (item.date || "")));
      }
      return card;
    }'''

CSS = """

/* ==========================================================================
   §5-3 案例对照卡（第 21 轮）
   --------------------------------------------------------------------------
   桌面双栏对照，移动端上下堆叠。
   左「错误做法」用克制的危险色，右「正确做法」用成功色，
   但两侧都有图标 + 文字标签，不单纯依赖颜色表意。
   ========================================================================== */
.case-compare {
  display: grid; grid-template-columns: 1fr 1fr; gap: 12px;
  margin: 12px 0 4px;
}
.case-side {
  border-radius: var(--r-sm); padding: 12px 14px;
  border: 1px solid var(--line); background: var(--surface);
  min-width: 0;
}
.case-side.is-wrong { border-left: 4px solid var(--risk-high); background: var(--risk-high-bg); }
.case-side.is-right { border-left: 4px solid var(--risk-low); background: var(--risk-low-bg); }
.case-side-head {
  display: flex; align-items: center; gap: 6px;
  font-size: var(--fs-sm); margin-bottom: 8px;
}
.case-side.is-wrong .case-side-head { color: var(--risk-high-text); }
.case-side.is-right .case-side-head { color: var(--risk-low-text); }
.case-side-body {
  margin: 0; font-size: var(--fs-sm); line-height: 1.7; color: var(--i700);
}
.case-side-body.is-empty { color: var(--i500); }
.case-why {
  display: flex; gap: 6px; align-items: flex-start;
  margin-top: 10px; padding-top: 10px;
  border-top: 1px dashed var(--line);
  font-size: var(--fs-xs); line-height: 1.7; color: var(--i600);
}
.case-outcome {
  margin-top: 10px; padding-top: 10px;
  border-top: 1px dashed var(--line);
  font-size: var(--fs-xs); line-height: 1.7; color: var(--i600);
}

@media (max-width: 720px) {
  .case-compare { grid-template-columns: 1fr; gap: 10px; }
}

/* 微交互：案例卡展开（§5-5） */
.case-detail {
  animation: caseReveal .22s ease-out;
}
@keyframes caseReveal {
  from { opacity: 0; transform: translateY(-4px); }
  to { opacity: 1; transform: none; }
}
@media (prefers-reduced-motion: reduce) {
  .case-detail { animation: none; }
}
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    text = SCRIPT_A.read_text(encoding="utf-8")
    tiers = TIERS.read_text(encoding="utf-8")
    applied = 0

    if "caseCompare" in text:
        print("  [跳过] 案例对照卡已改")
    else:
        old = "\n\n".join(OLD.split("\n"))
        new = "\n\n".join(NEW.split("\n"))
        if old in text:
            text = text.replace(old, new, 1)
            applied += 1
            print("  [ok] caseCard 改为 ✗/✓ 对照结构")
        elif OLD in text:
            text = text.replace(OLD, NEW, 1)
            applied += 1
            print("  [ok] caseCard 改为 ✗/✓ 对照结构（无空行格式）")
        else:
            print("  [FAIL] caseCard 锚点未匹配")
            return 1

    if "§5-3 案例对照卡" not in tiers:
        tiers = tiers.rstrip() + CSS
        applied += 1
        print("  [ok] 样式已加入")

    if text.count(chr(92)):
        print("[FAIL] script 含反斜杠")
        return 1
    print("  [ok] 无反斜杠")

    if args.dry_run:
        print(f"（dry-run，未写入；{applied} 处）")
        return 0
    SCRIPT_A.write_text(text, encoding="utf-8")
    TIERS.write_text(tiers, encoding="utf-8")
    print(f"[ok] 已写入（{applied} 处）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
