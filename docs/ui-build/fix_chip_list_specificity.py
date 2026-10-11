"""把 .role-chip-list 的选择器提到与基础层同特异性（第 16 轮 §7 方向 5）。

真正根因（用 probe_chip_runtime.py 实测出来的）：
  基础层有  .role-block ul { display: grid; gap: 4px; }   特异性 (0,1,1)
  我写的是  .role-chip-list { display: flex; gap: 8px; }  特异性 (0,1,0)
  → 特异性低，display 被压成 grid。

  于是 <li> 变成 grid 项（display=list-item），宽度撑满整行 946px。
  之前看到的"标签被拉长"其实是这个，跟 .role-chip 类名撞车无关
  （撞车是另一个真问题，已单独修掉）。

修法：写成 .role-block .role-chip-list（同为 0,1,1，且位置更靠后 → 胜出）。

用法：python fix_chip_list_specificity.py [--dry-run]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
TIERS = BUILD / "v16_tiers.css"

OLD_BLOCK = '''.role-chip-list {
  display: flex; flex-wrap: wrap; gap: 8px;
  list-style: none; margin: 0; padding: 0;
}'''

NEW_BLOCK = '''/* 基础层有 `.role-block ul { display:grid }`（特异性 0,1,1），
   所以这里必须写成 `.role-block .role-chip-list`（同为 0,1,1 且位置更后）
   才能把 display 改回 flex —— 只写 .role-chip-list 会被它压过，
   结果 li 变成 grid 项、宽度撑满整行。 */
.role-block .role-chip-list {
  display: flex; flex-wrap: wrap; gap: 8px;
  list-style: none; margin: 0; padding: 0;
}'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    text = TIERS.read_text(encoding="utf-8")
    if ".role-block .role-chip-list {" in text:
        print("[跳过] 特异性已提高")
        return 0
    if OLD_BLOCK not in text:
        print("[FAIL] 找不到 .role-chip-list 规则")
        return 1

    text = text.replace(OLD_BLOCK, NEW_BLOCK, 1)
    print("[ok] .role-chip-list 选择器提高特异性")

    # 复核
    leftover = re.findall(r"^\.role-chip-list\s*\{", text, re.M)
    print(f"[复核] 剩余的裸 .role-chip-list 规则：{len(leftover)} 处（应为 0）")

    if args.dry_run:
        print("（dry-run，未写入）")
        return 0
    TIERS.write_text(text, encoding="utf-8")
    print("[ok] 已写入")
    return 0


if __name__ == "__main__":
    sys.exit(main())
