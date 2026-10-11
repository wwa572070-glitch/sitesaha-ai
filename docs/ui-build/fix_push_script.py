"""修正 PUSH_AND_DEPLOY.ps1 里对 git 可执行文件的调用方式。

原脚本用 `& $git.Source` 调用，在 PowerShell 5.1 下会因对字符串结果取 .Source
而失效。改为显式取一次路径再调用。同时统一写入 UTF-8 BOM，避免中文乱码。

用法：python fix_push_script.py
"""

from __future__ import annotations

import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent          # docs/ui-build
ROOT = BUILD.parent.parent                       # sitesaha_v3（项目根）
DELIVERY = ROOT.parent                           # 交付根
TARGET = DELIVERY / "PUSH_AND_DEPLOY.ps1"


def main() -> int:
    if not TARGET.is_file():
        print(f"未找到 {TARGET}")
        return 1
    text = TARGET.read_bytes().decode("utf-8-sig")

    if "$git.Source" not in text:
        print("已经修过（无 $git.Source），跳过")
        return 0

    # Get-Command 的返回对象在 PS 5.1 下取 .Source 不可靠，
    # 统一改成先解析成明确的路径变量，再用 & $git 调用。
    pairs = [
        (
            "$git = Get-Command git -ErrorAction SilentlyContinue",
            "$gitCmd = Get-Command git -ErrorAction SilentlyContinue",
        ),
        ("if (-not $git) {", "if (-not $gitCmd) {"),
    ]
    for old, new in pairs:
        count = text.count(old)
        if count != 1:
            print(f"[FAIL] 未命中（{count} 次）：{old}")
            return 1
        text = text.replace(old, new)

    # 在 gitCmd 检查块之后声明 $git
    marker = "未找到 Git。请先安装 Git，或在已登录 GitHub 的 Git 客户端中推送 source 目录。"
    index = text.find(marker)
    if index < 0:
        print("[FAIL] 未找到 git 检查块的提示文案")
        return 1
    close = text.find("}", index)
    if close < 0:
        print("[FAIL] 未找到检查块的收尾花括号")
        return 1
    insert_at = close + 1
    text = text[:insert_at] + "\n$git = $gitCmd.Source\n" + text[insert_at:]

    before = text.count("$git.Source")
    text = text.replace("$git.Source", "$git")

    TARGET.write_bytes(b"\xef\xbb\xbf" + text.encode("utf-8"))
    print(f"[ok] 替换 $git.Source {before} 处；已写回 UTF-8 BOM")
    return 0


if __name__ == "__main__":
    sys.exit(main())
