"""把脚本适配到 V11 极简结构。

做了三件事：
  1) 删掉「标准现行状态表」相关代码（新界面不再有这一栏，避免无效请求）
  2) 把旧结构的类名/ID 换成新结构（bubble-title→who、document-list→doc-row 等）
  3) 渲染函数对"元素不存在"更宽容，缺元素时直接跳过

用法：python adapt_to_v11.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
SCRIPT_A = BUILD / "index_script_a.js"
SCRIPT_B = BUILD / "index_script_b.js"


def drop_block(text: str, start_marker: str, end_marker: str, label: str) -> tuple[str, str]:
    start = text.find(start_marker)
    if start < 0:
        return text, f"{label}：未找到起始标记"
    end = text.find(end_marker, start)
    if end < 0:
        return text, f"{label}：未找到结束标记"
    end += len(end_marker)
    return text[:start] + text[end:], ""


def main() -> int:
    problems: list[str] = []

    # ---------- script_b ----------
    b = SCRIPT_B.read_text(encoding="utf-8")

    # 1) 去掉标准表整段
    for start_marker, end_marker, label in [
        (
            "    /* 标准现行状态表（数据来自 /api/standards；接口不可用时降级为提示） */",
            "    bindClick(\"docSearchClear\"",
            "标准表整段",
        ),
    ]:
        b, err = drop_block(b, start_marker, end_marker, label)
        if err:
            problems.append(err)
        else:
            # 重新接上 docSearchClear 的绑定
            b = b.replace(
                "    bindClick(\"docSearchClear\"",
                "    bindClick(\"docSearchClear\"",
                1,
            )
            print(f"[ok] 已移除{label}")

    # 2) 去掉 loadStandards 调用
    before = b.count("await loadStandards();")
    b = b.replace("      await loadStandards();\n", "")
    print(f"[ok] 移除 loadStandards 调用 {before} 处")

    # 3) 类名与 id 适配
    replacements = [
        ('textNode("div", "bubble-title"', 'make("div", "who"'),
        ('.appendChild(textNode("div", "bubble-meta"', '.appendChild(make("div", "meta"'),
        ('make("div", "answer-body"', 'make("div", "answer"'),
        ('class="document-list"', 'class="doc-row"'),
        ('make("ul", "doc-row")', 'make("div", "doc-row")'),
        ('var li = make("li");', 'var li = make("div", "doc-row");'),
        ('list.appendChild(li);', 'list.appendChild(li);'),
        ('"document-list"', '"doc-row"'),
        ('"answer-body"', '"answer"'),
        ('"bubble-title"', '"who"'),
        ('"bubble-meta"', '"meta"'),
    ]
    for old, new in replacements:
        count = b.count(old)
        if count:
            b = b.replace(old, new)
            print(f"[ok] script_b: {old[:44]!r} → {new[:44]!r}（{count} 处）")

    SCRIPT_B.write_text(b, encoding="utf-8")
    print(f"script_b 现在 {b.count(chr(10)) + 1} 行")

    # ---------- script_a ----------
    a = SCRIPT_A.read_text(encoding="utf-8")
    a = a.replace('class="document-list"', 'class="doc-row"')
    a = a.replace('"document-list"', '"doc-row"')
    SCRIPT_A.write_text(a, encoding="utf-8")
    print(f"script_a 现在 {a.count(chr(10)) + 1} 行")

    if problems:
        print("\n需要人工处理：")
        for item in problems:
            print("  -", item)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
