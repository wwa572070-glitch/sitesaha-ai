"""把 VERIFY_ONLINE.ps1 的"服务未响应"提示改成可操作建议（纯文本，无嵌套引号）。

用法：python fix_verify_message.py
"""

from __future__ import annotations

import sys
from pathlib import Path

DELIVERY = Path(__file__).resolve().parent.parent.parent.parent
TARGET = DELIVERY / "VERIFY_ONLINE.ps1"

# 上一次改写引入的坏块（含未转义引号）
BROKEN_MARKER = "用 Python 单独验证（绕开 PowerShell 网络栈）"

OLD = "    Write-Host \"服务未响应。Render 免费实例休眠时冷启动需要 15-60 秒，请稍后重试。\" -ForegroundColor Yellow"

NEW_LINES = [
    '    Write-Host "服务未响应。请依次排查：" -ForegroundColor Yellow',
    '    Write-Host "  1) Render 免费实例休眠后冷启动需要 15-60 秒，稍等再试一次" -ForegroundColor Yellow',
    '    Write-Host "  2) 用浏览器打开线上地址的 /healthz 看能否访问" -ForegroundColor Yellow',
    '    Write-Host "     浏览器能打开但本脚本失败 = 本机网络或 TLS 问题，不是线上故障" -ForegroundColor Yellow',
    '    Write-Host "  3) 可改用同目录的 GO_ONLINE.ps1 先做本地与远端诊断" -ForegroundColor Yellow',
    '    Write-Host "  4) 仍失败则查看 Render 部署日志" -ForegroundColor Yellow',
]


def main() -> int:
    if not TARGET.is_file():
        print(f"未找到 {TARGET}")
        return 1

    text = TARGET.read_bytes().decode("utf-8-sig")

    # 先清理上一次写坏的行
    if BROKEN_MARKER in text:
        kept: list[str] = []
        skip_until_exit = False
        for line in text.split("\n"):
            if BROKEN_MARKER in line:
                skip_until_exit = True
                continue
            if skip_until_exit:
                # 丢掉坏块剩下的 Write-Host / exit 行，直到遇到 exit 1
                if line.strip() == "exit 1":
                    skip_until_exit = False
                    kept.append(line)
                    continue
                if line.strip().startswith("Write-Host"):
                    continue
                skip_until_exit = False
            kept.append(line)
        text = "\n".join(kept)
        print("已清理上一次写坏的提示块")

    if OLD not in text:
        if NEW_LINES[0] in text:
            print("提示已是新版，无需再改")
        else:
            print("[FAIL] 未找到可替换的旧提示行")
            return 1
    else:
        text = text.replace(OLD, "\n".join(NEW_LINES), 1)

    TARGET.write_bytes(b"\xef\xbb\xbf" + text.encode("utf-8"))
    print("[ok] 提示已更新；写回 UTF-8 BOM")
    return 0


if __name__ == "__main__":
    sys.exit(main())
