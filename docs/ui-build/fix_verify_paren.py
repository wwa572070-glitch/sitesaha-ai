"""修掉 VERIFY_ONLINE.ps1 第 53/154 行 Join-Path 后多余的右括号。

用法：python fix_verify_paren.py
"""

from __future__ import annotations

import sys
from pathlib import Path

DELIVERY = Path(__file__).resolve().parent.parent.parent.parent
TARGET = DELIVERY / "VERIFY_ONLINE.ps1"

BAD = "$probeFile = Join-Path $probeDir ) \"sitesaha_probe.py\""
GOOD = "$probeFile = Join-Path $probeDir \"sitesaha_probe.py\""


def main() -> int:
    if not TARGET.is_file():
        print(f"未找到 {TARGET}")
        return 1

    text = TARGET.read_bytes().decode("utf-8-sig")
    count = text.count(BAD)
    if count == 0:
        print("未发现多余括号行（可能已修）")
        return 0

    text = text.replace(BAD, GOOD)
    leftover = text.count(BAD)
    if leftover:
        print(f"[FAIL] 仍有 {leftover} 处")
        return 1

    TARGET.write_bytes(b"\xef\xbb\xbf" + text.encode("utf-8"))
    print(f"[ok] 修复 {count} 处；已写回 UTF-8 BOM")
    return 0


if __name__ == "__main__":
    sys.exit(main())
