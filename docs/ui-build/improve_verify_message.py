"""把 VERIFY_ONLINE.ps1 的"服务未响应"提示改成可操作建议。

用法：python improve_verify_message.py
"""

from __future__ import annotations

import sys
from pathlib import Path

DELIVERY = Path(__file__).resolve().parent.parent.parent.parent
TARGET = DELIVERY / "VERIFY_ONLINE.ps1"

OLD = '''    Write-Host "服务未响应。Render 免费实例休眠时冷启动需要 15-60 秒，请稍后重试。" -ForegroundColor Yellow
    Write-Host "若持续失败，请查看 Render 部署日志。" -ForegroundColor Yellow
    exit 1'''

NEW = '''    Write-Host "服务未响应。请依次排查：" -ForegroundColor Yellow
    Write-Host "  1) Render 免费实例休眠后冷启动需要 15-60 秒，稍等再试一次" -ForegroundColor Yellow
    Write-Host "  2) 打开 https://sitesaha-ai.onrender.com/healthz 看浏览器能否访问" -ForegroundColor Yellow
    Write-Host "     浏览器能打开但本脚本失败 = 本机网络/TLS 问题，不是线上故障" -ForegroundColor Yellow
    Write-Host "  3) 用 Python 单独验证（绕开 PowerShell 网络栈）：" -ForegroundColor Yellow
    Write-Host "       python -c \\"import urllib.request;print(urllib.request.urlopen('$BaseUrl/healthz',timeout=60).read().decode())\\"" -ForegroundColor DarkGray
    Write-Host "  4) 仍失败则查看 Render 部署日志" -ForegroundColor Yellow
    exit 1'''


def main() -> int:
    if not TARGET.is_file():
        print(f"未找到 {TARGET}")
        return 1

    text = TARGET.read_bytes().decode("utf-8-sig")
    count = text.count(OLD)
    if count == 0:
        print("未找到旧提示（可能已改）")
        return 0
    if count != 1:
        print(f"[FAIL] 锚点命中 {count} 次")
        return 1

    text = text.replace(OLD, NEW)
    TARGET.write_bytes(b"\xef\xbb\xbf" + text.encode("utf-8"))
    print("[ok] 提示已改为可操作建议；写回 UTF-8 BOM")
    return 0


if __name__ == "__main__":
    sys.exit(main())
