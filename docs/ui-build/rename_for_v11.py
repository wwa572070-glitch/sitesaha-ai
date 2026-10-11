"""把脚本里的旧类名/旧 ID 适配到 V11 极简结构。"""

from __future__ import annotations

import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
FILES = [BUILD / "index_script_a.js", BUILD / "index_script_b.js"]

# (原文, 新文, 说明)
REPLACEMENTS = [
    ('make("div", "bubble-title"', 'make("div", "who"', "气泡标题类名"),
    ('make("div", "bubble-meta"', 'make("div", "meta"', "气泡元信息类名"),
    ('make("div", "answer-body"', 'make("div", "answer"', "回答正文类名"),
    ('make("ul", "document-list")', 'make("div", "doc-list")', "文档列表容器"),
    ('var li = make("li");', 'var li = make("div", "doc-row");', "文档行"),
    ('make("li", "source-meta"', 'make("div", "src"', "来源行"),
    ('list.appendChild(li);', 'list.appendChild(li);', "占位，不改"),
    ('$("headerRole")', '$("roleChip")', "顶栏工种标签 id"),
    ('"当前工种：" + role', '"工种：" + role', "顶栏文案精简"),
    ('"工种未选择"', '"工种未选"', "顶栏文案精简"),
]


def main() -> int:
    changed_total = 0
    for path in FILES:
        if not path.is_file():
            print(f"[跳过] {path.name} 不存在")
            continue
        text = path.read_text(encoding="utf-8")
        hits = 0
        for old, new, label in REPLACEMENTS:
            if old == new:
                continue
            count = text.count(old)
            if count:
                text = text.replace(old, new)
                hits += count
                print(f"  {path.name}: {label} ×{count}")
        path.write_text(text, encoding="utf-8")
        changed_total += hits
        print(f"[ok] {path.name} 共替换 {hits} 处")

    if changed_total == 0:
        print("没有任何替换，可能已经改过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
