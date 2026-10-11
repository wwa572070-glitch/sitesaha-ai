"""§7 图形语言：近 7 天学习热力格 + 测验正确率趋势（第 16 轮）。

样式已在 v16_tiers.css 就位（.heat-grid / .heat-cell / .trend-figure），
本脚本补渲染逻辑。

数据来源（全部本机，不外传）：
  · 学习热力格：localStorage 里记录每天的学习动作次数
    数据键 sitesaha-activity-v1 = { "2026-05-20": 3, ... }
  · 测验趋势：QUIZ_KEY 里保存的历次得分
    若历史记录尚未累积，显示空状态而不是假数据

诚实原则：没有数据就画空状态，不编造趋势线。
  趋势图需要至少 2 个点才有意义，1 个点显示"再做一次就能看到趋势"。

用法：python add_charts.py [--dry-run]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
BODY = BUILD / "index_body.html"
SCRIPT_A = BUILD / "index_script_a.js"

# ---------- 热力格与趋势图的容器，插进知识测验块 ----------
HEAT_ANCHOR = '<div id="domainBars" class="domain-bars"></div>'
HEAT_NEW = '''<div id="domainBars" class="domain-bars"></div>

          <div class="chart-block">
            <h3 class="l4-sub">近 7 天学习记录</h3>
            <div id="studyHeat" class="heat-grid" role="img" aria-label="近 7 天学习热力格"></div>
            <div class="heat-legend">
              <span>少</span>
              <span class="heat-cell" data-level="0"></span>
              <span class="heat-cell" data-level="1"></span>
              <span class="heat-cell" data-level="2"></span>
              <span class="heat-cell" data-level="3"></span>
              <span class="heat-cell" data-level="4"></span>
              <span>多</span>
              <span id="studyHeatNote" class="answer-meta"></span>
            </div>
          </div>

          <div class="chart-block">
            <h3 class="l4-sub">测验正确率趋势</h3>
            <div id="quizTrend"></div>
          </div>'''

RENDERERS = '''    /* ==================================================================
       §7 图形语言：近 7 天学习热力格 + 测验正确率趋势
       ------------------------------------------------------------------
       数据全部来自本机 localStorage，不上传。
       没有数据就画空状态 —— 不编造趋势线。
       ================================================================== */
    var ACTIVITY_KEY = "sitesaha-activity-v1";

    function dayKey(date) {
      function pad(n) { return n < 10 ? "0" + n : String(n); }
      return date.getFullYear() + "-" + pad(date.getMonth() + 1) + "-" + pad(date.getDate());
    }

    /* 记一次学习动作。renderStudyHeat 会读它画热力格。 */
    function logActivity() {
      var store = readStore(ACTIVITY_KEY, {});
      var key = dayKey(new Date());
      store[key] = (store[key] || 0) + 1;
      /* 只留最近 30 天，避免无限增长 */
      var cutoff = new Date();
      cutoff.setDate(cutoff.getDate() - 30);
      var kept = {};
      Object.keys(store).forEach(function (item) {
        if (item >= dayKey(cutoff)) kept[item] = store[item];
      });
      writeStore(ACTIVITY_KEY, kept);
    }

    function renderStudyHeat() {
      var host = clear($("studyHeat"));
      if (!host) return;
      var store = readStore(ACTIVITY_KEY, {});
      var today = new Date();
      var values = [];
      for (var back = 6; back >= 0; back -= 1) {
        var day = new Date(today.getTime());
        day.setDate(day.getDate() - back);
        values.push({ key: dayKey(day), count: store[dayKey(day)] || 0, back: back });
      }
      var max = 1;
      values.forEach(function (item) { if (item.count > max) max = item.count; });

      values.forEach(function (item) {
        var level = item.count === 0 ? 0 : Math.min(4, Math.ceil((item.count / max) * 4));
        var cell = make("span", "heat-cell");
        cell.setAttribute("data-level", String(level));
        cell.setAttribute("title", item.key + "：" + item.count + " 次学习动作");
        cell.textContent = item.back === 0 ? "今" : String(item.back + 1);
        host.appendChild(cell);
      });

      var note = $("studyHeatNote");
      if (note) {
        var total = values.reduce(function (sum, item) { return sum + item.count; }, 0);
        note.textContent = total
          ? ("近 7 天共 " + total + " 次学习动作")
          : "还没有记录。完成培训步骤、做测验或班前确认后会出现在这里。";
      }
    }

    function renderQuizTrend() {
      var host = clear($("quizTrend"));
      if (!host) return;
      var quiz = readStore(QUIZ_KEY, EMPTY_QUIZ);
      var history = (quiz.history || []).filter(function (item) {
        return item && typeof item.percent === "number";
      });

      if (history.length < 2) {
        host.appendChild(make(
          "p", "trend-empty",
          history.length === 1
            ? "目前只有 1 次记录（" + history[0].percent + "%）。再做一次就能看到趋势线。"
            : "还没有测验记录。点上面的「开始测验」做一遍，这里会画出正确率变化。"
        ));
        return;
      }

      var recent = history.slice(-8);
      var width = 420;
      var height = 108;
      var padX = 26;
      var padY = 18;
      var stepX = recent.length > 1 ? (width - padX * 2) / (recent.length - 1) : 0;

      function pointX(index) { return padX + index * stepX; }
      function pointY(percent) {
        return height - padY - (Math.max(0, Math.min(100, percent)) / 100) * (height - padY * 2);
      }

      var points = recent.map(function (item, index) {
        return pointX(index) + "," + pointY(item.percent).toFixed(1);
      });
      var areaPath = "M" + pointX(0) + "," + (height - padY)
        + " L" + points.join(" L")
        + " L" + pointX(recent.length - 1) + "," + (height - padY) + " Z";

      var svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
      svg.setAttribute("class", "trend-figure");
      svg.setAttribute("viewBox", "0 0 " + width + " " + height);
      svg.setAttribute("role", "img");
      svg.setAttribute("aria-label",
        "最近 " + recent.length + " 次测验正确率趋势，最新 " + recent[recent.length - 1].percent + "%");

      function add(tag, attrs, text) {
        var node = document.createElementNS("http://www.w3.org/2000/svg", tag);
        Object.keys(attrs).forEach(function (key) { node.setAttribute(key, attrs[key]); });
        if (text) node.textContent = text;
        svg.appendChild(node);
        return node;
      }

      add("line", { class: "axis", x1: padX, y1: height - padY, x2: width - padX, y2: height - padY });
      add("path", { class: "area", d: areaPath });
      add("polyline", { class: "line", points: points.join(" ") });

      recent.forEach(function (item, index) {
        add("circle", { class: "pt", cx: pointX(index), cy: pointY(item.percent).toFixed(1), r: 3.5 });
      });
      add("text", { class: "pt-label", x: padX, y: height - 4 }, "60%");
      add("text", { class: "pt-label", x: width - padX - 26, y: height - 4 },
        recent[recent.length - 1].percent + "%");

      host.appendChild(svg);
      host.appendChild(make(
        "p", "answer-meta",
        "最近 " + recent.length + " 次记录，最新 " + recent[recent.length - 1].percent + "%（及格线 80%）。"
      ));
    }

'''

ANCHOR = "    function renderDomainBars() {"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    body = BODY.read_text(encoding="utf-8")
    if 'id="studyHeat"' not in body:
        if HEAT_ANCHOR in body:
            body = body.replace(HEAT_ANCHOR, HEAT_NEW, 1)
            print("[ok] 已插入热力格与趋势图容器")
        else:
            print("[FAIL] 未找到 domainBars 锚点")
            return 1
    else:
        print("[跳过] 容器已存在")

    script = SCRIPT_A.read_text(encoding="utf-8")
    if "function renderStudyHeat" not in script:
        if ANCHOR not in script:
            print("[FAIL] 未找到 renderDomainBars 锚点")
            return 1
        script = script.replace(ANCHOR, RENDERERS + ANCHOR, 1)
        print("[ok] 已加入 renderStudyHeat 与 renderQuizTrend")
    else:
        print("[跳过] 渲染函数已存在")

    if script.count(chr(92)) or body.count(chr(92)):
        print("[FAIL] 引入反斜杠")
        return 1
    print("[ok] 无反斜杠")

    if args.dry_run:
        print("（dry-run，未写入）")
        return 0
    BODY.write_text(body, encoding="utf-8")
    SCRIPT_A.write_text(script, encoding="utf-8")
    print("[ok] 已写入")
    return 0


if __name__ == "__main__":
    sys.exit(main())
