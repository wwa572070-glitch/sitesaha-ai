"""把 VERIFY_ONLINE.ps1 里对 [System.IO.Path]::GetTempPath() 的调用改成纯变量路径。

原因：受限的 PowerShell（ConstrainedLanguage 模式）禁止 .NET 静态调用，
会让脚本里的 Python 兜底通道整个失效。改用 $env:TEMP / $env:TMP / $PSScriptRoot。

用法：python fix_temp_path.py
"""

from __future__ import annotations

import sys
from pathlib import Path

DELIVERY = Path(__file__).resolve().parent.parent.parent.parent
TARGET = DELIVERY / "VERIFY_ONLINE.ps1"
NEEDLE = "[System.IO.Path]::GetTempPath()"
COMMENT = "# 路径回退不使用 .NET 静态方法：受限的 PowerShell 会禁止这类调用"


def main() -> int:
    if not TARGET.is_file():
        print(f"未找到 {TARGET}")
        return 1

    text = TARGET.read_bytes().decode("utf-8-sig")
    lines = text.split("\n")
    out: list[str] = []
    replaced = 0

    for line in lines:
        if NEEDLE not in line or "Join-Path" not in line:
            out.append(line)
            continue

        indent = line[: len(line) - len(line.lstrip())]
        stripped = line.strip()
        var = stripped.split("=", 1)[0].strip()
        # 取最外层 Join-Path 的右括号之后的内容作为文件名参数。
        # 注意不能用 split(")", 1)：第一个右括号属于 GetTempPath()，会把 ")" 带进来。
        tail = '"sitesaha_probe.py"'
        if ")" in stripped:
            after = stripped.rsplit(")", 1)[1].strip()
            if after:
                tail = after

        out.append(f"{indent}{COMMENT}")
        out.append(f"{indent}$probeDir = $env:TEMP")
        out.append(f"{indent}if (-not $probeDir) {{ $probeDir = $env:TMP }}")
        out.append(f"{indent}if (-not $probeDir) {{ $probeDir = $PSScriptRoot }}")
        out.append(f"{indent}{var} = Join-Path $probeDir {tail}")
        replaced += 1

    new_text = "\n".join(out)
    remaining = new_text.count(NEEDLE)
    print(f"替换 {replaced} 处；残留 {remaining} 处")

    if replaced == 0:
        print("无需改动" if remaining == 0 else "[FAIL] 未匹配到目标行")
        return 0 if remaining == 0 else 1
    if remaining:
        print("[FAIL] 仍有残留，未写入")
        return 1

    TARGET.write_bytes(b"\xef\xbb\xbf" + new_text.encode("utf-8"))
    print("[ok] 已写回 UTF-8 BOM")
    return 0


if __name__ == "__main__":
    sys.exit(main())
