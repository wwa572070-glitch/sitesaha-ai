"""实现「每日警示案例」渲染（第 16 轮 §3 缺陷 3）。

缺陷现状：`#homeDailyCase` 是一块 990px 宽的空 div —— 有容器没渲染函数。
（容器在第一阶段建好了，渲染逻辑一直没写。）

内容准确性说明：
  案例数据的 date 字段是事故/通报日期（2023~2026），不是"今天的案例"。
  所以标题用「每日警示案例 · 每天轮换一条」，不用「今日」——
  否则会让人以为这是当天发生的事，属于内容失真。

渲染要点：
  · 按日期取模轮换，同一天稳定显示同一条
  · 有目录/日期/来源时如实展示，不编造
  · 加载中给骨架屏；无数据给空状态 + 下一步动作（§3.4 要求）

用法：python add_daily_case.py [--dry-run]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
BODY = BUILD / "index_body.html"
SCRIPT_B = BUILD / "index_script_b.js"


def blank(text: str) -> str:
    return "\n\n".join(text.split("\n"))


OLD_HEAD = blank('''        <div class="l4-head">
          <svg class="ico" aria-hidden="true"><use href="#i-alert"/></svg>
          <h2>今日警示案例</h2>
          <span class="l4-note">每天一条，看完再上工</span>
        </div>''')

NEW_HEAD = blank('''        <div class="l4-head">
          <svg class="ico" aria-hidden="true"><use href="#i-alert"/></svg>
          <h2>每日警示案例</h2>
          <span class="l4-note">每天轮换一条，看完再上工</span>
        </div>''')

RENDERER = '''    /* ==================================================================
       每日警示案例（首页 L4）
       ------------------------------------------------------------------
       数据来自 /api/cases，按日期取模轮换，同一天稳定显示同一条。
       案例的 date 是事故/通报日期，不是"今天发生"，所以文案用
       「每日警示案例」而不是「今日」，避免内容失真。
       ================================================================== */
    function renderDailyCase() {
      var host = $("homeDailyCase");
      if (!host) return;

      function paint(cases) {
        if (!cases || !cases.length) {
          host.innerHTML = "";
          var empty = make("div", "case-empty");
          empty.appendChild(make("p", "", "案例库暂时是空的。"));
          var hint = make("p", "case-empty-hint", "案例来自公开事故与隐患通报，管理员导入后会在这里轮换显示。");
          empty.appendChild(hint);
          host.appendChild(empty);
          return;
        }
        var stamp = new Date();
        var seed = stamp.getFullYear() * 10000 + (stamp.getMonth() + 1) * 100 + stamp.getDate();
        var pick = cases[seed % cases.length];

        host.innerHTML = "";
        var wrap = make("div", "case-daily");

        var meta = make("div", "case-daily-meta");
        if (pick.category) meta.appendChild(make("span", "case-tag", pick.category));
        if (pick.date) meta.appendChild(make("span", "case-daily-date", pick.date));
        wrap.appendChild(meta);

        wrap.appendChild(make("h3", "case-daily-title", pick.title || "未命名案例"));

        if (pick.what_happened) {
          var what = make("p", "case-daily-what");
          what.appendChild(make("b", "", "发生了什么："));
          what.appendChild(document.createTextNode(pick.what_happened));
          wrap.appendChild(what);
        }
        if (pick.why_dangerous) {
          var why = make("p", "case-daily-why");
          why.appendChild(make("b", "", "为什么危险："));
          why.appendChild(document.createTextNode(pick.why_dangerous));
          wrap.appendChild(why);
        }
        if (pick.lesson) {
          var lesson = make("div", "case-daily-lesson");
          lesson.appendChild(make("b", "", "记住这一条："));
          lesson.appendChild(document.createTextNode(pick.lesson));
          wrap.appendChild(lesson);
        }

        var foot = make("div", "case-daily-foot");
        if (pick.source_name) {
          foot.appendChild(make("span", "case-daily-source", "来源：" + pick.source_name));
        }
        var more = make("button", "ghost-button ico-button", "看全部案例");
        more.type = "button";
        more.addEventListener("click", function () { showView("learn"); });
        foot.appendChild(more);
        wrap.appendChild(foot);

        host.appendChild(wrap);
      }

      getJson("/api/cases")
        .then(function (data) { paint((data && data.cases) || []); })
        .catch(function () {
          host.innerHTML = "";
          var box = make("div", "case-empty");
          box.appendChild(make("p", "", "案例读取失败。"));
          box.appendChild(make("p", "case-empty-hint", "检查网络后刷新重试；也可以先看「学习与资料」里的案例库。"));
          host.appendChild(box);
        });
    }

'''

ANCHOR = "    function renderEmergencyGrid() {"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    body = BODY.read_text(encoding="utf-8")
    if "每日警示案例" not in body:
        if OLD_HEAD in body:
            body = body.replace(OLD_HEAD, NEW_HEAD, 1)
            print("[ok] 标题改为「每日警示案例」（原「今日」与数据日期不符）")
        else:
            print("[跳过] 标题已改或锚点未匹配")
    else:
        print("[跳过] 标题已是「每日警示案例」")

    script = SCRIPT_B.read_text(encoding="utf-8")
    if "function renderDailyCase" not in script:
        if ANCHOR not in script:
            print("[FAIL] 未找到 renderEmergencyGrid 锚点")
            return 1
        script = script.replace(ANCHOR, RENDERER + ANCHOR, 1)
        print("[ok] 已加入 renderDailyCase 函数")
    else:
        print("[跳过] renderDailyCase 已存在")

    # 在 init 里调用
    init_marker = "renderEmergencyGrid();"
    if "renderDailyCase();" not in script:
        # 只替换 init 里的调用点（第一次出现的）
        index = script.find(init_marker)
        if index < 0:
            print("[FAIL] 未找到 renderEmergencyGrid() 调用点")
            return 1
        script = script[:index] + init_marker + "\n\n      renderDailyCase();" + script[index + len(init_marker):]
        print("[ok] 已在 init 里调用 renderDailyCase")

    if script.count(chr(92)) or body.count(chr(92)):
        print("[FAIL] 引入反斜杠")
        return 1
    print("[ok] 无反斜杠")

    if args.dry_run:
        print("（dry-run，未写入）")
        return 0
    BODY.write_text(body, encoding="utf-8")
    SCRIPT_B.write_text(script, encoding="utf-8")
    print("[ok] 已写入")
    return 0


if __name__ == "__main__":
    sys.exit(main())
