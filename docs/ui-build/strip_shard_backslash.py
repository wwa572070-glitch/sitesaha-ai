"""去掉分片里唯一一处反斜杠（inject.py 禁止分片含反斜杠）。

原因：我给 HEIC 检测写的正则 /\\.(heic|heif)$/i 含转义点。
改为字符串判断，不引入反斜杠。

用法：python strip_shard_backslash.py
"""

from __future__ import annotations

import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
SCRIPT_B = BUILD / "index_script_b.js"
BACKSLASH = chr(92)


def main() -> int:
    text = SCRIPT_B.read_text(encoding="utf-8")
    before = text.count(BACKSLASH)
    if before == 0:
        print("[跳过] 没有反斜杠")
        return 0

    # 定位含反斜杠的那一行，打印出来便于人工确认
    for index, line in enumerate(text.split("\n"), 1):
        if BACKSLASH in line:
            print(f"  第 {index} 行: {line.strip()[:110]}")

    # 把正则判断换成字符串判断
    candidates = [
        '/' + BACKSLASH + '.(heic|heif)$/i.test(file.name || "")',
        '/' + BACKSLASH + '.(heic|heif)$/i.test(file.name)',
    ]
    replaced = False
    for old in candidates:
        if old in text:
            new = (
                'file.name.toLowerCase().indexOf(".heic") >= 0 ||'
                + "\n\n            " +
                'file.name.toLowerCase().indexOf(".heif") >= 0'
            )
            text = text.replace(old, new)
            replaced = True
            print(f"[ok] 已替换正则判断：{old}")
            break

    if not replaced:
        print("[FAIL] 未匹配到目标正则，需人工处理")
        return 1

    after = text.count(BACKSLASH)
    if after:
        print(f"[FAIL] 仍有 {after} 处反斜杠")
        return 1

    SCRIPT_B.write_text(text, encoding="utf-8")
    print(f"[ok] 反斜杠 {before} → {after}，index_script_b.js 已更新")
    return 0


if __name__ == "__main__":
    sys.exit(main())
