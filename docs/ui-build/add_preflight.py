"""给 VERIFY_ONLINE.ps1 加"本地地址预检"。

问题：脚本对 http://127.0.0.1:8504 验证时若本地服务未启动，只会报一句连接失败，
使用者容易误判成线上故障或脚本坏了。加预检后直接提示"请先启动本地服务 + 命令"。

用法：python add_preflight.py
"""

from __future__ import annotations

import sys
from pathlib import Path

DELIVERY = Path(__file__).resolve().parent.parent.parent.parent
TARGET = DELIVERY / "VERIFY_ONLINE.ps1"

ANCHOR = "# ---------- 1. 健康检查与版本 ----------\n"

PREFLIGHT = '''# ---------- 0. 本地地址预检 ----------
# 测本地服务时，先确认端口是否真的在监听，否则给明确指引而不是笼统的连接失败。
if ($BaseUrl -match '127\\.0\\.0\\.1|localhost') {
    $portMatch = [regex]::Match($BaseUrl, ':(\\d+)')
    if ($portMatch.Success) {
        $port = [int]$portMatch.Groups[1].Value
        $listening = $false
        try {
            $client = New-Object System.Net.Sockets.TcpClient
            $client.Connect("127.0.0.1", $port)
            $listening = $client.Connected
            $client.Close()
        } catch {
            $listening = $false
        }
        if ($listening) {
            Write-Host "  本地服务已在 127.0.0.1:$port 监听" -ForegroundColor Green
        } else {
            Write-Host ("  本地 127.0.0.1:{0} 没有服务在监听。" -f $port) -ForegroundColor Red
            Write-Host "  请先在另一个终端启动本地服务：" -ForegroundColor Yellow
            Write-Host "    cd <项目根>" -ForegroundColor DarkGray
            Write-Host "    `$env:SITESHAHA_LLM_MODE=\"off\"; python webapp.py --port $port" -ForegroundColor DarkGray
            Write-Host "  或直接改为验证线上：  .\\VERIFY_ONLINE.ps1 -ExpectedVersion 10.0.0" -ForegroundColor Yellow
            exit 2
        }
    }
}

'''


def main() -> int:
    if not TARGET.is_file():
        print(f"未找到 {TARGET}")
        return 1

    text = TARGET.read_bytes().decode("utf-8-sig")
    if "本地地址预检" in text:
        print("已经加过预检，跳过")
        return 0

    count = text.count(ANCHOR)
    if count != 1:
        print(f"[FAIL] 锚点命中 {count} 次（应为 1）")
        return 1

    text = text.replace(ANCHOR, PREFLIGHT + ANCHOR)
    TARGET.write_bytes(b"\xef\xbb\xbf" + text.encode("utf-8"))
    print("[ok] 已加入本地地址预检；写回 UTF-8 BOM")
    return 0


if __name__ == "__main__":
    sys.exit(main())
