"""统一表格与状态标签规范（第 28 轮）。

实测发现项目里有两套互相不一致的表格样式：

  .tier-table（标准库）
      表头 品牌蓝底白字 · 有斑马纹 · padding 9px 12px · 有悬停
  .import-table（导入预览）
      表头 浅灰底深字 · 无斑马纹 · padding 8px 12px · 无悬停

同一站内两张表长得不一样，用户会觉得「不是一个产品」。
本次把两者收敛到同一套规格，并抽出共享的设计变量，
以后改表格只动一处。

同时统一状态标签（风险等级 / 现行状态）的尺寸与配色。

用法：python patch_table_spec.py [--dry-run]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
TIERS = BUILD / "v16_tiers.css"

CSS = """

/* ==========================================================================
   第 28 轮 · 表格与状态标签统一
   --------------------------------------------------------------------------
   原来 .tier-table（标准库）与 .import-table（导入预览）表头、斑马纹、
   行高、悬停各不相同，同一站内像两个产品。
   这里抽出共享变量，两套表统一到同一规格。
   ========================================================================== */
:root {
  --table-head-bg: var(--brand);
  --table-head-fg: #fff;
  --table-pad-y: 9px;
  --table-pad-x: 12px;
  --table-row-line: var(--line);
  --table-row-alt: var(--i50);
  --table-row-hover: var(--brand-050);
}

/* 两张表统一：表头、斑马纹、行高、悬停 */
.tier-table th,
.import-table th {
  background: var(--table-head-bg);
  color: var(--table-head-fg);
  font-weight: 700;
  text-align: left;
  white-space: nowrap;
  padding: var(--table-pad-y) var(--table-pad-x);
}

.tier-table td,
.import-table td {
  padding: var(--table-pad-y) var(--table-pad-x);
  border-top: 1px solid var(--table-row-line);
  color: var(--i600);
  line-height: 1.6;
  vertical-align: top;
}

.tier-table tbody tr:nth-child(even),
.import-table tbody tr:nth-child(even) {
  background: var(--table-row-alt);
}

.tier-table tbody tr:hover,
.import-table tbody tr:hover {
  background: var(--table-row-hover);
}

/* 导入预览的错误行保持危险色，不被斑马纹覆盖 */
.import-table tr.is-error td {
  background: var(--risk-high-bg);
  color: var(--risk-high-text);
}

/* 小屏：表格横向可滚，不挤压内容 */
.table-scroll { width: 100%; overflow-x: auto; -webkit-overflow-scrolling: touch; }

@media (max-width: 640px) {
  :root { --table-pad-y: 8px; --table-pad-x: 10px; }
  .tier-table, .import-table { font-size: var(--fs-xs); }
}

/* --------------------------------------------------------------------------
   状态标签：风险等级、标准现行状态、来源标签统一尺寸
   -------------------------------------------------------------------------- */
.tag,
.status-badge,
.risk-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  border-radius: var(--r-sm);
  font-size: var(--fs-xs);
  font-weight: 800;
  line-height: 1.5;
  white-space: nowrap;
}

/* 语义色只在真正表示状态时使用，不做装饰 */
.tag.is-current,
.status-badge.is-ok { background: var(--risk-low-bg); color: var(--risk-low-text); }
.tag.is-pending,
.status-badge.is-warn { background: var(--risk-mid-bg); color: var(--risk-mid-text); }
.tag.is-void,
.status-badge.is-dead { background: var(--risk-high-bg); color: var(--risk-high-text); }
.tag.is-neutral { background: var(--i100); color: var(--i600); }
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    tiers = TIERS.read_text(encoding="utf-8")
    if "第 28 轮 · 表格与状态标签统一" in tiers:
        print("[跳过] 已统一")
        return 0

    tiers = tiers.rstrip() + CSS
    if tiers.count(chr(92)):
        print("[FAIL] 含反斜杠")
        return 1

    if args.dry_run:
        print("（dry-run，未写入）")
        return 0
    TIERS.write_text(tiers, encoding="utf-8")
    print("[ok] 表格与状态标签规范已统一")
    return 0


if __name__ == "__main__":
    sys.exit(main())
