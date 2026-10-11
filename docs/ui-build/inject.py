"""把 _build/index_full.html 注入 webapp.py 的 INDEX_HTML 常量。

用法：
    python inject.py            # 注入并自检
    python inject.py --revert   # 从 webapp.py.bak-v91 还原 INDEX_HTML

自检项：
  1) 注入后 webapp.py 能被 ast 解析
  2) 从 webapp.py 里取回的 HTML 与 index_full.html 逐字节一致
  3) 旧接口字符串仍在（确保没有误删后端）
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
APP_DIR = BUILD.parent.parent  # docs/ui-build -> docs -> 项目根目录
WEBAPP = APP_DIR / "webapp.py"
BACKUP = APP_DIR / "webapp.py.bak-v91"
TEMPLATE = BUILD / "index_full.html"

MARKER_PATTERN = re.compile(r'INDEX_HTML = r?"""')
CLOSING = '"""'

# 注入后必须依然存在的后端契约
MUST_KEEP = [
    '"/api/status"',
    '"/api/cases"',
    '"/api/checklists"',
    '"/api/training"',
    '"/api/ask"',
    '"/api/inspect-image"',
    '"/healthz"',
    "class SiteSahaHandler",
    "class SiteSahaServer",
    "class RequestThrottle",
    "def build_services",
    "def answer_payload",
    "def main",
]

# 旧 INDEX_HTML 里必须被清掉的历史痕迹（说明替换生效）
MUST_GONE = [
    "home-safety-tools",
    "big-action",
    "emergencyGuides",
    "case-search input",
]


def extract_block(text: str) -> tuple[int, int, str]:
    """返回 (起始下标, 结束下标含尾部, 内容) 的 INDEX_HTML 字面量区间。"""
    found = MARKER_PATTERN.search(text)
    if not found:
        raise SystemExit("未找到 INDEX_HTML = \"\"\" 字面量")
    start = found.start()
    content_start = found.end()
    end = text.index(CLOSING, content_start)
    return start, end + len(CLOSING), text[content_start:end]


def main() -> int:
    revert = "--revert" in sys.argv
    source = BACKUP if revert else WEBAPP
    if not source.is_file():
        raise SystemExit(f"源文件不存在：{source}")

    text = WEBAPP.read_text(encoding="utf-8")
    start, end, old_html = extract_block(text)

    if revert:
        backup_text = BACKUP.read_text(encoding="utf-8")
        _b_start, _b_end, backup_html = extract_block(backup_text)
        new_html = backup_html
        label = "还原自 webapp.py.bak-v91"
    else:
        new_html = TEMPLATE.read_text(encoding="utf-8").rstrip("\n")
        label = "注入自 index_full.html"

    if '"""' in new_html:
        raise SystemExit("模板包含三引号，无法安全注入")
    if "\\" in new_html:
        # 新模板刻意不含反斜杠，这样可以改用非 raw 三引号字符串，避免转义歧义
        raise SystemExit("模板包含反斜杠，需要改用 raw 字符串后再注入")

    replacement = 'INDEX_HTML = """' + new_html + '"""'
    updated = text[:start] + replacement + text[end:]

    try:
        ast.parse(updated)
    except SyntaxError as exc:
        raise SystemExit(f"注入后 webapp.py 语法错误，已放弃写入：{exc}") from exc

    if not revert:
        _s, _e, written = extract_block(updated)
        if written != new_html:
            raise SystemExit("往返比对失败：写回的 HTML 与模板不一致")

    WEBAPP.write_text(updated, encoding="utf-8")

    problems: list[str] = []
    for needle in MUST_KEEP:
        if needle not in updated:
            problems.append(f"后端契约缺失：{needle}")
    if not revert:
        for needle in MUST_GONE:
            if needle in updated:
                problems.append(f"旧首页痕迹仍在：{needle}")

    print(f"{label}")
    print(f"INDEX_HTML: {len(old_html)} -> {len(new_html)} chars")
    print(f"webapp.py  : {len(text)} -> {len(updated)} chars, {updated.count(chr(10)) + 1} lines")
    if problems:
        for item in problems:
            print("  [FAIL]", item)
        return 1
    print("inject check: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
