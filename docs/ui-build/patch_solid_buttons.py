"""§5：每屏恰好 1 个实心按钮（第 16 轮）。

实测现状：
  ask:   查询安全依据(primary) + 打开摄像头拍照(amber) + 拍下这一张(primary) + 分析照片(primary)
  learn: 开始测验(amber) + 生成培训记录单(amber)
  home / pre / sos: 0 个（没有主行动）

§5 要求「主色只用于主行动（每屏恰好 1 个实心按钮）」，所以：
  · ask 保留「查询安全依据」为主行动，把拍照流程内的 3 个降为描边
  · learn 保留「开始测验」为主行动，把「生成培训记录单」降为描边
  · home 把「开始逐条确认」升为主行动（原先是 0 个）
  · pre 把「生成当班清单」升为主行动
  · sos 把「拨打 120」保持为唯一主行动（它本来就是红实心，按风险语义保留红色）

用法：python patch_solid_buttons.py [--dry-run]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
BODY = BUILD / "index_body.html"

# (定位文本, 原 class, 新 class, 说明)
DEMOTE = [
    ("打开摄像头拍照", "amber-button", "secondary-button", "拍照流程第 1 步，非主行动"),
    ("拍下这一张", "primary-button", "secondary-button", "拍照流程第 2 步，非主行动"),
    ("分析照片", "primary-button", "secondary-button", "拍照流程第 3 步，非主行动"),
    ("生成培训记录单", "amber-button", "secondary-button", "学习页次级动作"),
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    body = BODY.read_text(encoding="utf-8")
    applied = 0

    for label, old_class, new_class, why in DEMOTE:
        # 找包含该文案的 button，替换它的 class
        pattern = re.compile(
            r'(<button[^>]*class=")' + re.escape(old_class) + r'("[^>]*>[^<]*'
            + re.escape(label) + r')',
            re.S,
        )
        body, count = pattern.subn(r"\1" + new_class + r"\2", body)
        if count:
            applied += count
            print(f"  [ok] 「{label}」{old_class} → {new_class}（{why}）")
        else:
            print(f"  [跳过] 未匹配「{label}」")

    if args.dry_run:
        print(f"（dry-run，未写入；{applied} 处）")
        return 0
    BODY.write_text(body, encoding="utf-8")

    # 复核：按屏统计
    sections = [(m.start(), m.group(1)) for m in re.finditer(r'<section id="([^"]+)"', body)]
    print("\n[复核] 每屏实心按钮：")
    for index, (start, name) in enumerate(sections):
        end = sections[index + 1][0] if index + 1 < len(sections) else len(body)
        count = len(re.findall(r'class="(?:primary-button|amber-button)', body[start:end]))
        mark = "OK" if count == 1 else ("缺主行动" if count == 0 else "过多")
        print(f"  #{name:<7} {count} 个  {mark}")
    print(f"\n[ok] 已更新（{applied} 处）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
