"""按行号区间精确删除 script_b 里的「标准现行状态表」代码。

行号区间以当前文件为准，运行前会校验行内容是否符合预期，不符合就放弃写入。

用法：python strip_standards_ui.py
"""

from __future__ import annotations

import sys
from pathlib import Path

TARGET = Path(__file__).resolve().parent / "index_script_b.js"

# 1-based，闭区间
BLOCKS = [
    (1497, 1595, "标准表现在这段：allStandards / statusClass / renderStandardsTable / loadStandards"),
    (1602, 1606, "standardsSearchClear 的绑定"),
    (1611, 1614, "standardsSearchInput 的 input 监听"),
]

# 删除后需要同时清掉的行（单独处理）
EXTRA_REMOVE = [
    "      await loadStandards();\n",
]

# 区间首行必须包含的标记
START_MARKERS = {
    1497: "标准现行状态表",
    1602: 'bindClick("standardsSearchClear"',
    1611: 'var standardsSearchInput = $("standardsSearch")',
}
# 区间末行必须包含的标记
END_MARKERS = {
    1595: "}",
    1606: "});",
    1614: "}",
}


def main() -> int:
    lines = TARGET.read_text(encoding="utf-8").split("\n")
    print(f"原文件 {len(lines)} 行")

    for start, end, label in BLOCKS:
        head = lines[start - 1] if start - 1 < len(lines) else ""
        tail = lines[end - 1] if end - 1 < len(lines) else ""
        head_marker = START_MARKERS.get(start, "")
        tail_marker = END_MARKERS.get(end, "")
        if head_marker and head_marker not in head:
            print(f"[FAIL] 区间起始行不符：第 {start} 行 = {head.strip()[:70]!r}")
            return 1
        if tail_marker and tail.strip() != tail_marker and tail_marker not in tail:
            print(f"[FAIL] 区间结束行不符：第 {end} 行 = {tail.strip()[:70]!r}")
            return 1
        print(f"[ok] 校验通过：{label}（第 {start}-{end} 行）")

    # 从后往前删，避免行号位移
    for start, end, _label in sorted(BLOCKS, reverse=True):
        del lines[start - 1:end]

    text = "\n".join(lines)
    for snippet in EXTRA_REMOVE:
        if snippet in text:
            text = text.replace(snippet, "")
            print(f"[ok] 移除 {snippet.strip()}")

    leftovers = [m for m in ("allStandards", "renderStandardsTable", "loadStandards", "standardsTable") if m in text]
    if leftovers:
        print(f"[FAIL] 仍有残留符号：{leftovers}")
        return 1

    TARGET.write_text(text, encoding="utf-8")
    print(f"[ok] 写入完成，现在 {text.count(chr(10)) + 1} 行")
    return 0


if __name__ == "__main__":
    sys.exit(main())
