"""第 24 轮 A：识别结果结构化渲染。

已核实的真实结构（inspect_structured.py 实测）：
  structured = {
    work_type: str,
    risks: [ { where: str, what: str, action: str } ],   # action 可能为空串
    uncertain: [ str ],                                   # 注意不是 unclear
    citations: [ { index: int|null, title: str } ]
  }

指令里的 actions / unclear **不存在**，实际是嵌在 risks 里的 action 与 uncertain。
所以按真实字段渲染，不自造结构。

四段式（按指令 A/B/C/D）：
  A 作业场景与风险结论 —— work_type + 真实风险条数
  B 图片证据与风险位置 —— where 位置标签 + what 现象
  C 整改建议         —— 每条 risk 自带的 action（关联关系是数据本身给的，不编造）
  D 待确认信息       —— uncertain，并提示人工复核

容错：
  · structured 缺失 / 非对象 / 字段为空数组 → 回退显示原始 text
  · action 为空串 → 不显示该条措施，也不补造
  · 三段都空 → 明确说明「没有识别到可报告的风险」

用法：python patch_result_render.py [--dry-run]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
SCRIPT_B = BUILD / "index_script_b.js"
TIERS = BUILD / "v16_tiers.css"

RENDERER = '''    /* ==================================================================
       第 24 轮 A：识别结果结构化渲染
       ------------------------------------------------------------------
       后端一直返回 structured，但前端只用了 text，结构化数据全被浪费。
       这里按真实字段分四段渲染：

         A 作业场景与风险结论   work_type + 真实风险条数
         B 图片证据与风险位置   risks[].where（位置）+ risks[].what（现象）
         C 整改建议             risks[].action（关联关系来自数据本身）
         D 待确认信息           uncertain[]

       容错：structured 不可用就回退到原始文本，绝不让结果区崩掉。
       不伪造坐标、置信度、检测框或任何后端没给的字段。
       ================================================================== */
    function isNonEmptyString(value) {
      return typeof value === "string" && value.trim().length > 0;
    }

    function renderPhotoResult(payload, host) {
      var data = payload && payload.structured;
      if (!data || typeof data !== "object") return false;

      var risks = Array.isArray(data.risks) ? data.risks.filter(function (item) {
        return item && (isNonEmptyString(item.what) || isNonEmptyString(item.where));
      }) : [];
      var uncertain = Array.isArray(data.uncertain) ? data.uncertain.filter(isNonEmptyString) : [];
      var actions = risks.filter(function (item) { return isNonEmptyString(item.action); });
      var workType = isNonEmptyString(data.work_type) ? data.work_type.trim() : "";

      /* 三段全空 —— 如实说明，不硬凑 */
      if (!workType && !risks.length && !uncertain.length) return false;

      var wrap = make("div", "ins-result");

      /* ---- A 作业场景与风险结论 ---- */
      var head = make("section", "ins-block ins-summary");
      head.appendChild(make("h3", "ins-block-title", "识别结论"));
      if (workType) {
        var wt = make("p", "ins-worktype");
        wt.appendChild(make("span", "ins-worktype-label", "作业场景"));
        wt.appendChild(make("span", "ins-worktype-value", workType));
        head.appendChild(wt);
      } else {
        head.appendChild(make("p", "ins-worktype is-empty",
          "未能从这张照片确定作业场景。请把作业面、防护设施和周边环境一起拍进去。"));
      }
      var metric = make("div", "ins-metric");
      metric.appendChild(make("span", "ins-metric-num", String(risks.length)));
      metric.appendChild(make("span", "ins-metric-unit", "条可见风险"));
      if (uncertain.length) {
        metric.appendChild(make("span", "ins-metric-note",
          "另有 " + uncertain.length + " 项待确认"));
      }
      head.appendChild(metric);
      wrap.appendChild(head);

      /* ---- B 图片证据与风险位置 ---- */
      if (risks.length) {
        var section = make("section", "ins-block");
        section.appendChild(make("h3", "ins-block-title",
          "风险位置与现象（" + risks.length + " 条）"));
        var list = make("ol", "ins-risk-list");
        risks.forEach(function (item) {
          var row = make("li", "ins-risk");
          if (isNonEmptyString(item.where)) {
            /* 位置标签：模型给的是画面方位描述，如实展示，不换算成坐标 */
            var where = make("span", "ins-risk-where");
            where.appendChild(makeIcon("i-search", "ico ico-sm"));
            where.appendChild(document.createTextNode(item.where));
            row.appendChild(where);
          }
          row.appendChild(make("p", "ins-risk-what",
            isNonEmptyString(item.what) ? item.what : "（这一条没有文字描述）"));
          /* C 整改建议紧跟在对应风险下 —— 关联关系来自数据本身 */
          if (isNonEmptyString(item.action)) {
            var fix = make("div", "ins-risk-action");
            fix.appendChild(makeIcon("i-check", "ico ico-sm"));
            var fixText = make("span");
            fixText.appendChild(make("b", "", "立即动作："));
            fixText.appendChild(document.createTextNode(item.action));
            fix.appendChild(fixText);
            row.appendChild(fix);
          }
          list.appendChild(row);
        });
        section.appendChild(list);
        if (!actions.length) {
          section.appendChild(make("p", "ins-note",
            "这张照片的识别结果没有给出逐条整改动作，请以现场安全交底和项目制度为准。"));
        }
        wrap.appendChild(section);
      } else {
        var clean = make("section", "ins-block ins-clean");
        clean.appendChild(make("h3", "ins-block-title", "未识别到可报告的风险"));
        clean.appendChild(make("p", "ins-note",
          "这不代表现场安全。换个角度多拍几张，或请现场安全员确认。"));
        wrap.appendChild(clean);
      }

      /* ---- D 待确认信息 ---- */
      if (uncertain.length) {
        var pending = make("section", "ins-block ins-pending");
        var title = make("h3", "ins-block-title");
        title.appendChild(makeIcon("i-alert", "ico ico-sm"));
        title.appendChild(document.createTextNode("待确认（" + uncertain.length + " 项）"));
        pending.appendChild(title);
        var ul = make("ul", "ins-pending-list");
        uncertain.forEach(function (text) { ul.appendChild(make("li", "", text)); });
        pending.appendChild(ul);
        pending.appendChild(make("p", "ins-note",
          "以上内容模型无法确认，需要你补充现场信息或请安全员人工复核。"));
        wrap.appendChild(pending);
      }

      /* ---- 免责声明（与页面既有口径一致） ---- */
      wrap.appendChild(make("p", "ins-disclaimer",
        "本结果仅辅助识别照片中肉眼可见的风险，不替代现场安全员检查，也不证明现场完全合规。"));

      /* 服务端告警（如模型降级）如实透出 */
      (payload.warnings || []).forEach(function (warning) {
        wrap.appendChild(makeIconText("div", "warn-box", "i-alert", "ico ico-sm", warning));
      });

      host.textContent = "";
      host.appendChild(wrap);
      return true;
    }

'''

OLD_SUCCESS = '''        var text = payload.text || "";
        (payload.warnings || []).forEach(function (warning) { text += NL2 + "⚠ " + warning; });
        if (payload.sources && payload.sources.length) {
          text += NL2 + "参考依据：" + payload.sources.slice(0, 3).map(function (item) {
            return item.title;
          }).join("；");
        }
        result.textContent = text || "服务端没有返回内容。";'''

NEW_SUCCESS = '''        /* 优先结构化渲染；structured 不可用时回退到原始文本 */
        result.textContent = "";
        if (!renderPhotoResult(payload, result)) {
          var text = payload.text || "";
          (payload.warnings || []).forEach(function (warning) { text += NL2 + "⚠ " + warning; });
          if (payload.sources && payload.sources.length) {
            text += NL2 + "参考依据：" + payload.sources.slice(0, 3).map(function (item) {
              return item.title;
            }).join("；");
          }
          result.textContent = text || "服务端没有返回内容。";
        }'''

CSS = """

/* ==========================================================================
   第 24 轮 A · 识别结果结构化渲染
   --------------------------------------------------------------------------
   后端一直返回 structured，前端却只显示纯文本。这里按真实字段分四段呈现：
   结论 / 风险位置与现象 / 整改建议 / 待确认，并保留免责声明。
   ========================================================================== */
.ins-result { display: flex; flex-direction: column; gap: 16px; }
.ins-block {
  border: 1px solid var(--line); border-radius: var(--r-md);
  background: var(--surface); padding: 16px;
}
.ins-block-title {
  margin: 0 0 12px; font-size: var(--fs-md); font-weight: 800; color: var(--brand);
  display: flex; align-items: center; gap: 8px;
}

/* A 结论 */
.ins-summary { background: var(--brand-050); border-color: var(--brand-100); }
.ins-worktype { margin: 0; display: flex; flex-wrap: wrap; gap: 8px; align-items: baseline; }
.ins-worktype-label {
  flex: 0 0 auto; padding: 2px 8px; border-radius: var(--r-sm);
  background: var(--brand); color: #fff; font-size: var(--fs-xs); font-weight: 800;
}
.ins-worktype-value { font-size: var(--fs-base); font-weight: 800; color: var(--i900); }
.ins-worktype.is-empty { font-size: var(--fs-sm); color: var(--i600); line-height: 1.7; }
.ins-metric { margin-top: 12px; display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap; }
.ins-metric-num {
  font-family: var(--mono); font-size: 34px; font-weight: 800; color: var(--brand);
  line-height: 1;
}
.ins-metric-unit { font-size: var(--fs-sm); color: var(--i600); }
.ins-metric-note {
  padding: 2px 8px; border-radius: var(--r-sm);
  background: var(--accent-100); color: var(--accent-700);
  font-size: var(--fs-xs); font-weight: 800;
}

/* B 风险条目 */
.ins-risk-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 12px; }
.ins-risk {
  border-left: 4px solid var(--risk-mid); border-radius: var(--r-sm);
  background: var(--surface-soft); padding: 12px 16px;
}
.ins-risk-where {
  display: inline-flex; align-items: center; gap: 4px;
  font-size: var(--fs-xs); font-weight: 800; color: var(--brand-600);
  background: var(--brand-050); border-radius: var(--r-sm);
  padding: 2px 8px; margin-bottom: 8px;
}
.ins-risk-what { margin: 0; font-size: var(--fs-base); line-height: 1.7; color: var(--i800); }
.ins-risk-action {
  display: flex; align-items: flex-start; gap: 6px;
  margin-top: 12px; padding-top: 12px; border-top: 1px dashed var(--line);
  font-size: var(--fs-sm); line-height: 1.7; color: var(--risk-low-text);
}
.ins-note { margin: 12px 0 0; font-size: var(--fs-xs); line-height: 1.7; color: var(--i600); }
.ins-clean { border-left: 4px solid var(--risk-low); }
.ins-pending { border-left: 4px solid var(--risk-mid); background: var(--risk-mid-bg); }
.ins-pending-list {
  margin: 0; padding-left: 20px;
  font-size: var(--fs-sm); line-height: 1.7; color: var(--i700);
}
.ins-disclaimer {
  margin: 0; padding: 12px 16px; border-radius: var(--r-sm);
  background: var(--i100); font-size: var(--fs-xs); line-height: 1.7; color: var(--i600);
}

@media (max-width: 640px) {
  .ins-block { padding: 12px; }
  .ins-metric-num { font-size: 27px; }
}
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    script = SCRIPT_B.read_text(encoding="utf-8")
    tiers = TIERS.read_text(encoding="utf-8")
    applied = 0

    if "renderPhotoResult" in script:
        print("  [跳过] 渲染器已存在")
    else:
        anchor = "    async function inspectPhoto() {"
        if "\n\n".join(anchor.split("\n")) in script:
            anchor = "\n\n".join(anchor.split("\n"))
        if anchor not in script:
            print("  [FAIL] 找不到 inspectPhoto")
            return 1
        renderer = "\n\n".join(RENDERER.split("\n"))
        script = script.replace(anchor, renderer + anchor, 1)
        applied += 1
        print("  [ok] renderPhotoResult 已加入")

    if "优先结构化渲染" not in script:
        old = "\n\n".join(OLD_SUCCESS.split("\n"))
        new = "\n\n".join(NEW_SUCCESS.split("\n"))
        if old in script:
            script = script.replace(old, new, 1)
            applied += 1
            print("  [ok] 成功路径改为结构化优先 + 文本回退")
        elif OLD_SUCCESS in script:
            script = script.replace(OLD_SUCCESS, NEW_SUCCESS, 1)
            applied += 1
            print("  [ok] 成功路径已改（无空行格式）")
        else:
            print("  [FAIL] 成功路径锚点未匹配")
            return 1
    else:
        print("  [跳过] 成功路径已改")

    # 按钮文案在 finally 里被覆盖，修掉
    if 'button.textContent = "分析照片";' in script:
        script = script.replace('button.textContent = "分析照片";',
                                'button.textContent = "开始识别风险";', 1)
        applied += 1
        print("  [ok] 修掉 finally 覆盖按钮文案的问题")

    if "第 24 轮 A · 识别结果结构化渲染" not in tiers:
        tiers = tiers.rstrip() + CSS
        applied += 1
        print("  [ok] 样式已加入")

    if script.count(chr(92)):
        print("[FAIL] script 含反斜杠")
        return 1
    print("  [ok] 无反斜杠")

    if args.dry_run:
        print(f"（dry-run，未写入；{applied} 处）")
        return 0
    SCRIPT_B.write_text(script, encoding="utf-8")
    TIERS.write_text(tiers, encoding="utf-8")
    print(f"[ok] 已写入（{applied} 处）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
