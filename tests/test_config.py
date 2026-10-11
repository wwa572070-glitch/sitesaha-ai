from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sitesaha.config import AppConfig


class ConfigTests(unittest.TestCase):
    def test_dotenv_is_loaded_without_overriding_process_environment(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".env").write_text(
                "\n".join(
                    [
                        "SITESHAHA_LLM_MODE=on",
                        "SITESHAHA_LLM_BASE_URL=https://api.deepseek.com/v1",
                        "SITESHAHA_LLM_API_KEY=from-dotenv",
                        "SITESHAHA_LLM_MODEL=deepseek-chat",
                        "SITESHAHA_RATE_LIMIT_PER_MINUTE=25",
                        "SITESHAHA_TRUST_PROXY_HEADERS=true",
                    ]
                ),
                encoding="utf-8",
            )
            with patch.dict(
                os.environ,
                {
                    "SITESHAHA_PROJECT_ROOT": str(root),
                    "SITESHAHA_LLM_API_KEY": "from-process",
                },
                clear=True,
            ):
                config = AppConfig.from_env()

        self.assertTrue(config.model_configured)
        self.assertEqual(config.llm_api_key, "from-process")
        self.assertEqual(config.llm_model, "deepseek-chat")
        self.assertEqual(config.rate_limit_per_minute, 25)
        self.assertTrue(config.trust_proxy_headers)

    def test_asr_is_unconfigured_by_default(self) -> None:
        # 隔离真实 .env：指向一个空的临时项目根，_load_dotenv 会落空。
        # 否则项目里那份已配好 ASR 的 .env 会让「默认未配置」不再成立。
        with tempfile.TemporaryDirectory() as empty_root:
            with patch.dict(
                os.environ, {"SITESHAHA_PROJECT_ROOT": empty_root}, clear=True
            ):
                config = AppConfig.from_env()

        self.assertFalse(config.asr_configured)
        self.assertEqual(config.asr_endpoint, "")

    def test_asr_endpoint_is_built_from_base_url(self) -> None:
        with patch.dict(
            os.environ,
            {
                "SITESHAHA_ASR_BASE_URL": "https://asr.example.com/v1/",
                "SITESHAHA_ASR_MODEL": "whisper-1",
            },
            clear=True,
        ):
            config = AppConfig.from_env()

        self.assertTrue(config.asr_configured)
        self.assertEqual(
            config.asr_endpoint, "https://asr.example.com/v1/audio/transcriptions"
        )

    def test_asr_endpoint_path_can_be_overridden(self) -> None:
        with patch.dict(
            os.environ,
            {
                "SITESHAHA_ASR_BASE_URL": "https://asr.example.com",
                "SITESHAHA_ASR_MODEL": "sensevoice",
                "SITESHAHA_ASR_ENDPOINT_PATH": "v1/asr",
            },
            clear=True,
        ):
            config = AppConfig.from_env()

        # 缺少前导斜杠时自动补上，避免拼出不存在的路径
        self.assertEqual(config.asr_endpoint, "https://asr.example.com/v1/asr")

    def test_vision_and_asr_are_independent(self) -> None:
        with tempfile.TemporaryDirectory() as empty_root:
            with patch.dict(
                os.environ,
                {
                    "SITESHAHA_PROJECT_ROOT": empty_root,
                    "SITESHAHA_VISION_BASE_URL": "https://vision.example.com/v1",
                    "SITESHAHA_VISION_MODEL": "qwen-vl",
                    "SITESHAHA_ASR_BASE_URL": "https://asr.example.com/v1",
                    "SITESHAHA_ASR_MODEL": "whisper-1",
                },
                clear=True,
            ):
                config = AppConfig.from_env()

        self.assertTrue(config.vision_configured)
        self.assertTrue(config.asr_configured)

        # 同样隔离 .env，否则真实配置会让 asr_configured 为真
        with tempfile.TemporaryDirectory() as empty_root:
            with patch.dict(
                os.environ,
                {
                    "SITESHAHA_PROJECT_ROOT": empty_root,
                    "SITESHAHA_VISION_BASE_URL": "https://vision.example.com/v1",
                    "SITESHAHA_VISION_MODEL": "qwen-vl",
                },
                clear=True,
            ):
                vision_only = AppConfig.from_env()

        self.assertTrue(vision_only.vision_configured)
        self.assertFalse(vision_only.asr_configured)


if __name__ == "__main__":
    unittest.main()
