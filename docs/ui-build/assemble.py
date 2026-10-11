"""把模板分片拼成完整 HTML，供 webapp.py 注入，并做结构自检。

用法：python assemble.py
产物：_build/index_full.html

拼接顺序：
  1) index_head.html —— <!doctype> ... <style> 设计系统 </style> </head> <body> 之前
  2) index_body.html —— <body> ... 页脚 </body 之前（不含 script）
  3) index_script_a.js —— <script> 开头 + 逻辑前半
  4) index_script_b.js —— 逻辑后半 + </script></body></html>
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
HEAD = BUILD / "index_head.html"
BODY = BUILD / "index_body.html"
SCRIPT_A = BUILD / "index_script_a.js"
SCRIPT_B = BUILD / "index_script_b.js"
OUTPUT = BUILD / "index_full.html"


def _check(full: str) -> int:
    problems: list[str] = []
    counts = {
        "<script": full.count("<script"),
        "</script>": full.count("</script>"),
        "<style": full.count("<style"),
        "</style>": full.count("</style>"),
        "<body": full.count("<body"),
        "</body>": full.count("</body>"),
        "<html": full.count("<html"),
        "</html>": full.count("</html>"),
    }
    if counts["<script"] != counts["</script>"]:
        problems.append(f"script 标签不匹配：{counts['<script']} 开 / {counts['</script>']} 闭")
    for name in ("<style", "<body", "<html"):
        closing = "</" + name[1:] + ">"
        if counts[name] != counts[closing]:
            problems.append(f"{name} 标签不匹配：{counts[name]} 开 / {counts[closing]} 闭")
    ids = re.findall(r'\bid="([^"]+)"', full)
    duplicates = sorted({value for value in ids if ids.count(value) > 1})
    if duplicates:
        problems.append("重复 id：" + "、".join(duplicates))

    # JS 里 $("xxx") 引用的 id 必须真实存在，避免空指针式静默失败。
    # 例外：运行时才插入 DOM 的节点。
    runtime_ids = {"chatThinking", "quizNext"}
    referenced = sorted(set(re.findall(r'\$\("([A-Za-z][\w-]*)"\)', full)))
    missing = [
        name for name in referenced
        if f'id="{name}"' not in full and name not in runtime_ids
    ]
    if missing:
        problems.append("JS 引用了不存在的 id：" + "、".join(missing))

    # data-view 与 section id 必须一一对应（导航按钮类名 V11 起为 .tab）
    views = set(re.findall(r'class="tab[^"]*"[^>]*\sdata-view="([^"]+)"', full))
    if not views:
        views = set(re.findall(r'data-view="([^"]+)"', full))
    sections = set(re.findall(r'<section id="([^"]+)" class="view', full))
    if views != sections:
        problems.append(
            "导航模块与视图不一致：仅导航有 " + str(sorted(views - sections))
            + "；仅视图有 " + str(sorted(sections - views))
        )

    print(f"lines={full.count(chr(10))} chars={len(full)}")
    print("counts:", counts)
    print(f"nav views={len(views)} sections={len(sections)} ids={len(ids)} js_id_refs={len(referenced)}")
    if problems:
        for item in problems:
            print("  [FAIL]", item)
        return 1
    print("structure check: OK")
    return 0


def main() -> int:
    for path in (HEAD, BODY, SCRIPT_A, SCRIPT_B):
        if not path.is_file():
            raise SystemExit(f"缺少分片文件：{path}")
        if not path.read_text(encoding="utf-8").strip():
            raise SystemExit(f"分片文件为空：{path}")

    full = (
        HEAD.read_text(encoding="utf-8").rstrip("\n")
        + "\n"
        + BODY.read_text(encoding="utf-8").rstrip("\n")
        + "\n"
        + SCRIPT_A.read_text(encoding="utf-8").rstrip("\n")
        + "\n"
        + SCRIPT_B.read_text(encoding="utf-8").rstrip("\n")
        + "\n"
    )
    OUTPUT.write_text(full, encoding="utf-8")
    print(f"assembled -> {OUTPUT.name}")
    return _check(full)


if __name__ == "__main__":
    sys.exit(main())
