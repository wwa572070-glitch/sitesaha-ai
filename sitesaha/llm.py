from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from threading import Lock

from .config import AppConfig
from .models import SearchResult
from .text import truncate


@dataclass(slots=True)
class ModelStatus:
    available: bool
    detail: str
    model: str


class ProviderError(RuntimeError):
    """服务商侧的可分类错误。

    带上稳定的 error_code 与面向用户的中文说明，让 HTTP 层直接映射成
    可操作的响应，而不是把 ``RuntimeError: ... HTTP 402: {"code":30001,...}``
    这种一长串英文原文丢给界面。

    为什么需要：第 16 轮实测发现硅基流动余额不足时返回 402，原样冒到前端
    就是 500 + 英文 JSON，用户完全不知道发生了什么、下一步做什么。
    """

    def __init__(self, code: str, message: str, *, http_status: int | None = None,
                 hint: str = "", retryable: bool = False, raw: str = "") -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status
        self.hint = hint
        self.retryable = retryable
        self.raw = raw

    def as_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {"error": self.message, "error_code": self.code}
        if self.hint:
            payload["hint"] = self.hint
        if self.http_status is not None:
            payload["upstream_status"] = self.http_status
        if self.raw:
            # 回显服务商原始信息（截断），便于管理员定位；不含密钥
            payload["upstream_message"] = self.raw[:300]
        return payload


# 上游状态码 → (错误码, 用户可读说明, 下一步提示, 是否可重试)
_UPSTREAM_MAP: dict[int, tuple[str, str, str, bool]] = {
    401: ("provider_unauthorized", "模型服务的密钥无效或已过期。",
          "请联系管理员核对 API Key（注意硅基流动必须用 api.siliconflow.cn，旧的 .com 域名会把正确密钥判为无效）。", False),
    402: ("provider_insufficient_balance", "模型服务账户余额不足。",
          "请为该账户充值或完成实名认证；在此之前语音/图像识别不可用，可先用文字提问。", False),
    403: ("provider_forbidden", "模型服务拒绝了本次请求（权限不足）。",
          "请确认该账号已开通对应模型的使用权限。", False),
    404: ("provider_model_missing", "模型服务找不到这个模型。",
          "请核对模型名；免费版用原名，收费版才有 Pro/ 前缀。", False),
    413: ("provider_payload_too_large", "提交的内容超过模型服务的体积上限。",
          "请换更小的图片，或把录音缩短到 60 秒以内。", False),
    429: ("provider_rate_limited", "模型服务当前请求过多，被限流了。",
          "稍等几秒再试；免费版模型的调用频率是固定上限。", True),
    500: ("provider_error", "模型服务内部错误。", "稍后重试；持续失败请联系管理员。", True),
    502: ("provider_error", "模型服务网关错误。", "稍后重试。", True),
    503: ("provider_error", "模型服务暂时不可用。", "稍后重试。", True),
    504: ("provider_error", "模型服务响应超时。", "稍后重试，或换更小的图片/更短的录音。", True),
}


def classify_upstream(status: int, detail: str) -> ProviderError:
    """把上游 HTTP 状态码翻译成 ProviderError。"""
    code, message, hint, retryable = _UPSTREAM_MAP.get(
        status,
        ("provider_error", f"模型服务返回 HTTP {status}。", "稍后重试；持续失败请联系管理员。", status >= 500),
    )
    return ProviderError(code, message, http_status=status, hint=hint,
                         retryable=retryable, raw=detail)


def with_retry(operation, *, attempts: int = 4, base_delay: float = 2.0,
               max_delay: float = 12.0):
    """对可重试的 ProviderError 做指数退避。

    依据第 16 轮 §4.2，并在线上实测后调整：
    免费模型（glm-4-flash）的限流恢复比较慢，原来 0.8s→2s 的重试窗口太短，
    实测会出现「重试完仍然 429 → 回退成检索摘要」。
    现在改成 2s → 4s → 8s（封顶 12s），共 4 次尝试。
    """
    last: ProviderError | None = None
    for index in range(attempts):
        try:
            return operation()
        except ProviderError as exc:
            last = exc
            if not exc.retryable or index == attempts - 1:
                raise
            delay = min(max_delay, base_delay * (2 ** index))
            time.sleep(delay)
    if last is not None:
        raise last
    raise RuntimeError("重试逻辑异常：没有任何尝试被执行")


class LocalModelClient:
    """OpenAI-compatible model client with optional Responses API support."""

    def __init__(self, config: AppConfig):
        self.config = config
        self._status: ModelStatus | None = None
        self._status_checked_at = 0.0
        self._lock = Lock()

    @staticmethod
    def _headers(api_key: str = "") -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    def status(self, *, refresh: bool = False) -> ModelStatus:
        if not self.config.model_configured:
            return ModelStatus(False, "未配置模型服务地址，当前使用检索摘要", self.config.llm_model)
        with self._lock:
            now = time.monotonic()
            if (
                self._status is not None
                and not refresh
                and now - self._status_checked_at < 60
            ):
                return self._status
            request = urllib.request.Request(
                f"{self.config.llm_base_url}/models",
                headers=self._headers(self.config.llm_api_key),
                method="GET",
            )
            try:
                with urllib.request.urlopen(request, timeout=4) as response:
                    response.read(1024)
                self._status = ModelStatus(True, "模型服务已连接", self.config.llm_model)
            except urllib.error.HTTPError as exc:
                self._status = ModelStatus(
                    False, f"模型服务返回 HTTP {exc.code}", self.config.llm_model
                )
            except (OSError, urllib.error.URLError) as exc:
                self._status = ModelStatus(
                    False, f"模型服务未连接：{type(exc).__name__}", self.config.llm_model
                )
            self._status_checked_at = now
            return self._status

    def _post(
        self,
        path: str,
        payload: dict,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: int | None = None,
    ) -> dict:
        request = urllib.request.Request(
            f"{base_url or self.config.llm_base_url}{path}",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers=self._headers(
                self.config.llm_api_key if api_key is None else api_key
            ),
            method="POST",
        )
        try:
            with urllib.request.urlopen(
                request, timeout=timeout or self.config.llm_timeout_seconds
            ) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read(500).decode("utf-8", errors="replace").strip()
            raise classify_upstream(exc.code, detail) from exc
        except (OSError, urllib.error.URLError) as exc:
            raise ProviderError(
                "provider_unreachable", "连接模型服务失败。",
                hint="检查网络后重试。", raw=type(exc).__name__,
            ) from exc

    @staticmethod
    def _extract_response_text(result: dict) -> str:
        if isinstance(result.get("output_text"), str):
            return result["output_text"]
        parts: list[str] = []
        for item in result.get("output", []) or []:
            for content in item.get("content", []) or []:
                text = content.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(parts).strip()

    @staticmethod
    def _extract_chat_text(result: dict) -> str:
        content = result["choices"][0]["message"]["content"]
        if isinstance(content, list):
            return "\n".join(str(x.get("text", "")) for x in content if isinstance(x, dict)).strip()
        return str(content).strip()

    def _generate_responses(self, system: str, user: str, model: str) -> str:
        payload = {
            "model": model,
            "input": [
                {"role": "system", "content": [{"type": "input_text", "text": system}]},
                {"role": "user", "content": [{"type": "input_text", "text": user}]},
            ],
            "max_output_tokens": 650,
        }
        result = self._post("/responses", payload)
        text = self._extract_response_text(result)
        if not text:
            raise RuntimeError("Responses API 返回为空")
        return truncate(text, 5000)

    def _generate_chat(self, system: str, user: str, model: str) -> str:
        payload = {
            "model": model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": 0.1,
            "max_tokens": 650,
        }
        result = self._post("/chat/completions", payload)
        try:
            text = self._extract_chat_text(result)
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("聊天模型返回格式不正确") from exc
        return truncate(text, 5000)

    def inspect_image(self, image_bytes: bytes, mime_type: str, question: str, sources: list[SearchResult], *, worker_role: str = "") -> str:
        if not self.config.vision_configured:
            raise ProviderError(
                "vision_not_configured",
                "当前未配置图像识别服务，照片检查暂不可用。",
                hint="改用文字提问；文字问答与知识库检索不受影响。",
            )
        model = self.config.vision_model
        import base64
        encoded = base64.b64encode(image_bytes).decode("ascii")
        context_parts = []
        used = 0
        for i, source in enumerate(sources, 1):
            item = f"[{i}] {source.title} / {source.heading}\n{source.content}"
            if used + len(item) > self.config.max_context_chars:
                break
            context_parts.append(item)
            used += len(item)
        system = """你是筑安智培的施工现场安全照片辅助检查员，服务对象是没受过专业训练的新工人。
你的任务是**只看这张照片里看得见的东西**，帮他判断"我现在下去干活安不安全、先做什么"。

【必须遵守】
1. 第一句先判断作业类型与阶段（例如：深基坑开挖、主体结构、脚手架搭设、装饰装修），
   再谈风险。不要跳过这一步直接列举。
2. **严禁条件式假设**。不许出现"如果有夜间作业""如果有高空作业""如果有临时用电"
   "需要确保消防设施充足"这类句子 —— 照片里没有的东西，一个字都不要写。
   这类句式是最常见的错误，务必避免。
3. 每条风险必须指出**在照片的哪个位置**（如"画面中下部""左上方"），
   让用户能对着照片核对。指不出位置的，就不要提。
4. 看不清或信息不足时直接说"这一处看不清，需要现场确认"。**不要用通用常识凑数**。
   宁可只给 3 条站得住的风险，也不要给 10 条泛泛而谈。
5. 每条风险后面跟"立即动作"，要具体可执行（停工、撤离、报给谁、查哪个部位），
   不要写"注意安全""加强管理"这类无动作价值的空话。
6. 高风险场景（高处、临电、吊装、机械、动火、基坑、脚手架、有限空间）优先建议
   停止/隔离危险区域，按现场交底处理。

【输出格式】
严格按下面四行结构输出，**没有内容的章节整行省略**（不要打印标题后再写"无"）：
- **作业类型**：一句话
- **可见风险**：每条一行，格式为「位置 + 现象 + 立即动作」
- **看不清的**：只在确有必要现场确认时输出这一行
- **依据**：引用参考资料时标注编号如 [1]。没有任何一条能对应上参考资料时，
  **整行省略**，不要写"无依据""不适用"之类的话，也不要编造标准号、条款号、数值或处罚。

不要输出"高风险场景"这类额外章节 —— 高风险提示要融进对应的那条风险里。

结尾必须保留这句：本页仅辅助识别肉眼可见的风险，不替代现场安全员检查，也不证明现场完全合规。
"""
        user_text = f"工种：{worker_role or '未选择'}\n用户问题：{question or '请检查这张施工现场照片中的明显安全风险。'}\n\n参考资料：\n{chr(10).join(context_parts) or '无'}"
        if self.config.vision_api_style == "responses":
            payload = {
                "model": model,
                "input": [
                    {"role": "system", "content": [{"type": "input_text", "text": system}]},
                    {"role": "user", "content": [
                        {"type": "input_text", "text": user_text},
                        {"type": "input_image", "image_url": f"data:{mime_type};base64,{encoded}"},
                    ]},
                ],
                "max_output_tokens": 700,
            }
            result = self._post(
                "/responses",
                payload,
                base_url=self.config.vision_base_url,
                api_key=self.config.vision_api_key,
            )
            text = self._extract_response_text(result)
        else:
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": [
                        {"type": "text", "text": user_text},
                        {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{encoded}"}},
                    ]},
                ],
                "temperature": 0.1,
                "max_tokens": 700,
            }
            result = self._post(
                "/chat/completions",
                payload,
                base_url=self.config.vision_base_url,
                api_key=self.config.vision_api_key,
            )
            text = self._extract_chat_text(result)
        if not text:
            raise RuntimeError("多模态模型返回为空")
        return truncate(text, 6000)

    def transcribe_audio(
        self, audio_bytes: bytes, *, mime_type: str = "audio/webm", filename: str = "speech.webm"
    ) -> str:
        """OpenAI 兼容的语音转写接口（multipart/form-data）。

        未配置 ASR 时抛出明确的未配置错误，由调用方转换成可操作的提示。
        """
        if not self.config.asr_configured:
            raise ProviderError(
                "asr_not_configured",
                "当前未配置语音识别服务，请改用键盘输入。",
                hint="管理员配置 SITESHAHA_ASR_BASE_URL / SITESHAHA_ASR_MODEL 后即可使用。",
            )
        if not audio_bytes:
            raise ProviderError("audio_empty", "录音内容为空，请重新录制。", hint="按住录音按钮，说完再松开。")

        boundary = "----SiteSahaASRBoundary7f3a9c"
        parts: list[bytes] = []

        def add_field(name: str, value: str) -> None:
            parts.append(
                (
                    f"--{boundary}\r\n"
                    f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
                    f"{value}\r\n"
                ).encode("utf-8")
            )

        parts.append(
            (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
                f"Content-Type: {mime_type}\r\n\r\n"
            ).encode("utf-8")
        )
        parts.append(audio_bytes)
        parts.append(b"\r\n")
        add_field("model", self.config.asr_model)
        add_field("language", "zh")
        add_field("response_format", "json")
        parts.append(f"--{boundary}--\r\n".encode("utf-8"))
        body = b"".join(parts)

        headers = {
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Accept": "application/json",
        }
        if self.config.asr_api_key:
            headers["Authorization"] = f"Bearer {self.config.asr_api_key}"

        request = urllib.request.Request(
            self.config.asr_endpoint, data=body, headers=headers, method="POST"
        )
        try:
            with urllib.request.urlopen(
                request, timeout=self.config.asr_timeout_seconds
            ) as response:
                result = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read(500).decode("utf-8", errors="replace").strip()
            raise classify_upstream(exc.code, detail) from exc
        except (OSError, urllib.error.URLError) as exc:
            raise ProviderError("provider_unreachable", "连接模型服务失败。", hint="检查网络后重试；也可先用文字提问。", raw=type(exc).__name__) from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError("语音识别服务返回格式不正确") from exc

        text = ""
        if isinstance(result, dict):
            candidate = result.get("text")
            if isinstance(candidate, str):
                text = candidate
            else:
                segments = result.get("segments")
                if isinstance(segments, list):
                    text = "".join(
                        str(item.get("text", ""))
                        for item in segments
                        if isinstance(item, dict)
                    )
        text = truncate(text.strip(), 800)
        if not text:
            raise ProviderError("audio_no_text", "没有识别出文字。", hint="靠近麦克风、在安静处再说一次；也可以直接打字提问。")
        return text

    def generate(self, question: str, sources: list[SearchResult], *, mode: str = "普通咨询", worker_role: str = "", training_context: str = "") -> str:
        if self.config.llm_mode == "off":
            raise RuntimeError("生成模型已关闭")
        if not self.config.model_configured:
            raise RuntimeError("未配置模型服务地址")

        context_parts: list[str] = []
        used_chars = 0
        for index, source in enumerate(sources, start=1):
            heading = f" / {source.heading}" if source.heading else ""
            item = f"[{index}] {source.title}{heading}\n来源：{source.source} {source.version}\n{source.content}"
            if used_chars + len(item) > self.config.max_context_chars:
                break
            context_parts.append(item)
            used_chars += len(item)

        system_prompt = f"""
你是“筑安智培”，服务对象是建筑施工现场一线新员工。当前回答模式：{mode}。当前工种：{worker_role or "未选择"}。培训上下文：{training_context or "无"}。
你的目标不是背规范，而是像一位耐心、可靠的现场安全师傅一样帮助新人。先理解新人真正想问什么，再把可靠安全要求转成新人听得懂、现场能执行的动作。语气自然、友善，不训斥、不居高临下。

沟通原则：如果用户的问题很短或口语化，先用一句话确认你理解的意思；能直接回答就不要反复追问。只有缺少关键信息且可能影响安全判断时才追问，并且一次最多问2个最关键的问题。

严格规则：
1. 只使用参考资料中的事实，不编造条款号、数值、处罚、设备参数或项目制度。
2. 国家/行业标准、项目制度、培训摘要发生冲突时，明确提示以适用且最新的项目制度和现场安全交底为准；不要自行裁决未给出的具体要求。
3. 回答先给结论，再给“马上怎么做”，再给“不要做什么”，最后给依据编号。[1][2]。可以使用“你可以这样做”“先别急”“如果你不确定”等自然表达。
4. 操作问题优先使用步骤化语言；新人不懂术语时，用通俗解释并保留必要专业名称。
5. 只要涉及高处、吊装、临电、基坑、脚手架、动火、受限空间、机械异常等高风险作业，明确“未经交底/授权不要擅自操作”。
6. 遇到触电、火灾、坍塌、坠落、重伤等疑似紧急情况：先停止危险行为、撤离/隔离危险区域、呼救并按项目应急流程处置；不要指导未受训人员进行危险施救。
7. 资料不足时明确说“当前知识库依据不足”，不要猜。
8. 不要用论文腔；单次回答尽量控制在 150~350 字，必要时更短。
9. 不要把新人叫“作业人员”“施工人员”等生硬称呼，优先用“你”。
10. 不要为了显得专业而堆术语；出现专业词时顺手用一句白话解释。
11. 如果用户只是想确认“能不能做”，第一句话直接回答能否继续；若不能确认，就明确说“先别做”。
12. 回答末尾可给一个很短的下一步提示，不要每次机械添加。
""".strip()
        user_prompt = f"问题：{question}\n工种：{worker_role or '未选择'}\n培训上下文：{training_context or '无'}\n\n参考资料：\n{chr(10).join(context_parts) or '无'}\n\n请直接用中文回答。"
        if self.config.llm_api_style == "responses":
            return self._generate_responses(system_prompt, user_prompt, self.config.llm_model)
        return self._generate_chat(system_prompt, user_prompt, self.config.llm_model)
