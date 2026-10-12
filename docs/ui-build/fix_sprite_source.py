"""把插画写进正确的源文件（第 29 轮，根因修复）。

根因（已用逐步二分法证实）：
  apply_v13_theme.py 每次运行都会
    1. 删掉 index_body.html 里 SPRITE_BEGIN..SPRITE_END 之间的内容
    2. 用 v16_icons.svg.html 的内容重新注入

  所以往 index_body.html 里加符号**一定会被覆盖**。
  之前 ill-emergency 加了三次、消失了三次，就是这个原因；
  而上轮重画的 ill-edge / ill-ppe **也从未生效过**。

  正确的写入位置是 v16_icons.svg.html。

本脚本把三张插画写进正确位置，并复验。

用法：python fix_sprite_source.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
SPRITE = BUILD / "v16_icons.svg.html"

# 从 redraw_illustrations2.py 复用同一份markup，避免两处不一致
sys.path.insert(0, str(BUILD))
from redraw_illustrations2 import EDGE, PPE, EMERGENCY  # noqa: E402


def upsert(text: str, name: str, markup: str) -> tuple[str, str]:
    pattern = re.compile(
        rf'<symbol\b[^>]*id="{re.escape(name)}"[^>]*>.*?</symbol>\s*', re.S
    )
    if pattern.search(text):
        return pattern.sub(markup, text, count=1), "替换"
    anchor = '  <symbol id="ill-ppe"'
    if anchor in text:
        return text.replace(anchor, markup + anchor, 1), "新增"
    marker = "<!-- ===== 示意图用（较大、线稿） ===== -->\n"
    if marker in text:
        return text.replace(marker, marker + "\n" + markup, 1), "新增"
    return text, "失败"


def main() -> int:
    text = SPRITE.read_text(encoding="utf-8")
    print(f"源文件 {SPRITE.name}：{len(text)} 字符")

    before = {n: text.count(f'<symbol id="{n}"') for n in
              ("ill-edge", "ill-ppe", "ill-emergency", "ill-scaffold")}
    print("  写入前：", before)

    for name, markup in (("ill-edge", EDGE), ("ill-ppe", PPE), ("ill-emergency", EMERGENCY)):
        text, action = upsert(text, name, markup)
        print(f"  [{action}] {name}")

    SPRITE.write_text(text, encoding="utf-8")

    # 读回复验
    check = SPRITE.read_text(encoding="utf-8")
    after = {n: check.count(f'<symbol id="{n}"') for n in
             ("ill-edge", "ill-ppe", "ill-emergency", "ill-scaffold")}
    print("  写入后：", after)

    ok = all(v == 1 for v in after.values())
    if not ok:
        print("[FAIL] 复验不通过")
        return 1
    print("[OK] 四张插画都在源文件里，各 1 份")
    return 0


if __name__ == "__main__":
    sys.exit(main())
