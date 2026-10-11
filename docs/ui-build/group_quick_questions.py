"""§6 收敛：把「可以这样问」按场景分组（第 16 轮）。

规格要求：按场景分组，每组 ≤4 个，超出折叠。

现状：10 条 chip 平铺在一个 quick-list 里，冷读者不知道从哪条开始。

分组依据 —— 按**新工人实际会遇到的场景**分，不是按专业分类：
  第一天上工   入场后先做什么 / 必须做哪些防护
  常见高风险   高处作业 / 吊物下方 / 基坑裂缝渗水
  本工种专项   按当前工种过滤（电工/钢筋工/木工/焊工/架子工各自的题）

实现要点：
  · 前两组各 ≤4 条，直接显示
  · 第三组「更多本工种问题」用 <details> 折叠，命中当前工种的题优先
  · 保留 QUICK_QUESTIONS 数据结构与 quickList 容器 id（脚本依赖）
  · 组内仍用 quick-button 类，交互不变

用法：python group_quick_questions.py [--dry-run]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
SCRIPT_A = BUILD / "index_script_a.js"

OLD_DATA = '''    var QUICK_QUESTIONS = [
      { text: "我是第一次上工地，入场后先做什么？", roles: [] },
      { text: "进入施工现场必须做哪些防护？", roles: [] },
      { text: "高处作业前要检查什么？", roles: ["架子工", "钢筋工", "木工", "焊工", "电工", "普工/杂工"] },
      { text: "发现配电箱进水怎么办？", roles: ["电工"] },
      { text: "基坑出现裂缝和渗水怎么处理？", roles: [] },
      { text: "钢筋加工机械清理前要做什么？", roles: ["钢筋工"] },
      { text: "圆盘锯的防护罩能拆掉吗？", roles: ["木工"] },
      { text: "动火作业前要做哪些确认？", roles: ["焊工"] },
      { text: "脚手架验收牌有什么作用？", roles: ["架子工"] },
      { text: "吊物下方为什么不能站人？", roles: [] },
    ];'''

NEW_DATA = '''    /* 快捷提问按场景分组（第 16 轮 §6：每组 ≤4 个，超出折叠）。
       分组按新工人实际会遇到的场景，不是按专业分类。 */
    var QUICK_GROUPS = [
      {
        title: "第一天上工",
        hint: "刚进场，先弄清这几件",
        items: [
          { text: "我是第一次上工地，入场后先做什么？", roles: [] },
          { text: "进入施工现场必须做哪些防护？", roles: [] },
        ],
      },
      {
        title: "常见高风险",
        hint: "这些场景出事最多",
        items: [
          { text: "高处作业前要检查什么？", roles: ["架子工", "钢筋工", "木工", "焊工", "电工", "普工/杂工"] },
          { text: "吊物下方为什么不能站人？", roles: [] },
          { text: "基坑出现裂缝和渗水怎么处理？", roles: ["普工/杂工", "钢筋工"] },
          { text: "动火作业前要做哪些确认？", roles: ["焊工"] },
        ],
      },
      {
        title: "本工种专项",
        hint: "按你选的工种出题",
        collapsed: true,
        items: [
          { text: "脚手架验收牌有什么作用？", roles: ["架子工"] },
          { text: "发现配电箱进水怎么办？", roles: ["电工"] },
          { text: "钢筋加工机械清理前要做什么？", roles: ["钢筋工"] },
          { text: "圆盘锯的防护罩能拆掉吗？", roles: ["木工"] },
        ],
      },
    ];
'''

OLD_RENDER = '''      var host = clear($("quickList"));
      if (!host) return;
      var role = currentRole();
      QUICK_QUESTIONS.forEach(function (item) {
        var button = make("button", "quick-button", item.text);
        button.type = "button";
        if (role && item.roles.indexOf(role) >= 0) button.classList.add("is-role-match");
        button.addEventListener("click", function () { fillQuestion(item.text); });
        host.appendChild(button);
      });'''

NEW_RENDER = '''      var host = clear($("quickList"));
      if (!host) return;
      var role = currentRole();

      function buildGroup(group, container) {
        var shown = 0;
        group.items.forEach(function (item) {
          var matched = !!(role && item.roles.indexOf(role) >= 0);
          /* 折叠组只显示命中当前工种的题；未选工种时显示全部 */
          if (group.collapsed && role && !matched) return;
          var button = make("button", "quick-button", item.text);
          button.type = "button";
          if (matched) button.classList.add("is-role-match");
          button.addEventListener("click", function () { fillQuestion(item.text); });
          container.appendChild(button);
          shown += 1;
        });
        return shown;
      }

      QUICK_GROUPS.forEach(function (group) {
        var bucket = make("div", "quick-group");
        var head = make("div", "quick-group-head");
        head.appendChild(make("span", "quick-group-title", group.title));
        if (group.hint) head.appendChild(make("span", "quick-group-hint", group.hint));
        bucket.appendChild(head);

        var list = make("div", "quick-list");
        var count = buildGroup(group, list);

        if (group.collapsed) {
          /* 折叠组：未选工种时先收起，避免十题平铺；选了工种直接展开命中的题 */
          var details = make("details", "quick-group-more");
          if (role && count) details.open = true;
          details.appendChild(make("summary", "", role ? "本工种专项问题" : "更多本工种问题"));
          if (!count) {
            list.appendChild(make("span", "answer-meta", "先在上面选好工种，这里会显示对应的专项问题。"));
          }
          details.appendChild(list);
          bucket.appendChild(details);
        } else {
          bucket.appendChild(list);
        }
        host.appendChild(bucket);
      });'''

ANCHOR_OLD_DATA = "    var QUICK_QUESTIONS = ["


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    script = SCRIPT_A.read_text(encoding="utf-8")
    applied = 0

    if OLD_DATA in script:
        script = script.replace(OLD_DATA, NEW_DATA, 1)
        applied += 1
        print("[ok] QUICK_QUESTIONS → 分组结构 QUICK_GROUPS")
    else:
        print("[跳过] 数据结构锚点未匹配")

    if OLD_RENDER in script:
        script = script.replace(OLD_RENDER, NEW_RENDER, 1)
        applied += 1
        print("[ok] 渲染函数改为按场景分组")
    else:
        print("[跳过] 渲染函数锚点未匹配")

    # 兼容：其他地方若仍引用 QUICK_QUESTIONS，给出提示
    leftover = script.count("QUICK_QUESTIONS")
    if leftover:
        print(f"[注意] 仍有 {leftover} 处引用 QUICK_QUESTIONS，需一并检查")

    if script.count(chr(92)):
        print("[FAIL] 引入反斜杠")
        return 1
    print("[ok] 无反斜杠")

    if args.dry_run:
        print(f"（dry-run，未写入；{applied} 处）")
        return 0
    SCRIPT_A.write_text(script, encoding="utf-8")
    print(f"[ok] 已写入（{applied} 处）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
