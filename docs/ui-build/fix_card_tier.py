"""修正应急卡描边分级：按场景致命速度，而不是按号码（第 16 轮 §6）。

问题：原判断是 scene.calls.indexOf("120") >= 0，但五张卡都打 120，
      结果五张全红，只有火警（打 119）是琥珀 —— 等于没分级。
      实测截图确认：全红描边，失去重点。

修法：按**场景致命速度**分级
  红（立即致命）：火灾 / 触电 / 坍塌
  琥珀（需尽快）：受伤 / 坠落 / 其他

用法：python fix_card_tier.py [--dry-run]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
SCRIPT_B = BUILD / "index_script_b.js"

OLD = '''        /* 描边分级：前两张是最常见也最紧急的（受伤/火灾），用红色；

           其余用琥珀色，避免整屏全红反而失去重点。 */

        card.classList.add(scene.calls && scene.calls.indexOf("120") >= 0

          ? "is-critical" : "is-urgent");'''

NEW = '''        /* 描边分级按**场景致命速度**，不是按号码 ——
           实测五张卡都打 120，按号码分级结果全红，等于没分级。
           红（立即致命）：火灾 / 触电 / 坍塌
           琥珀（需尽快）：受伤 / 坠落 / 其他 */

        var CRITICAL = ["火灾", "触电", "坍塌"];

        card.classList.add(CRITICAL.indexOf(scene.key) >= 0 ? "is-critical" : "is-urgent");'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    text = SCRIPT_B.read_text(encoding="utf-8")
    if 'var CRITICAL = ["火灾", "触电", "坍塌"];' in text:
        print("[跳过] 已按致命速度分级")
        return 0
    if OLD not in text:
        print("[FAIL] 锚点未匹配")
        return 1

    text = text.replace(OLD, NEW, 1)
    if text.count(chr(92)):
        print("[FAIL] 引入反斜杠")
        return 1
    if args.dry_run:
        print("（dry-run，未写入）")
        return 0
    SCRIPT_B.write_text(text, encoding="utf-8")
    print("[ok] 描边分级改为按场景致命速度")
    return 0


if __name__ == "__main__":
    sys.exit(main())
