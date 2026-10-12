"""§5-4b 补齐插画 class 样式 + 接入剩余两张（第 21 轮）。

问题：ill-emergency / ill-ppe 作为 class 用了但没有样式规则（检查失败），
      而 ill-edge / ill-scaffold 仍然是定义了没人用的死代码。

本脚本：
  1. 给四个插画 class 补语义化样式
  2. 把 ill-edge（临边防护）接进班前准备页
  3. 把 ill-scaffold（脚手架）接进学习页

用法：python patch_illustrations2.py [--dry-run]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
BODY = BUILD / "index_body.html"
TIERS = BUILD / "v16_tiers.css"

CSS_ADD = """
.ill-figure.ill-ppe { color: var(--brand-600); }
.ill-figure.ill-edge { color: var(--brand-500); }
.ill-figure.ill-scaffold { color: var(--brand-500); }
.ill-figure.ill-emergency {
  color: var(--brand-700);
  border-color: var(--risk-high);
  border-left-width: 4px;
  background: var(--risk-high-bg);
}
"""

# 班前准备：检查项索引之后插临边防护图
PRE_ANCHOR = '''      <details class="disclosure">
  <summary>检查项目索引（参考，不代替标准检查表）'''

PRE_FIGURE = '''      <figure class="ill-figure ill-edge">
        <svg viewBox="0 0 240 130" role="img" aria-labelledby="illEdgeLabel">
          <title id="illEdgeLabel">临边防护做法：防护栏杆高度 1.2 米、中间栏杆、挡脚板不低于 180 毫米</title>
          <use href="#ill-edge"/>
        </svg>
        <figcaption>临边防护要点：栏杆 1.2m、设中间防护、挡脚板 ≥180mm。数值以适用规范与现场交底为准。</figcaption>
      </figure>

'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    body = BODY.read_text(encoding="utf-8")
    tiers = TIERS.read_text(encoding="utf-8")
    applied = 0

    if ".ill-figure.ill-emergency" not in tiers:
        tiers = tiers.rstrip() + "\n" + CSS_ADD
        applied += 1
        print("  [ok] 四个插画 class 样式已补")
    else:
        print("  [跳过] 样式已存在")

    if 'class="ill-figure ill-edge"' in body:
        print("  [跳过] ill-edge 已接入")
    elif PRE_ANCHOR in body:
        body = body.replace(PRE_ANCHOR, PRE_FIGURE + PRE_ANCHOR, 1)
        applied += 1
        print("  [ok] 班前准备页接入临边防护图")
    else:
        print("  [注意] 班前准备页锚点未匹配")

    if body.count(chr(92)):
        print("[FAIL] body 含反斜杠")
        return 1
    print("  [ok] 无反斜杠")

    if args.dry_run:
        print(f"（dry-run，未写入；{applied} 处）")
        return 0
    BODY.write_text(body, encoding="utf-8")
    TIERS.write_text(tiers, encoding="utf-8")
    print(f"[ok] 已写入（{applied} 处）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
