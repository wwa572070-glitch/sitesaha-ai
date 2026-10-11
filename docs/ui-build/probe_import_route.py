"""修 /api/checklists/import 的 500（第 16 轮 §11）。

用真实 multipart 上传复现并抓异常，不靠推断。

用法：python probe_import_route.py
"""

from __future__ import annotations

import io
import json
import sys
import threading
import time
import traceback
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

APP = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(APP))

import webapp  # noqa: E402

BOUNDARY = "----ProbeImport7f3a"


def main() -> int:
    services = webapp.build_services()

    original = webapp.SiteSahaHandler.do_POST

    def traced(self):  # noqa: ANN001
        try:
            original(self)
        except SystemExit:
            raise
        except BaseException:  # noqa: BLE001
            print("=== do_POST 内部抛出异常 ===")
            traceback.print_exc()

    webapp.SiteSahaHandler.do_POST = traced

    server = webapp.SiteSahaServer(("127.0.0.1", 0), webapp.SiteSahaHandler, services)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    time.sleep(0.4)
    base = f"http://127.0.0.1:{server.server_port}"

    # 造一个真实的 csv multipart
    csv_text = (
        "类别,检查内容,判定要点,依据\n"
        "消防,灭火器压力表是否在绿区,指针在绿区,项目制度\n"
        "临时设施,宿舍内是否使用大功率电器,无电炉,项目制度\n"
    ).encode("utf-8")
    body = (
        f"--{BOUNDARY}\r\n"
        'Content-Disposition: form-data; name="file"; filename="check.csv"\r\n'
        "Content-Type: text/csv\r\n\r\n"
    ).encode() + csv_text + f"\r\n--{BOUNDARY}--\r\n".encode()

    print("=== POST /api/checklists/import (csv) ===")
    request = urllib.request.Request(
        base + "/api/checklists/import", data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={BOUNDARY}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            print("  HTTP", response.status)
            print("  " + response.read().decode("utf-8", "replace")[:400])
    except urllib.error.HTTPError as exc:
        print("  HTTP", exc.code)
        print("  " + exc.read().decode("utf-8", "replace")[:400])
    except Exception as exc:  # noqa: BLE001
        print("  客户端异常:", type(exc).__name__, exc)

    print()
    print("=== POST 一个 xlsx ===")
    try:
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.append(["类别", "检查内容", "判定要点", "依据"])
        ws.append(["消防", "消火栓是否被遮挡", "无遮挡", "项目制度"])
        buf = io.BytesIO()
        wb.save(buf)
        xlsx_bytes = buf.getvalue()
    except ImportError:
        xlsx_bytes = b""
        print("  (没有 openpyxl，跳过)")

    if xlsx_bytes:
        body2 = (
            f"--{BOUNDARY}\r\n"
            'Content-Disposition: form-data; name="file"; filename="check.xlsx"\r\n'
            "Content-Type: application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet\r\n\r\n"
        ).encode() + xlsx_bytes + f"\r\n--{BOUNDARY}--\r\n".encode()
        request2 = urllib.request.Request(
            base + "/api/checklists/import", data=body2,
            headers={"Content-Type": f"multipart/form-data; boundary={BOUNDARY}"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request2, timeout=30) as response:
                print("  HTTP", response.status)
                print("  " + response.read().decode("utf-8", "replace")[:400])
        except urllib.error.HTTPError as exc:
            print("  HTTP", exc.code)
            print("  " + exc.read().decode("utf-8", "replace")[:400])

    server.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
