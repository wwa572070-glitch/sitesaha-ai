"""限制 learn 页两个过长区块的高度（第 16 轮 §6 收尾）。

实测（CDP，桌面 1440）：
  learn 区块总高 8455px，其中
    真实事故 / 隐患案例  2288px
    标准现行状态        2196px
  两页加起来占了一半以上，导致整页 8831px —— 远超正常浏览长度，
  截图 6000px 都装不下。

做法：给列表容器设 max-height + 纵向滚动，而不是删内容。
  · 案例网格：最多显示 6 张卡，其余滚动
  · 标准库表格：表头吸顶 + 表格区滚动
这样首屏信息密度不变，但页面长度可控，且不丢信息。

用法：python cap_learn_tall_blocks.py [--dry-run]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
PALETTE = BUILD / "v17_palette.css"

BLOCK = """

/* ==========================================================================
   learn 页过长区块的高度上限（§6 收尾）
   --------------------------------------------------------------------------
   实测：案例块 2288px + 标准库块 2196px，把整页撑到 8831px。
   设上限 + 滚动，信息不删，只是不再把页面拉长。
   ========================================================================== */
.case-grid {
  max-height: 640px; overflow-y: auto;
  padding-right: 6px;
  scrollbar-width: thin;
}
.case-grid::-webkit-scrollbar { width: 8px; }
.case-grid::-webkit-scrollbar-thumb {
  background: var(--i300); border-radius: 4px;
}
.case-grid::-webkit-scrollbar-track { background: transparent; }

/* 标准库表格：表头吸顶，表格区滚动 */
.table-wrap.is-scroll {
  max-height: 560px; overflow-y: auto;
  scrollbar-width: thin;
}
.table-wrap.is-scroll::-webkit-scrollbar { width: 8px; }
.table-wrap.is-scroll::-webkit-scrollbar-thumb {
  background: var(--i300); border-radius: 4px;
}
.table-wrap.is-scroll thead th {
  position: sticky; top: 0; z-index: 2;
}

/* 滚动区底部加一点渐隐提示，让人知道还有内容 */
.case-grid::after {
  content: ""; display: block; height: 1px;
}

@media (max-width: 640px) {
  .case-grid { max-height: 520px; }
  .table-wrap.is-scroll { max-height: 440px; }
}
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    text = PALETTE.read_text(encoding="utf-8")
    if "learn 页过长区块的高度上限" not in text:
        text = text.rstrip() + BLOCK
        if not args.dry_run:
            PALETTE.write_text(text, encoding="utf-8")
        print("[ok] 已加高度上限样式")
    else:
        print("[跳过] 已存在")
    return 0


if __name__ == "__main__":
    sys.exit(main())
