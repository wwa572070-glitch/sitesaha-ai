"""补回「检查项目索引」的渲染（第 16 轮 §11 前端收尾）。

删掉旧 loadChecklists 后，#inspectionChecks 空了 —— 那个索引面板原本由它填充。
这里补一个精简的渲染函数，只负责索引，不再碰主清单。

用法：python restore_inspection_index.py [--dry-run]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
SCRIPT_B = BUILD / "index_script_b.js"

FUNC = '''    /* 检查项目索引：按类别列出场景条目，配 §5 的对照表格。
       与主清单分开 —— 主清单随当班条件变化，索引是固定参考资料。 */
    function renderInspectionIndex() {
      var host = $("inspectionChecks");
      if (!host) return;
      getJson("/api/checklists")
        .then(function (data) {
          clear(host);
          var groups = data.categories || [];
          if (!groups.length) {
            host.appendChild(make("p", "empty-state", "索引暂时读不到，刷新后再试。"));
            return;
          }
          groups.forEach(function (group) {
            var bucket = make("section", "index-cat");
            var head = make("div", "index-cat-head");
            head.appendChild(make("b", "index-cat-name", group.name || "未命名"));
            if (group.scope) {
              head.appendChild(make("span", "index-cat-scope", group.scope));
            }
            bucket.appendChild(head);
            var list = make("ul", "index-cat-list");
            (group.worker_checks || []).forEach(function (text) {
              list.appendChild(make("li", "", text));
            });
            bucket.appendChild(list);
            host.appendChild(bucket);
          });
        })
        .catch(function () {
          clear(host);
          host.appendChild(make("p", "empty-state", "索引读取失败，刷新页面重试。"));
        });
    }

'''

CSS = """

/* 检查项目索引（§11 前端拆分后的独立区块） */
.index-cat { margin-bottom: 14px; }
.index-cat:last-child { margin-bottom: 0; }
.index-cat-head {
  display: flex; flex-wrap: wrap; align-items: baseline; gap: 10px;
  margin-bottom: 6px;
}
.index-cat-name { font-size: var(--fs-md); font-weight: 800; color: var(--i900); }
.index-cat-scope { font-size: var(--fs-xs); color: var(--i500); }
.index-cat-list { margin: 0; padding-left: 20px; }
.index-cat-list li {
  font-size: var(--fs-sm); line-height: 1.7; color: var(--i700); margin-bottom: 2px;
}
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    from pathlib import Path as _P
    tiers = _P(__file__).resolve().parent / "v16_tiers.css"

    text = SCRIPT_B.read_text(encoding="utf-8")
    changed = 0

    if "function renderInspectionIndex" not in text:
        anchor = "    function initPrePanels() {"
        if anchor not in text:
            print("[FAIL] 找不到 initPrePanels")
            return 1
        text = text.replace(anchor, FUNC + anchor, 1)
        changed += 1
        print("[ok] 新增 renderInspectionIndex")
    else:
        print("[跳过] 已存在")

    if "renderInspectionIndex();" not in text:
        marker = "bindPrePanels();"
        if marker in text:
            text = text.replace(marker, marker + "\n\n      renderInspectionIndex();", 1)
            changed += 1
            print("[ok] initPrePanels 里调用")
        else:
            print("[跳过] 找不到 bindPrePanels 调用点")

    css_text = tiers.read_text(encoding="utf-8")
    if "检查项目索引（§11" not in css_text:
        css_text = css_text.rstrip() + CSS
        tiers.write_text(css_text, encoding="utf-8")
        changed += 1
        print("[ok] 样式已加入")

    if text.count(chr(92)):
        print("[FAIL] 引入反斜杠")
        return 1
    print("[ok] 无反斜杠")

    if args.dry_run:
        print(f"（dry-run，未写入；{changed} 处）")
        return 0
    SCRIPT_B.write_text(text, encoding="utf-8")
    print(f"[ok] 已写入（{changed} 处）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
