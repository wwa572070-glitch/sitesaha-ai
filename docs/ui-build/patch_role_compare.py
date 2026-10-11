"""§7 方向 5：工种专项改「✗ 典型违规 / ✓ 必守规矩」对比式排版。

用户说"缺乏创意性"，方向 5 是"对比式教学排版：用 ✗/✓ 左右对照卡，
而不是长段落"。

现状：三个 role-block（常见风险 / 必守规矩 / 典型违规）等宽并排，
读起来是三个平行清单，看不出"违规 ↔ 正确做法"的对应关系。

改法：
  · 保留「常见风险」独立一行（它是背景资料，不是对照项）
  · 「✗ 典型违规」与「✓ 必守规矩」改为**左右对照卡**，
    左边红底、右边绿底，视觉上直接对撞
  · 「防护用品」独立一行（它是清单，不是对照项）

数据来源不变（data.violations / data.rules），不改内容只改排版。

用法：python patch_role_compare.py [--dry-run]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
SCRIPT_A = BUILD / "index_script_a.js"
TIERS = BUILD / "v16_tiers.css"

OLD = '''      var cols = make("div", "role-cols");
      var haz = make("div", "role-block is-danger");
      haz.appendChild(iconText("i-alert", "常见风险"));
      var hazList = make("ul");
      (data.hazards || []).forEach(function (text) { hazList.appendChild(make("li", "", text)); });
      haz.appendChild(hazList);
      cols.appendChild(haz);

      var safe = make("div", "role-block is-safe");
      safe.appendChild(iconText("i-check", "必守规矩"));
      var ruleList = make("ul");
      (data.rules || []).forEach(function (text) { ruleList.appendChild(make("li", "", text)); });
      safe.appendChild(ruleList);
      cols.appendChild(safe);

      var bad = make("div", "role-block is-danger");
      bad.appendChild(iconText("i-close", "典型违规"));
      var badList = make("ul");
      (data.violations || []).forEach(function (text) { badList.appendChild(make("li", "", text)); });
      bad.appendChild(badList);
      cols.appendChild(bad);

      var ppe = make("div", "role-block");
      ppe.appendChild(iconText("i-helmet", "防护用品"));
      var ppeList = make("ul");
      (data.ppe || []).forEach(function (text) { ppeList.appendChild(make("li", "", text)); });
      ppe.appendChild(ppeList);
      cols.appendChild(ppe);
      host.appendChild(cols);'''

NEW = '''      /* ---- 常见风险：背景资料，独立一行 ---- */
      var haz = make("div", "role-block is-danger role-block-wide");
      haz.appendChild(iconText("i-alert", "常见风险"));
      var hazList = make("ul", "role-chip-list");
      var hazards = data.hazards || [];
      if (hazards.length) {
        hazards.forEach(function (text) {
          hazList.appendChild(make("li", "role-chip", text));
        });
      } else {
        hazList.appendChild(make("li", "role-chip", "本工种暂无单独列出的风险条目。"));
      }
      haz.appendChild(hazList);
      host.appendChild(haz);

      /* ---- ✗ 典型违规 / ✓ 必守规矩：左右对照（§7 方向 5）----
         这两块讲的是同一件事的两面，并排才看得出对应关系。
         左边红底、右边绿底，视觉上直接对撞。 */
      var compare = make("div", "role-compare");
      var wrong = make("div", "role-compare-col is-wrong");
      wrong.appendChild(make("b", "role-compare-head", "✗ 典型违规"));
      var wrongList = make("ul");
      var violations = data.violations || [];
      if (violations.length) {
        violations.forEach(function (text) { wrongList.appendChild(make("li", "", text)); });
      } else {
        wrongList.appendChild(make("li", "", "本工种暂无单独列出的典型违规。"));
      }
      wrong.appendChild(wrongList);
      compare.appendChild(wrong);

      var right = make("div", "role-compare-col is-right");
      right.appendChild(make("b", "role-compare-head", "✓ 必守规矩"));
      var rightList = make("ul");
      var rules = data.rules || [];
      if (rules.length) {
        rules.forEach(function (text) { rightList.appendChild(make("li", "", text)); });
      } else {
        rightList.appendChild(make("li", "", "本工种暂无单独列出的必守规矩。"));
      }
      right.appendChild(rightList);
      compare.appendChild(right);
      host.appendChild(compare);

      /* ---- 防护用品：清单，独立一行 ---- */
      var ppe = make("div", "role-block role-block-wide");
      ppe.appendChild(iconText("i-helmet", "防护用品"));
      var ppeList = make("ul", "role-chip-list");
      var ppeItems = data.ppe || [];
      if (ppeItems.length) {
        ppeItems.forEach(function (text) {
          ppeList.appendChild(make("li", "role-chip", text));
        });
      } else {
        ppeList.appendChild(make("li", "role-chip", "按项目交底配备，以现场要求为准。"));
      }
      ppe.appendChild(ppeList);
      host.appendChild(ppe);'''

CSS = """

/* ==========================================================================
   §7 方向 5：工种专项对比式教学排版
   --------------------------------------------------------------------------
   原来「常见风险 / 必守规矩 / 典型违规 / 防护用品」四块等宽并排，
   读起来是四个平行清单，看不出"违规 ↔ 正确做法"的对应关系。
   改为：风险与防护用品独立成行，违规与规矩左右对撞。
   ========================================================================== */
.role-block-wide { grid-column: 1 / -1; }
.role-chip-list {
  display: flex; flex-wrap: wrap; gap: 8px;
  list-style: none; margin: 0; padding: 0;
}
.role-chip {
  padding: 4px 10px; border-radius: 999px;
  background: var(--surface-soft); border: 1px solid var(--line);
  font-size: var(--fs-sm); color: var(--i700);
}
.role-block.is-danger .role-chip {
  background: var(--risk-high-bg); border-color: var(--risk-high);
  color: var(--risk-high-text);
}

.role-compare {
  display: grid; grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px; margin-top: 12px;
}
.role-compare-col { border-radius: var(--r-md); padding: 12px 16px; }
.role-compare-col.is-wrong {
  background: var(--risk-high-bg); border-left: 4px solid var(--risk-high);
}
.role-compare-col.is-right {
  background: var(--risk-low-bg); border-left: 4px solid var(--risk-low);
}
.role-compare-head {
  display: block; font-size: var(--fs-md); font-weight: 800; margin-bottom: 6px;
}
.role-compare-col.is-wrong .role-compare-head { color: var(--risk-high-text); }
.role-compare-col.is-right .role-compare-head { color: var(--risk-low-text); }
.role-compare-col ul { margin: 0; padding-left: 18px; }
.role-compare-col li {
  font-size: var(--fs-sm); line-height: 1.7; color: var(--i700); margin-bottom: 4px;
}
.role-compare-col li:last-child { margin-bottom: 0; }
.role-block + .role-block { margin-top: 12px; }

@media (max-width: 640px) {
  .role-compare { grid-template-columns: minmax(0, 1fr); }
}
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    applied = 0
    script = SCRIPT_A.read_text(encoding="utf-8")
    tiers = TIERS.read_text(encoding="utf-8")

    if "role-compare" not in script:
        if OLD not in script:
            print("[FAIL] 找不到 role-cols 锚点")
            return 1
        script = script.replace(OLD, NEW, 1)
        applied += 1
        print("[ok] 工种专项改为 ✗/✓ 左右对照")
    else:
        print("[跳过] 已是对照排版")

    if "工种专项对比式教学排版" not in tiers:
        tiers = tiers.rstrip() + CSS
        applied += 1
        print("[ok] 对照样式已加入")

    if script.count(chr(92)):
        print("[FAIL] 引入反斜杠")
        return 1
    print("[ok] 无反斜杠")

    if args.dry_run:
        print(f"（dry-run，未写入；{applied} 处）")
        return 0
    SCRIPT_A.write_text(script, encoding="utf-8")
    TIERS.write_text(tiers, encoding="utf-8")
    print(f"[ok] 已写入（{applied} 处）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
