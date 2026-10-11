"""修正 VERIFY_ONLINE.ps1 预检提示里的引号。

问题：用了 `\\"off\\"`（反斜杠转义），PowerShell 里会丢掉引号，
显示成 $env:SITESHAHA_LLM_MODE= off，直接复制粘贴会语法错误。
PowerShell 的转义符是反引号，正确写法是 `"off`"。

用法：python fix_preflight_quote.py
"""

from __future__ import annotations

import sys
from pathlib import Path

DELIVERY = Path(__file__).resolve().parent.parent.parent.parent
TARGET = DELIVERY / "VERIFY_ONLINE.ps1"

BAD = 'Write-Host "    `$env:SITESHAHA_LLM_MODE="off"; python webapp.py --port $port" -ForegroundColor DarkGray'
# 用单引号包裹整条命令：内部的 "off" 不会提前闭合字符串，也无需转义
GOOD = "Write-Host '    $env:SITESHAHA_LLM_MODE=\"off\"; python webapp.py --port $port' -ForegroundColor DarkGray"


def main() -> int:
    if not TARGET.is_file():
        print(f"未找到 {TARGET}")
        return 1

    text = TARGET.read_bytes().decode("utf-8-sig")
    if GOOD in text:
        print("引号已正确，无需修改")
        return 0

    count = text.count(BAD)
    if count != 1:
        print(f"[FAIL] 锚点命中 {count} 次（应为 1）")
        # 打印实际那一行便于人工核对
        for line in text.split("\n"):
            if "SITESHAHA_LLM_MODE" in line and "webapp.py" in line:
                print("实际行：", repr(line))
        return 1

    text = text.replace(BAD, GOOD)
    TARGET.write_bytes(b"\xef\xbb\xbf" + text.encode("utf-8"))
    print("[ok] 引号已修正；写回 UTF-8 BOM")
    return 0


if __name__ == "__main__":
    sys.exit(main())
