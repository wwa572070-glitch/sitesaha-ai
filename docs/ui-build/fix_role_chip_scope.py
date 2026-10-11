"""修正类名撞车：把新加的 .role-chip 规则收窄到 .role-chip-list 内。

事故：
  .role-chip 这个类**本来已经存在**，是 #roleChips 里工种选择按钮的样式。
  我新写的 .role-chip { flex: 0 0 auto; width: auto; padding: 4px 12px; ... }
  位置更靠后，于是覆盖了原有的 .role-chips.is-inline .role-chip，
  把工种选择器改成了小字号、无最小高度；我自己的标签反而没吃到规则。

教训：加样式前先查类名是否已被占用 —— 这次是靠读计算样式才发现的，
      只看截图会误判成"标签拉伸"。

修法：所有新规则的作用域收窄到 .role-chip-list 内（那是我的容器）。

用法：python fix_role_chip_scope.py [--dry-run]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
TIERS = BUILD / "v16_tiers.css"

OLD = '''.role-chip {
  /* 关键：默认 flex 项会拉伸填满整行，标签必须按内容宽度收缩 */
  flex: 0 0 auto; width: auto;
  padding: 4px 12px; border-radius: 999px;
  background: var(--surface-soft); border: 1px solid var(--line);
  font-size: var(--fs-sm); color: var(--i700);
  white-space: nowrap;
}
.role-block.is-danger .role-chip {
  background: var(--risk-high-bg); border-color: var(--risk-high);
  color: var(--risk-high-text);
}'''

NEW = '''/* 注意：.role-chip 已被 #roleChips 的工种选择按钮占用，
   这里必须限定在 .role-chip-list 内，否则会改坏工种选择器。 */
.role-chip-list .role-chip {
  flex: 0 0 auto; width: auto;
  padding: 4px 12px; border-radius: 999px;
  background: var(--surface-soft); border: 1px solid var(--line);
  font-size: var(--fs-sm); color: var(--i700);
  white-space: nowrap;
}
.role-block.is-danger .role-chip-list .role-chip {
  background: var(--risk-high-bg); border-color: var(--risk-high);
  color: var(--risk-high-text);
}'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    text = TIERS.read_text(encoding="utf-8")
    if ".role-chip-list .role-chip {" in text:
        print("[跳过] 作用域已收窄")
        return 0
    if OLD not in text:
        print("[FAIL] 找不到待修规则")
        return 1

    text = text.replace(OLD, NEW, 1)
    print("[ok] .role-chip 规则已收窄到 .role-chip-list 内")

    # 复核：不该再有裸的 .role-chip { 规则
    import re
    bare = re.findall(r"^\.role-chip\s*\{", text, re.M)
    print(f"[复核] 剩余的裸 .role-chip 规则：{len(bare)} 处（应为 0）")

    if args.dry_run:
        print("（dry-run，未写入）")
        return 0
    TIERS.write_text(text, encoding="utf-8")
    print("[ok] 已写入")
    return 0


if __name__ == "__main__":
    sys.exit(main())
