"""把 renderQuickQuestions 改为按分组渲染（配合 QUICK_GROUPS）。

上一版锚点写错了：我按记忆里的旧实现写的，实际实现用的是
`button.style.borderColor` 而不是 `classList.add`。本版按实际内容替换。

用法：python group_quick_render.py [--dry-run]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
SCRIPT_A = BUILD / "index_script_a.js"

NEW_RENDER = '''    function renderQuickQuestions() {
      var host = clear($("quickList"));
      if (!host) return;
      var role = currentRole();

      function buildButtons(group, container) {
        var shown = 0;
        group.items.forEach(function (item) {
          var matched = !!(role && item.roles.indexOf(role) >= 0);
          /* 折叠组只显示命中当前工种的题；未选工种时先不展开 */
          if (group.collapsed && role && !matched) return;
          if (group.collapsed && !role) return;
          var button = make("button", "quick-button", item.text);
          button.type = "button";
          if (matched) button.classList.add("is-role-match");
          button.addEventListener("click", function () {
            var input = $("question");
            if (!input) return;
            input.value = item.text;
            input.focus();
            setVoiceHint("");
          });
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

        if (group.collapsed) {
          var details = make("details", "quick-group-more");
          details.appendChild(make("summary", "", role ? "本工种专项问题" : "更多本工种问题"));
          var count = buildButtons(group, list);
          if (!count) {
            list.appendChild(make(
              "span", "answer-meta",
              "先在上面选好工种，这里会显示对应的专项问题。"
            ));
          }
          details.appendChild(list);
          bucket.appendChild(details);
        } else {
          buildButtons(group, list);
          bucket.appendChild(list);
        }
        host.appendChild(bucket);
      });
    }'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    text = SCRIPT_A.read_text(encoding="utf-8")
    start = text.find("    function renderQuickQuestions() {")
    if start < 0:
        print("[FAIL] 找不到 renderQuickQuestions")
        return 1
    # 找到函数结束：下一个顶格 4 空格的 function 定义
    nxt = text.find("\n    function ", start + 10)
    if nxt < 0:
        print("[FAIL] 找不到函数结束位置")
        return 1
    old = text[start:nxt]
    print(f"[信息] 原函数 {len(old)} 字符，含 QUICK_QUESTIONS：{'QUICK_QUESTIONS' in old}")

    text = text[:start] + NEW_RENDER + text[nxt:]
    leftover = text.count("QUICK_QUESTIONS")
    print(f"[ok] 已替换渲染函数；剩余 QUICK_QUESTIONS 引用 {leftover} 处")

    if text.count(chr(92)):
        print("[FAIL] 引入反斜杠")
        return 1
    print("[ok] 无反斜杠")

    if args.dry_run:
        print("（dry-run，未写入）")
        return 0
    SCRIPT_A.write_text(text, encoding="utf-8")
    print("[ok] index_script_a.js 已更新")
    return 0


if __name__ == "__main__":
    sys.exit(main())
