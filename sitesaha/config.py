from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        return
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        name, value = line.split("=", 1)
        name = name.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if name:
            os.environ.setdefault(name, value)


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class AppConfig:
    project_root: Path
    db_path: Path
    knowledge_dir: Path
    sources_dir: Path = PROJECT_ROOT / "data" / "sources"
    normalized_sources_dir: Path = (
        PROJECT_ROOT / "data" / "sources" / "normalized"
    )
    top_k: int = 5
    max_context_chars: int = 9000
    llm_mode: str = "auto"
    llm_base_url: str = ""
    llm_model: str = "deepseek-chat"
    llm_api_key: str = "local"
    llm_timeout_seconds: int = 90
    vision_model: str = ""
    vision_base_url: str = ""
    vision_api_key: str = ""
    vision_api_style: str = "chat"
    asr_base_url: str = ""
    asr_api_key: str = ""
    asr_model: str = ""
    asr_endpoint_path: str = "/audio/transcriptions"
    asr_api_style: str = "chat"
    asr_timeout_seconds: int = 60
    max_audio_bytes: int = 4 * 1024 * 1024
    llm_api_style: str = "chat"
    max_image_bytes: int = 8 * 1024 * 1024
    rate_limit_per_minute: int = 60
    max_concurrent_requests: int = 4
    request_timeout_seconds: int = 30
    access_code: str = ""
    trust_proxy_headers: bool = False

    @classmethod
    def from_env(cls) -> "AppConfig":
        root = Path(os.getenv("SITESHAHA_PROJECT_ROOT", PROJECT_ROOT)).resolve()
        _load_dotenv(root / ".env")
        db_path = Path(
            os.getenv("SITESHAHA_DB_PATH", str(root / "data" / "sitesaha.db"))
        ).resolve()
        knowledge_dir = Path(
            os.getenv("SITESHAHA_KNOWLEDGE_DIR", str(root / "data" / "knowledge"))
        ).resolve()
        sources_dir = Path(
            os.getenv("SITESHAHA_SOURCES_DIR", str(root / "data" / "sources"))
        ).resolve()
        normalized_sources_dir = Path(
            os.getenv(
                "SITESHAHA_NORMALIZED_SOURCES_DIR",
                str(root / "data" / "sources" / "normalized"),
            )
        ).resolve()

        mode = os.getenv("SITESHAHA_LLM_MODE", "auto").strip().lower()
        if mode not in {"auto", "on", "off"}:
            mode = "auto"

        llm_base_url = os.getenv("SITESHAHA_LLM_BASE_URL", "").rstrip("/")
        llm_api_key = os.getenv("SITESHAHA_LLM_API_KEY", "")
        llm_api_style = os.getenv("SITESHAHA_LLM_API_STYLE", "chat").strip().lower()
        if llm_api_style not in {"chat", "responses"}:
            llm_api_style = "chat"

        vision_base_url = os.getenv(
            "SITESHAHA_VISION_BASE_URL", llm_base_url
        ).rstrip("/")
        vision_api_key = os.getenv(
            "SITESHAHA_VISION_API_KEY", llm_api_key
        )
        vision_api_style = os.getenv(
            "SITESHAHA_VISION_API_STYLE", llm_api_style
        ).strip().lower()
        if vision_api_style not in {"chat", "responses"}:
            vision_api_style = "chat"

        asr_base_url = os.getenv("SITESHAHA_ASR_BASE_URL", "").rstrip("/")
        asr_endpoint_path = os.getenv(
            "SITESHAHA_ASR_ENDPOINT_PATH", "/audio/transcriptions"
        ).strip()
        if not asr_endpoint_path.startswith("/"):
            asr_endpoint_path = "/" + asr_endpoint_path

        return cls(
            project_root=root,
            db_path=db_path,
            knowledge_dir=knowledge_dir,
            sources_dir=sources_dir,
            normalized_sources_dir=normalized_sources_dir,
            top_k=max(1, min(_env_int("SITESHAHA_TOP_K", 5), 12)),
            max_context_chars=max(
                1000, min(_env_int("SITESHAHA_MAX_CONTEXT_CHARS", 9000), 24000)
            ),
            llm_mode=mode,
            llm_base_url=llm_base_url,
            llm_model=os.getenv(
                "SITESHAHA_LLM_MODEL", "deepseek-chat"
            ).strip(),
            llm_api_key=llm_api_key,
            llm_timeout_seconds=max(
                10, min(_env_int("SITESHAHA_LLM_TIMEOUT_SECONDS", 90), 300)
            ),
            vision_model=os.getenv("SITESHAHA_VISION_MODEL", "").strip(),
            vision_base_url=vision_base_url,
            vision_api_key=vision_api_key,
            vision_api_style=vision_api_style,
            asr_base_url=asr_base_url,
            asr_api_key=os.getenv("SITESHAHA_ASR_API_KEY", "").strip(),
            asr_model=os.getenv("SITESHAHA_ASR_MODEL", "").strip(),
            asr_endpoint_path=asr_endpoint_path,
            asr_api_style=os.getenv("SITESHAHA_ASR_API_STYLE", "chat").strip().lower()
            if os.getenv("SITESHAHA_ASR_API_STYLE", "chat").strip().lower()
            in {"chat", "responses"}
            else "chat",
            asr_timeout_seconds=max(
                10, min(_env_int("SITESHAHA_ASR_TIMEOUT_SECONDS", 60), 300)
            ),
            max_audio_bytes=max(
                256 * 1024,
                min(_env_int("SITESHAHA_MAX_AUDIO_BYTES", 4 * 1024 * 1024), 20 * 1024 * 1024),
            ),
            llm_api_style=llm_api_style,
            max_image_bytes=max(1024 * 1024, min(_env_int("SITESHAHA_MAX_IMAGE_BYTES", 8 * 1024 * 1024), 20 * 1024 * 1024)),
            rate_limit_per_minute=max(
                0, min(_env_int("SITESHAHA_RATE_LIMIT_PER_MINUTE", 60), 600)
            ),
            max_concurrent_requests=max(
                1, min(_env_int("SITESHAHA_MAX_CONCURRENT_REQUESTS", 4), 32)
            ),
            request_timeout_seconds=max(
                5, min(_env_int("SITESHAHA_REQUEST_TIMEOUT_SECONDS", 30), 120)
            ),
            access_code=os.getenv("SITESHAHA_ACCESS_CODE", "").strip(),
            trust_proxy_headers=_env_bool(
                "SITESHAHA_TRUST_PROXY_HEADERS", False
            ),
        )

    @property
    def model_configured(self) -> bool:
        return self.llm_mode != "off" and bool(self.llm_base_url)

    @property
    def vision_configured(self) -> bool:
        return (
            self.llm_mode != "off"
            and bool(self.vision_model)
            and bool(self.vision_base_url)
        )

    @property
    def asr_configured(self) -> bool:
        """服务端语音识别（ASR）是否可用。未配置时前端降级到浏览器识别。"""
        return bool(self.asr_model) and bool(self.asr_base_url)

    @property
    def asr_endpoint(self) -> str:
        """OpenAI 兼容的语音转写端点。"""
        if not self.asr_base_url:
            return ""
        return self.asr_base_url + self.asr_endpoint_path
