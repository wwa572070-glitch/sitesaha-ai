"""收敛标题字号层级：目标 h2=21 / h2(hero)=26 / h3=17 / h4=14.5。

用法：python collapse_headings.py
只做精确字符串替换，每处都要求命中一次，否则放弃写入。
"""

from __future__ import annotations

import sys
from pathlib import Path

HEAD = Path(__file__).resolve().parent / "index_head.html"

# (原文, 新文, 说明) —— 把 18/19/16/15.5 等杂号归并到三级
REPLACEMENTS: list[tuple[str, str, str]] = [
    (
        ".panel-body > h2 { font-size:21px; }",
        ".panel-body > h2 { font-size:21px; }",
        "视图主标题：保持 21px（h2 级）",
    ),
    (
        ".hero h2 { color:#fff; font-size:29px; line-height:1.26; max-width:19em; }",
        ".hero h2 { color:#fff; font-size:26px; line-height:1.32; max-width:19em; }",
        "首页 Hero 标题：29 -> 26px",
    ),
    (
        ".emergency-hero h2 { color:#a8291c; font-size:22px; }",
        ".emergency-hero h2 { color:#a8291c; font-size:20px; }",
        "应急页标题：22 -> 20px（h2 级）",
    ),
    (
        ".quiz-result h3 { font-size:19px; }",
        ".quiz-result h3 { font-size:17px; }",
        "测验结果标题：19 -> 17px（h3 级）",
    ),
    (
        ".emergency-guide h3 { font-size:19px; color:#a8291c; display:flex; align-items:center; gap:10px; flex-wrap:wrap; }",
        ".emergency-guide h3 { font-size:17px; color:#a8291c; display:flex; align-items:center; gap:10px; flex-wrap:wrap; }",
        "应急指引标题：19 -> 17px（h3 级）",
    ),
    (
        ".role-detail h3 { font-size:17px; display:flex; align-items:center; gap:9px; flex-wrap:wrap; }",
        ".role-detail h3 { font-size:17px; display:flex; align-items:center; gap:9px; flex-wrap:wrap; }",
        "工种标题：保持 17px（h3 级）",
    ),
    (
        ".q-head { font-size:17px; line-height:1.5; margin:9px 0 13px; }",
        ".q-head { font-size:17px; line-height:1.5; margin:9px 0 13px; max-width:var(--measure); }",
        "题干：保持 17px，补阅读度量",
    ),
    (
        ".case-card h3 { font-size:16px; line-height:1.42; }",
        ".case-card h3 { font-size:17px; line-height:1.42; }",
        "案例标题：16 -> 17px（h3 级）",
    ),
    (
        ".check-group h3 { font-size:16px; display:flex; align-items:center; gap:9px; flex-wrap:wrap; }",
        ".check-group h3 { font-size:17px; display:flex; align-items:center; gap:9px; flex-wrap:wrap; }",
        "检查分组标题：16 -> 17px（h3 级）",
    ),
    (
        ".step-item h3 { font-size:15.5px; display:flex; align-items:center; gap:8px; flex-wrap:wrap; }",
        ".step-item h3 { font-size:17px; display:flex; align-items:center; gap:8px; flex-wrap:wrap; }",
        "培训步骤标题：15.5 -> 17px（h3 级）",
    ),
    (
        ".doc-group h3 { font-size:15.5px; display:flex; align-items:center; gap:9px; flex-wrap:wrap; }",
        ".doc-group h3 { font-size:17px; display:flex; align-items:center; gap:9px; flex-wrap:wrap; }",
        "知识库分组标题：15.5 -> 17px（h3 级）",
    ),
    (
        ".role-block h4 { font-size:13px; display:flex; align-items:center; gap:6px; margin-bottom:8px; }",
        ".role-block h4 { font-size:14.5px; display:flex; align-items:center; gap:6px; margin-bottom:8px; }",
        "工种块小标题：13 -> 14.5px（h4 级）",
    ),
    (
        ".training-card strong { font-size:15.5px; color:var(--ink); }",
        ".training-card strong { font-size:15px; color:var(--ink); }",
        "训练卡标题：15.5 -> 15px（卡片标题，非 h 级）",
    ),
    (
        ".action-card strong { font-size:16.5px; color:var(--ink); display:block; }",
        ".action-card strong { font-size:16px; color:var(--ink); display:block; }",
        "主行动卡标题：16.5 -> 16px",
    ),
    (
        ".side-title { font-size:15.5px; }",
        ".side-title { font-size:15px; }",
        "侧栏标题：15.5 -> 15px",
    ),
    (
        ".sec-title { font-size:17px; }",
        ".sec-title { font-size:17px; }",
        "区块标题：保持 17px（h3 级）",
    ),
]


def main() -> int:
    text = HEAD.read_text(encoding="utf-8")
    problems: list[str] = []
    changed = 0

    for old, new, note in REPLACEMENTS:
        count = text.count(old)
        if count != 1:
            problems.append(f"{note}：原文命中 {count} 次（应为 1）")
            continue
        if old != new:
            text = text.replace(old, new)
            changed += 1
        print(f"[ok] {note}")

    if problems:
        for item in problems:
            print("  [FAIL]", item)
        return 1

    HEAD.write_text(text, encoding="utf-8")
    print(f"\n实际改写 {changed} 处")
    return 0


if __name__ == "__main__":
    sys.exit(main())
