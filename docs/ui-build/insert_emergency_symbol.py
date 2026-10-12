"""直接补 ill-emergency 符号（第三次尝试，读回验证）。

前两次失败：补丁报成功，但文件里实际没有。
本次用最简单的字符串操作，并且**写完立刻读回断言**，
不成功就报错退出，绝不谎报。

用法：python insert_emergency_symbol.py
"""

from __future__ import annotations

import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
BODY = BUILD / "index_body.html"

SYMBOL = '''  <symbol id="ill-emergency" viewBox="0 0 240 130">
    <path d="M8 116h224"/>
    <path d="M34 96V74h6V60a4 4 0 0 1 8 0v14h4V56a4 4 0 0 1 8 0v18h4V62a4 4 0 0 1 8 0v16h4V70a4 4 0 0 1 8 0v18a14 14 0 0 1-14 14H48a14 14 0 0 1-14-14z"/>
    <path d="M26 46h44"/>
    <text x="26" y="38" font-size="10" fill="currentColor">1 停手</text>
    <text x="24" y="128" font-size="10" fill="currentColor">停止作业</text>
    <circle cx="112" cy="60" r="6"/>
    <path d="M112 66v20M112 72l-9 8M112 72l9 8M112 86l-7 12M112 86l7 12"/>
    <path d="M132 76h30M152 68l10 8-10 8"/>
    <text x="104" y="38" font-size="10" fill="currentColor">2 撤离</text>
    <text x="100" y="128" font-size="10" fill="currentColor">撤到安全区</text>
    <rect x="184" y="72" width="34" height="26" rx="4"/>
    <path d="M192 86h18"/>
    <path d="M194 64a7 7 0 0 1 14 0"/>
    <path d="M201 54v6"/>
    <text x="182" y="38" font-size="10" fill="currentColor">3 报告</text>
    <text x="178" y="128" font-size="10" fill="currentColor">报告负责人</text>
  </symbol>

'''


def main() -> int:
    text = BODY.read_text(encoding="utf-8")
    marker = 'id="ill-emergency"'
    print(f"插入前：{marker} 出现 {text.count(marker)} 次")

    if text.count(marker) >= 1 and '<symbol id="ill-emergency"' in text:
        print("[跳过] 符号已存在")
        return 0

    anchor = '  <symbol id="ill-ppe"'
    if anchor not in text:
        print(f"[FAIL] 找不到锚点 {anchor!r}")
        return 1
    print(f"锚点出现 {text.count(anchor)} 次，在其中第一个之前插入")

    text = text.replace(anchor, SYMBOL + anchor, 1)
    BODY.write_text(text, encoding="utf-8")

    # 写完立刻读回
    check = BODY.read_text(encoding="utf-8")
    found = check.count('<symbol id="ill-emergency"')
    print(f"写回后复验：<symbol id=\"ill-emergency\" 出现 {found} 次")
    if found != 1:
        print("[FAIL] 复验不通过 —— 不再谎报成功")
        return 1
    print("[OK] 符号确实已写入")
    return 0


if __name__ == "__main__":
    sys.exit(main())
