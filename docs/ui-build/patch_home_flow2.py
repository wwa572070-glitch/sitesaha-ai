"""按实际实现替换 renderPractical，改为四步动线（第 16 轮 §7 方向 2）。

上一版锚点是我凭记忆写的，和实际实现差很多。本版按当前真实代码替换整个函数。

用法：python patch_home_flow2.py [--dry-run]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
SCRIPT_A = BUILD / "index_script_a.js"

NEW_FUNC = '''    /* ==================================================================
       5. 首页：班前 5 分钟四步动线（§7 方向 2）
       ------------------------------------------------------------------
       勾选项一条都没减少（用户要求"不合并"），只是按步骤归位：
       进门过关 → 弄清风险 → 检查机具 → 不确定就停。
       ================================================================== */
    function renderPractical() {
      var done = readStore(PRACTICAL_KEY, {});
      var host = clear($("todoList"));
      if (!host) return;

      PRACTICAL_STEPS.forEach(function (group) {
        var items = PRACTICAL_ITEMS.filter(function (item) { return item.step === group.n; });
        if (!items.length) return;

        var bucket = make("section", "flow-step");
        var head = make("div", "flow-step-head");
        head.appendChild(make("span", "flow-step-num", String(group.n)));
        var titles = make("div", "flow-step-titles");
        titles.appendChild(make("b", "flow-step-title", group.title));
        if (group.note) titles.appendChild(make("span", "flow-step-note", group.note));
        head.appendChild(titles);
        bucket.appendChild(head);

        var list = make("div", "todo-list");
        items.forEach(function (item) {
          var label = make("label", "todo-item" + (done[item.id] ? " done" : ""));
          var input = document.createElement("input");
          input.type = "checkbox";
          input.checked = Boolean(done[item.id]);
          input.setAttribute("aria-label", item.label);
          input.addEventListener("change", function () {
            var state = readStore(PRACTICAL_KEY, {});
            state[item.id] = input.checked;
            writeStore(PRACTICAL_KEY, state);
            label.classList.toggle("done", input.checked);
            if (input.checked) logActivity();
            updatePracticalProgress();
          });
          label.appendChild(input);
          var text = make("span");
          text.appendChild(make("b", "", item.label));
          text.appendChild(make("span", "", item.hint));
          label.appendChild(text);
          list.appendChild(label);
        });
        bucket.appendChild(list);
        host.appendChild(bucket);
      });
      updatePracticalProgress();
    }'''

OLD_MARKER = "    function renderPractical() {"
END_MARKER = "\n    function updatePracticalProgress() {"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    text = SCRIPT_A.read_text(encoding="utf-8")
    if "flow-step" in text:
        print("[跳过] 已是四步动线")
        return 0

    start = text.find(OLD_MARKER)
    if start < 0:
        print("[FAIL] 找不到 renderPractical")
        return 1

    # 往前吃掉那段旧注释
    comment = "    /* ==================================================================\n       5. 首页：今天上工前的三件事"
    comment_at = text.rfind(comment, 0, start)
    if comment_at >= 0:
        start = comment_at

    end = text.find(END_MARKER, start)
    if end < 0:
        print("[FAIL] 找不到函数结束位置")
        return 1

    removed = text[start:end]
    print(f"[信息] 将替换 {len(removed)} 字符")
    text = text[:start] + NEW_FUNC + text[end:]

    left = len(re.findall(r"PRACTICAL_ITEMS\.forEach", text))
    print(f"[复核] 残留直接遍历 PRACTICAL_ITEMS 的地方：{left} 处")

    if text.count(chr(92)):
        print("[FAIL] 引入反斜杠")
        return 1
    print("[ok] 无反斜杠")

    if args.dry_run:
        print("（dry-run，未写入）")
        return 0
    SCRIPT_A.write_text(text, encoding="utf-8")
    print("[ok] 已写入")
    return 0


if __name__ == "__main__":
    sys.exit(main())
