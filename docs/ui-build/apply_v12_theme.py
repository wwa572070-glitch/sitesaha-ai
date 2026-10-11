"""把 V12 视觉层注入 index_head.html 的 </style> 之前。

V12 层只覆盖视觉令牌与卡片密度，不改任何类名与结构，
因此脚本动态创建的 91 个类名全部保留，功能不受影响。

用法：python apply_v12_theme.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
HEAD = BUILD / "index_head.html"
THEME = BUILD / "v12_theme.css"
DARK = BUILD / "v12_dark.css"
BOOT = BUILD / "theme_boot.js"

BEGIN = "/* ===== V12 THEME BEGIN ====="
END = "/* ===== V12 THEME END ===== */"
DARK_BEGIN = "/* ===== V12 DARK BEGIN ====="
DARK_END = "/* ===== V12 DARK END ===== */"
BOOT_BEGIN = "<!-- ===== THEME BOOT BEGIN ====="
BOOT_END = "<!-- ===== THEME BOOT END ===== -->"


def upsert_script(head: str, path: Path, begin: str, end: str, label: str) -> tuple[str, str]:
    """把 theme_boot.js 作为内联脚本插到 </head> 之前（必须同步执行）。"""
    if not path.is_file():
        return head, f"[FAIL] 缺少 {path.name}"
    content = path.read_text(encoding="utf-8").strip()
    block = f"{begin} -->\n<script>\n{content}\n</script>\n{end}\n"
    if begin in head:
        pattern = re.compile(re.escape(begin) + r".*?" + re.escape(end) + r"\n", re.S)
        head_new, n = pattern.subn(block, head)
        if n != 1:
            return head, f"[FAIL] 替换 {label} 失败（命中 {n} 次）"
        return head_new, f"[ok] 已更新{label}"
    if head.count("</head>") != 1:
        return head, f"[FAIL] </head> 命中 {head.count('</head>')} 次，应为 1"
    return head.replace("</head>", block + "</head>"), f"[ok] 已插入{label}"


def upsert(head: str, path: Path, begin: str, end: str, label: str) -> tuple[str, str]:
    """把 path 的内容作为 begin/end 包裹的块写入 head（已存在则替换）。"""
    if not path.is_file():
        return head, f"[FAIL] 缺少 {path.name}"
    content = path.read_text(encoding="utf-8").strip()
    block = f"{begin} */\n{content}\n{end}\n"
    if begin in head:
        pattern = re.compile(re.escape(begin) + r".*?" + re.escape(end) + r"\n", re.S)
        head_new, n = pattern.subn(block, head)
        if n != 1:
            return head, f"[FAIL] 替换 {label} 失败（命中 {n} 次）"
        return head_new, f"[ok] 已更新{label}"
    if head.count("</style>") != 1:
        return head, f"[FAIL] </style> 命中 {head.count('</style>')} 次，应为 1"
    return head.replace("</style>", block + "</style>"), f"[ok] 已追加{label}"


def main() -> int:
    if not HEAD.is_file():
        print("[FAIL] 缺少 index_head.html")
        return 1

    head = HEAD.read_text(encoding="utf-8")
    before = len(head)
    failed = False

    for path, begin, end, label in (
        (THEME, BEGIN, END, "V12 视觉层"),
        (DARK, DARK_BEGIN, DARK_END, "V12 暗色主题"),
    ):
        head, message = upsert(head, path, begin, end, label)
        print(message)
        if message.startswith("[FAIL]"):
            failed = True

    # 主题上色逻辑并进 index_script_a.js（单独 <script> 块会让 check_js 失效）
    if BOOT.is_file():
        import subprocess  # noqa: PLC0415

        result = subprocess.run(
            [sys.executable, str(BUILD / "merge_theme_boot.py")],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        print((result.stdout or "").strip())
        if result.returncode != 0:
            print((result.stderr or "").strip()[:300])
            failed = True

    if failed:
        return 1

    HEAD.write_text(head, encoding="utf-8")
    print(f"index_head.html：{before} → {len(head)} 字符")
    return 0


if __name__ == "__main__":
    sys.exit(main())
