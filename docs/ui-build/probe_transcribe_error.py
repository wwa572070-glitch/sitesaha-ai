"""抓 /api/transcribe 的真实异常（用真 SiteSahaServer，不用手搭）。

用法：python probe_transcribe_error.py
"""

from __future__ import annotations

import sys
import threading
import time
import traceback
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import Mock

APP = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(APP))

import webapp  # noqa: E402
from sitesaha.config import AppConfig  # noqa: E402
from sitesaha.models import Answer  # noqa: E402

PROJECT_ROOT = APP


def main() -> int:
    config = AppConfig(
        project_root=PROJECT_ROOT,
        db_path=PROJECT_ROOT / "data" / "test-probe.db",
        knowledge_dir=PROJECT_ROOT / "data" / "knowledge",
        asr_base_url="https://asr.example.com/v1",
        asr_model="whisper-1",
    )
    engine = Mock()
    engine.answer.return_value = Answer(text="测试回答", mode="extractive")
    engine.model.transcribe_audio.return_value = "识别出来的问题"
    services = webapp.Services(config=config, kb=Mock(), engine=engine)

    # 包住 do_POST，把被吞掉的异常打出来
    original = webapp.SiteSahaHandler.do_POST

    def traced(self):  # noqa: ANN001
        try:
            original(self)
        except SystemExit:
            raise
        except BaseException:  # noqa: BLE001
            print("=== do_POST 内部抛出异常 ===")
            traceback.print_exc()
            raise

    webapp.SiteSahaHandler.do_POST = traced

    server = webapp.SiteSahaServer(("127.0.0.1", 0), webapp.SiteSahaHandler, services)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    time.sleep(0.4)
    base = f"http://127.0.0.1:{server.server_port}"

    boundary = "----ProbeBoundary7f3a"
    body = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="audio"; filename="a.wav"\r\n'
        "Content-Type: audio/wav\r\n\r\n"
    ).encode() + b"\x00" * 4000 + f"\r\n--{boundary}--\r\n".encode()

    request = urllib.request.Request(
        base + "/api/transcribe", data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    print("=== POST /api/transcribe（空音频，期望 400）===")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            print("  HTTP", response.status, response.read().decode("utf-8", "replace")[:200])
    except urllib.error.HTTPError as exc:
        print("  HTTP", exc.code, exc.read().decode("utf-8", "replace")[:200])
    except Exception as exc:  # noqa: BLE001
        print("  客户端异常:", type(exc).__name__, exc)

    print()
    print("=== POST /api/ask（对照）===")
    request2 = urllib.request.Request(
        base + "/api/ask",
        data=b'{"question":"test"}',
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request2, timeout=30) as response:
            print("  HTTP", response.status, response.read().decode("utf-8", "replace")[:160])
    except urllib.error.HTTPError as exc:
        print("  HTTP", exc.code, exc.read().decode("utf-8", "replace")[:200])

    server.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
