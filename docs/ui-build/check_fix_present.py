"""检查领域分布修复是否已进入各层产物。"""

from __future__ import annotations

import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
APP = BUILD.parent.parent

TARGETS = [
    BUILD / "index_script_a.js",
    BUILD / "index_script_b.js",
    BUILD / "index_full.html",
    APP / "webapp.py",
]

MARKERS = {
    "新逻辑(haystack)": "var haystack = ((document.title",
    "旧文案(暂无分类统计)": "暂无分类统计",
    "source字段": "metaParts.push(document.source)",
    "新空态文案": "知识库中还没有可归类的文档",
}


def main() -> int:
    for path in TARGETS:
        if not path.is_file():
            print(f"{path.name:22} 缺失")
            continue
        text = path.read_text(encoding="utf-8")
        parts = []
        for label, marker in MARKERS.items():
            parts.append(f"{label}={'有' if marker in text else '无'}")
        print(f"{path.name:22} " + "  ".join(parts))
    return 0


if __name__ == "__main__":
    sys.exit(main())
