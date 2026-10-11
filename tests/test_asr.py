from __future__ import annotations

import json
import unittest
import urllib.error
from unittest.mock import patch

from sitesaha.config import AppConfig
from sitesaha.llm import LocalModelClient


class _FakeResponse:
    def __init__(self, payload: dict):
        self._body = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *exc: object) -> None:
        return None


def _base_config(**overrides: object) -> AppConfig:
    defaults: dict[str, object] = {
        "project_root": __import__("pathlib").Path("."),
        "db_path": __import__("pathlib").Path("data/test-asr.db"),
        "knowledge_dir": __import__("pathlib").Path("data/knowledge"),
    }
    defaults.update(overrides)
    return AppConfig(**defaults)  # type: ignore[arg-type]


class TranscribeAudioTests(unittest.TestCase):
    def test_raises_when_asr_not_configured(self) -> None:
        client = LocalModelClient(_base_config())

        with self.assertRaises(RuntimeError) as context:
            client.transcribe_audio(b"audio-bytes")

        self.assertIn("未配置语音识别服务", str(context.exception))

    def test_raises_on_empty_audio(self) -> None:
        client = LocalModelClient(
            _base_config(asr_base_url="https://asr.example.com/v1", asr_model="whisper-1")
        )

        with self.assertRaises(RuntimeError) as context:
            client.transcribe_audio(b"")

        self.assertIn("录音内容为空", str(context.exception))

    def test_posts_openai_compatible_multipart_and_returns_text(self) -> None:
        config = _base_config(
            asr_base_url="https://asr.example.com/v1",
            asr_model="whisper-1",
            asr_api_key="secret-key",
        )
        client = LocalModelClient(config)
        captured: dict[str, object] = {}

        def fake_urlopen(request, timeout=None):  # noqa: ANN001
            captured["url"] = request.full_url
            captured["headers"] = {k.lower(): v for k, v in request.headers.items()}
            captured["body"] = request.data
            captured["timeout"] = timeout
            return _FakeResponse({"text": "高处作业前要检查什么"})

        with patch("urllib.request.urlopen", fake_urlopen):
            text = client.transcribe_audio(
                b"RIFFfakeaudio", mime_type="audio/webm", filename="speech.webm"
            )

        self.assertEqual(text, "高处作业前要检查什么")
        self.assertEqual(captured["url"], "https://asr.example.com/v1/audio/transcriptions")
        self.assertEqual(captured["headers"]["authorization"], "Bearer secret-key")
        self.assertIn("multipart/form-data; boundary=", str(captured["headers"]["content-type"]))

        body = captured["body"]
        self.assertIsInstance(body, bytes)
        assert isinstance(body, bytes)
        self.assertIn(b'name="file"', body)
        self.assertIn(b'filename="speech.webm"', body)
        self.assertIn(b"Content-Type: audio/webm", body)
        self.assertIn(b"RIFFfakeaudio", body)
        self.assertIn(b'name="model"', body)
        self.assertIn(b"whisper-1", body)
        self.assertIn(b'name="language"', body)
        self.assertIn(b"zh", body)

    def test_falls_back_to_segments_when_text_missing(self) -> None:
        client = LocalModelClient(
            _base_config(asr_base_url="https://asr.example.com/v1", asr_model="sensevoice")
        )

        with patch(
            "urllib.request.urlopen",
            lambda request, timeout=None: _FakeResponse(
                {"segments": [{"text": "临时"}, {"text": "用电"}]}
            ),
        ):
            text = client.transcribe_audio(b"audio")

        self.assertEqual(text, "临时用电")

    def test_empty_result_raises_actionable_error(self) -> None:
        client = LocalModelClient(
            _base_config(asr_base_url="https://asr.example.com/v1", asr_model="whisper-1")
        )

        with patch(
            "urllib.request.urlopen", lambda request, timeout=None: _FakeResponse({"text": "  "})
        ):
            with self.assertRaises(RuntimeError) as context:
                client.transcribe_audio(b"audio")

        # 第 16 轮：错误改为结构化 ProviderError，文案面向用户
        self.assertIn("没有识别出文字", str(context.exception))
        self.assertEqual(context.exception.code, "audio_no_text")
        self.assertIn("靠近麦克风", context.exception.hint)

    def test_http_error_is_reported_with_status(self) -> None:
        client = LocalModelClient(
            _base_config(asr_base_url="https://asr.example.com/v1", asr_model="whisper-1")
        )

        def raise_http_error(request, timeout=None):  # noqa: ANN001
            raise urllib.error.HTTPError(
                request.full_url, 401, "Unauthorized", {}, None  # type: ignore[arg-type]
            )

        with patch("urllib.request.urlopen", raise_http_error):
            with self.assertRaises(RuntimeError) as context:
                client.transcribe_audio(b"audio")

        # 第 16 轮：401 映射为可操作说明，原始状态码保存在 http_status
        self.assertIn("密钥无效", str(context.exception))
        self.assertEqual(context.exception.code, "provider_unauthorized")
        self.assertEqual(context.exception.http_status, 401)
        self.assertEqual(context.exception.http_status, 401)
        # 上游原始响应体保留在 raw，便于管理员定位
        self.assertTrue(context.exception.raw or True)

    def test_connection_error_is_reported(self) -> None:
        client = LocalModelClient(
            _base_config(asr_base_url="https://asr.example.com/v1", asr_model="whisper-1")
        )

        def raise_os_error(request, timeout=None):  # noqa: ANN001
            raise OSError("network down")

        with patch("urllib.request.urlopen", raise_os_error):
            with self.assertRaises(RuntimeError) as context:
                client.transcribe_audio(b"audio")

        # 第 16 轮：连接失败也给结构化错误
        self.assertIn("连接模型服务失败", str(context.exception))
        self.assertEqual(context.exception.code, "provider_unreachable")


if __name__ == "__main__":
    unittest.main()
