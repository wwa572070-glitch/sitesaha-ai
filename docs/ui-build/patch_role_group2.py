"""把「未选工种时跳过折叠组」提到循环层（第 16 轮 §5 第 4 条）。

现状：判断只在 buildButtons 内部，外层 details 与占位文案仍会渲染出空壳。
实测：未选工种时 quickList 里仍有一个 <details>，展开是一句占位文案。

用法：python patch_role_group2.py [--dry-run]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
SCRIPT_A = BUILD / "index_script_a.js"

OLD = '''QUICK_GROUPS.forEach(function (group) {
        var bucket = make("div", "quick-group");
        var head = make("div", "quick-group-head");'''

NEW = '''QUICK_GROUPS.forEach(function (group) {
        /* collapsed 组的内容完全依赖工种：没选工种时整块不渲染。
           注意要在**循环这一层**跳过 —— 只在 buildButtons 里 return 的话，
           外层 details 与占位文案仍会渲染出一个空壳。 */
        if (group.collapsed && !role) return;

        var bucket = make("div", "quick-group");
        var head = make("div", "quick-group-head");'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    text = SCRIPT_A.read_text(encoding="utf-8")
    marker = "if (group.collapsed && !role) return;\n\n        var bucket"

    if marker in text:
        print("[跳过] 循环层已跳过空组")
        return 0

    if OLD not in text:
        print("[FAIL] 循环锚点未匹配")
        return 1

    text = text.replace(OLD, NEW, 1)
    print("[ok] 已在循环层跳过空组")

    # 移除内层重复判断（它现在永远不会命中，留着会误导读者）
    inner = "          if (group.collapsed && !role) return;\n"
    if inner in text:
        text = text.replace(inner, "", 1)
        print("[ok] 已移除内层重复判断")

    # 折叠组现在只在选了工种时渲染，summary 文案固定
    old_summary = 'details.appendChild(make("summary", "", role ? "本工种专项问题" : "更多本工种问题"));'
    new_summary = 'details.appendChild(make("summary", "", "本工种专项问题"));'
    if old_summary in text:
        text = text.replace(old_summary, new_summary, 1)
        print("[ok] summary 文案固定为「本工种专项问题」")

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
