"""把真实 SHA-256 写进 DESIGN.md 的 Source Evidence 段，让 design-baseline 认可该基线。"""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

APP = Path(__file__).resolve().parent.parent.parent
SOURCES = [
    "docs/ui-build/v15_theme.css",
    "docs/ui-build/v15_dark.css",
    "docs/ui-build/v13_layout.css",
    "docs/ui-build/v13_phases.css",
    "docs/ui-build/index_head.html",
    "docs/ui-build/index_body.html",
]


def main() -> int:
    lines: list[str] = []
    for rel in SOURCES:
        path = APP / rel
        if not path.is_file():
            print(f"[skip] {rel} 不存在")
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"- [observed] path: `{rel}`")
        lines.append(f"  sha256: `{digest}`")
        lines.append("  confidence: high")
    section = "## Source Evidence & Confidence\n\n" + "\n".join(lines) + "\n\n"

    for target in (".scratch/run-001/design-baseline/DESIGN.md", "DESIGN.md"):
        path = APP / target
        if not path.is_file():
            print(f"[skip] {target} 不存在")
            continue
        text = path.read_text(encoding="utf-8")
        start = text.find("## Source Evidence & Confidence")
        end = text.find("## 已归档")
        if start < 0 or end < 0:
            print(f"[FAIL] {target}: 找不到锚点")
            return 1
        text = text[:start] + section + text[end:]
        path.write_text(text, encoding="utf-8")
        found = len(re.findall(r"sha256: `[0-9a-f]{64}`", text))
        print(f"[ok] {target}: 写入 {found} 个来源哈希")
    return 0


if __name__ == "__main__":
    sys.exit(main())
