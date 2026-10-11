from __future__ import annotations

import json
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import Mock

from sitesaha.config import AppConfig
from sitesaha.models import Answer
from webapp import Services, SiteSahaHandler, SiteSahaServer


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class WebAppTests(unittest.TestCase):
    def _start_server(
        self,
        *,
        access_code: str = "",
        rate_limit: int = 60,
        trust_proxy_headers: bool = False,
        asr_configured: bool = False,
    ) -> tuple[SiteSahaServer, str]:
        config = AppConfig(
            project_root=PROJECT_ROOT,
            db_path=PROJECT_ROOT / "data" / "test-web.db",
            knowledge_dir=PROJECT_ROOT / "data" / "knowledge",
            access_code=access_code,
            rate_limit_per_minute=rate_limit,
            trust_proxy_headers=trust_proxy_headers,
            asr_base_url="https://asr.example.com/v1" if asr_configured else "",
            asr_model="whisper-1" if asr_configured else "",
        )
        engine = Mock()
        engine.answer.return_value = Answer(text="测试回答", mode="extractive")
        engine.model.transcribe_audio.return_value = "识别出来的问题"
        services = Services(config=config, kb=Mock(), engine=engine)
        server = SiteSahaServer(("127.0.0.1", 0), SiteSahaHandler, services)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server, f"http://127.0.0.1:{server.server_port}"

    @staticmethod
    def _multipart(fields: dict[str, str], file_field: str, filename: str,
                   payload: bytes, content_type: str) -> tuple[bytes, str]:
        boundary = "----testboundary1234567890"
        chunks: list[bytes] = []
        for name, value in fields.items():
            chunks.append(
                (
                    f"--{boundary}\r\n"
                    f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
                    f"{value}\r\n"
                ).encode("utf-8")
            )
        if payload:
            chunks.append(
                (
                    f"--{boundary}\r\n"
                    f'Content-Disposition: form-data; name="{file_field}"; '
                    f'filename="{filename}"\r\n'
                    f"Content-Type: {content_type}\r\n\r\n"
                ).encode("utf-8")
            )
            chunks.append(payload)
            chunks.append(b"\r\n")
        chunks.append(f"--{boundary}--\r\n".encode("utf-8"))
        return b"".join(chunks), f"multipart/form-data; boundary={boundary}"

    def test_healthz_has_security_headers(self) -> None:
        server, base_url = self._start_server()
        try:
            with urllib.request.urlopen(f"{base_url}/healthz", timeout=5) as response:
                payload = json.loads(response.read().decode("utf-8"))
                self.assertEqual(payload["status"], "ok")
                self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
                self.assertIn("frame-ancestors 'none'", response.headers["Content-Security-Policy"])
        finally:
            server.shutdown()
            server.server_close()

    def test_access_code_is_required_for_questions(self) -> None:
        server, base_url = self._start_server(access_code="project-code")
        try:
            request = urllib.request.Request(
                f"{base_url}/api/ask",
                data=json.dumps({"question": "安全帽怎么戴"}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with self.assertRaises(urllib.error.HTTPError) as context:
                urllib.request.urlopen(request, timeout=5)
            self.assertEqual(context.exception.code, 401)

            request.add_header("X-Access-Code", "project-code")
            with urllib.request.urlopen(request, timeout=5) as response:
                payload = json.loads(response.read().decode("utf-8"))
                self.assertEqual(payload["text"], "测试回答")
        finally:
            server.shutdown()
            server.server_close()

    def test_rate_limit_returns_429(self) -> None:
        server, base_url = self._start_server(rate_limit=1)
        try:
            request = urllib.request.Request(
                f"{base_url}/api/ask",
                data=json.dumps({"question": "高处作业"}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=5) as response:
                self.assertEqual(response.status, 200)
            with self.assertRaises(urllib.error.HTTPError) as context:
                urllib.request.urlopen(request, timeout=5)
            self.assertEqual(context.exception.code, 429)
            self.assertEqual(context.exception.headers["Retry-After"], "60")
        finally:
            server.shutdown()
            server.server_close()

    def test_forwarded_ip_is_used_when_proxy_headers_are_trusted(self) -> None:
        server, base_url = self._start_server(
            rate_limit=1, trust_proxy_headers=True
        )
        try:
            for client_ip in ("203.0.113.10", "203.0.113.11"):
                request = urllib.request.Request(
                    f"{base_url}/api/ask",
                    data=json.dumps({"question": "高处作业"}).encode("utf-8"),
                    headers={
                        "Content-Type": "application/json",
                        "X-Forwarded-For": client_ip,
                    },
                    method="POST",
                )
                with urllib.request.urlopen(request, timeout=5) as response:
                    self.assertEqual(response.status, 200)
        finally:
            server.shutdown()
            server.server_close()

    def test_healthz_reports_asr_flag(self) -> None:
        server, base_url = self._start_server(asr_configured=True)
        try:
            with urllib.request.urlopen(f"{base_url}/healthz", timeout=5) as response:
                payload = json.loads(response.read().decode("utf-8"))
            self.assertTrue(payload["asr_configured"])
            self.assertFalse(payload["vision_configured"])
        finally:
            server.shutdown()
            server.server_close()

    def test_inspect_image_degrades_clearly_when_vision_missing(self) -> None:
        server, base_url = self._start_server()
        body, content_type = self._multipart({}, "image", "site.jpg", b"fakejpeg", "image/jpeg")
        request = urllib.request.Request(
            f"{base_url}/api/inspect-image",
            data=body,
            headers={"Content-Type": content_type},
            method="POST",
        )
        try:
            with self.assertRaises(urllib.error.HTTPError) as context:
                urllib.request.urlopen(request, timeout=5)
            self.assertEqual(context.exception.code, 503)
            payload = json.loads(context.exception.read().decode("utf-8"))
            self.assertEqual(payload["error_code"], "vision_not_configured")
            self.assertIn("文字提问", payload["error"])
        finally:
            server.shutdown()
            server.server_close()

    def test_transcribe_degrades_clearly_when_asr_missing(self) -> None:
        server, base_url = self._start_server()
        body, content_type = self._multipart({}, "audio", "speech.webm", b"fakeaudio", "audio/webm")
        request = urllib.request.Request(
            f"{base_url}/api/transcribe",
            data=body,
            headers={"Content-Type": content_type},
            method="POST",
        )
        try:
            with self.assertRaises(urllib.error.HTTPError) as context:
                urllib.request.urlopen(request, timeout=5)
            self.assertEqual(context.exception.code, 503)
            payload = json.loads(context.exception.read().decode("utf-8"))
            self.assertEqual(payload["error_code"], "asr_not_configured")
        finally:
            server.shutdown()
            server.server_close()

    def test_transcribe_returns_text_when_asr_configured(self) -> None:
        server, base_url = self._start_server(asr_configured=True)
        body, content_type = self._multipart(
            {"access_code": ""}, "audio", "speech.webm", b"fakeaudio", "audio/webm"
        )
        request = urllib.request.Request(
            f"{base_url}/api/transcribe",
            data=body,
            headers={"Content-Type": content_type},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                payload = json.loads(response.read().decode("utf-8"))
            self.assertEqual(response.status, 200)
            self.assertEqual(payload["text"], "识别出来的问题")
            self.assertEqual(payload["mode"], "server-asr")
        finally:
            server.shutdown()
            server.server_close()

    def test_transcribe_requires_access_code_when_configured(self) -> None:
        server, base_url = self._start_server(access_code="project-code", asr_configured=True)
        body, content_type = self._multipart({}, "audio", "speech.webm", b"fakeaudio", "audio/webm")
        request = urllib.request.Request(
            f"{base_url}/api/transcribe",
            data=body,
            headers={"Content-Type": content_type},
            method="POST",
        )
        try:
            with self.assertRaises(urllib.error.HTTPError) as context:
                urllib.request.urlopen(request, timeout=5)
            self.assertEqual(context.exception.code, 401)
        finally:
            server.shutdown()
            server.server_close()

    def test_transcribe_rejects_empty_audio(self) -> None:
        server, base_url = self._start_server(asr_configured=True)
        body, content_type = self._multipart({}, "audio", "speech.webm", b"", "audio/webm")
        request = urllib.request.Request(
            f"{base_url}/api/transcribe",
            data=body,
            headers={"Content-Type": content_type},
            method="POST",
        )
        try:
            with self.assertRaises(urllib.error.HTTPError) as context:
                urllib.request.urlopen(request, timeout=5)
            self.assertIn(context.exception.code, {400, 413})
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
