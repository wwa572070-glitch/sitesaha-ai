"""把 V14 层加到注入链的最后，并同步暗色版。

层序：V13 设计系统 → V13 流程阶段 → V13 布局 → V14 实测校正 → V13 暗色
（暗色放最后，保证深色模式的令牌覆盖生效）

用法：python apply_v14_theme.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
APPLIER = BUILD / "apply_v13_theme.py"

V14_ENTRY = (
    '    ("v14_theme.css", "/* ===== V14 THEME BEGIN =====", '
    '"/* ===== V14 THEME END ===== */", "V14 实测校正"),\n'
)
V13_DARK_ENTRY = (
    '    ("v13_dark.css", "/* ===== V13 DARK BEGIN =====", '
    '"/* ===== V13 DARK END ===== */", "V13 暗色"),\n'
)


def main() -> int:
    text = APPLIER.read_text(encoding="utf-8")
    if "v14_theme.css" in text:
        print("[跳过] 注入链里已有 V14")
    else:
        if V13_DARK_ENTRY not in text:
            print("[FAIL] 找不到 V13 暗色条目，无法插入 V14")
            return 1
        # V14 插在 V13 暗色之前：亮色校正先生效，暗色再覆盖
        text = text.replace(V13_DARK_ENTRY, V14_ENTRY + V13_DARK_ENTRY, 1)
        APPLIER.write_text(text, encoding="utf-8")
        print("[ok] 注入链已插入 V14（位于 V13 暗色之前）")

    # 执行注入
    import subprocess  # noqa: PLC0415

    result = subprocess.run(
        [sys.executable, str(APPLIER)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    print((result.stdout or "").strip())
    if result.returncode != 0:
        print((result.stderr or "").strip()[:300])
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
