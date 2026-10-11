"""把 VERIFY_ONLINE.ps1 里的 [System.IO.Path]::GetTempPath() 换成纯变量路径。

原因：受限的 PowerShell（ConstrainedLanguage 模式）禁止 .NET 静态调用，
会让 Python 兜底通道整个失效。改用 $env:TEMP / $env:TMP / $PSScriptRoot 依次回退。

用正则匹配，避免缩进与行尾（CRLF/LF）导致的精确匹配失败。

用法：python patch_verify.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

DELIVERY = Path(__file__).resolve().parent.parent.parent.parent
TARGET = DELIVERY / "VERIFY_ONLINE.ps1"

# 匹配形如：  $probeFile = Join-Path ([System.IO.Path]::GetTempPath()) "sitesaha_probe.py"
LINE_PATTERN = re.compile(
    r'^(?P<indent>[ \t]*)\$(?P<var>\w+)\s*=\s*Join-Path\s*\(\[System\.IO\.Path\]::GetTempPath\(\)\)\s*(?P<tail>.*)$',
    re.MULTILINE,
)


def main() -> int:
    if not TARGET.is_file():
        print(f"未找到 {TARGET}")
        return 1

    text = TARGET.read_bytes().decode("utf-8-sig").replace("\r\n", "\n")
    matches = list(LINE_PATTERN.finditer(text))
    if not matches:
        if "[System.IO.Path]::GetTempPath()" in text:
            print("[FAIL] 仍有 GetTempPath 但未匹配到预期行，需人工检查")
            return 1
        print("已经没有 GetTempPath 调用，跳过")
        return 0

    def repl(match: re.Match[str]) -> str:
        indent = match.group("indent")
        var = match.group("var")
        tail = match.group("tail")
        return (
            f"{indent}# 不用 [System.IO.Path]::GetTempPath()：受限的 PowerShell 会禁止 .NET 静态调用\n"
            f"{indent}$probeDir = $env:TEMP\n"
            f"{indent}if (-not $probeDir) {{ $probeDir = $env:TMP }}\n"
            f"{indent}if (-not $probeDir) {{ $probeDir = $PSScriptRoot }}\n"
            f"{indent}${var} = Join-Path $probeDir {tail}"
        )

    text = LINE_PATTERN.sub(repl, text)

    remaining = text.count("[System.IO.Path]::GetTempPath()")
    if remaining:
        print(f"[FAIL] 仍有 {remaining} 处残留")
        return 1

    TARGET.write_bytes(b"\xef\xbb\xbf" + text.encode("utf-8"))
    print(f"[ok] 替换 {len(matches)} 处；文件写回 UTF-8 BOM")
    return 0


if __name__ == "__main__":
    sys.exit(main())
