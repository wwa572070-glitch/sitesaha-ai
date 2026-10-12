from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


# 被外部环境变量覆盖、因而 .env 未生效的键（诊断用，不记录密钥值）
ENV_OVERRIDES: dict[str, str] = {}

# 与 AI 能力直接相关的键：这些被覆盖时最危险
AI_KEYS = (
    "SITESHAHA_LLM_MODE",
    "SITESHAHA_LLM_BASE_URL",
    "SITESHAHA_LLM_API_KEY",
    "SITESHAHA_VISION_BASE_URL",
    "SITESHAHA_VISION_API_KEY",
    "SITESHAHA_VISION_MODEL",
)


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
            # 记录「环境变量已存在、因此 .env 没生效」的键。
            # 这类静默覆盖会让 AI 能力无声关闭，必须能查出来。
            if name in os.environ and os.environ[name] != value:
                ENV_OVERRIDES[name] = os.environ[name]
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
    max_context_chars: int = 4200
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
                1000, min(_env_int("SITESHAHA_MAX_CONTEXT_CHARS", 4200), 24000)
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

    def unavailable_reason(self, feature: str) -> str:
        """说明某项能力为什么不可用（用于 /healthz 与启动日志）。"""
        if feature == "model" and self.model_configured:
            return ""
        if feature == "vision" and self.vision_configured:
            return ""
        if feature == "asr" and self.asr_configured:
            return ""

        if self.llm_mode == "off":
            overridden = "SITESHAHA_LLM_MODE" in ENV_OVERRIDES
            if overridden:
                return ("模型已关闭，且这个值是**外部环境变量**覆盖 .env 得到的"
                        "（SITESHAHA_LLM_MODE=" + str(ENV_OVERRIDES.get("SITESHAHA_LLM_MODE"))
                        + "）。请清除该环境变量后重启。")
            return "模型已关闭（SITESHAHA_LLM_MODE=off）。"

        base = {"model": self.llm_base_url,
                "vision": self.vision_base_url or self.llm_base_url}.get(feature, "")
        if not base:
            return f"{feature} 未配置服务地址。"
        if feature == "vision" and not self.vision_model:
            return "未配置视觉模型名称（SITESHAHA_VISION_MODEL）。"
        return f"{feature} 配置不完整，请检查 .env 或部署环境变量。"

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


def _warn_about_disabled_ai(config) -> None:
    """AI 能力未就绪时打印醒目警告。

    为什么需要：这个失败以前是无声的 —— 页面只显示「未连接模型」，
    看不出是密钥缺失、被环境变量覆盖，还是模型名写错。
    本轮排查时就因为环境变量静默覆盖 .env，白找了一圈。
    """
    if config.llm_mode != "off" and config.model_configured and config.vision_configured:
        return

    print("!" * 66)
    print("警告：AI 能力未全部就绪")
    for feature in ("model", "vision", "asr"):
        reason = config.unavailable_reason(feature)
        if reason:
            print("  · " + feature + ": " + reason)
    if ENV_OVERRIDES:
        print("  以下外部环境变量覆盖了 .env 的同名配置：")
        for key in AI_KEYS:
            if key in ENV_OVERRIDES:
                shown = "***" if "KEY" in key else ENV_OVERRIDES[key]
                print("    - " + key + " = " + shown)
        print("  清除这些环境变量后重启，.env 才会生效。")
    print("!" * 66)
