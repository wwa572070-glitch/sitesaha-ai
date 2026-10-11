"""给 webapp.py 接入拍照/语音可用性改造（第 16 轮 §4）。

做三件事：
  1. 模块级加两个探针生成函数（最小 PNG / 静音 WAV，手写字节，零依赖）
  2. 加 /api/selftest 路由
  3. 加 _handle_selftest 方法

用法：python patch_selftest.py [--dry-run]
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

APP = Path(__file__).resolve().parent.parent.parent
WEBAPP = APP / "webapp.py"

PROBE_FUNCS = '''def _probe_png() -> bytes:
    """生成一张 8x8 的合法 PNG，用作视觉服务连通性探针。

    手写 PNG 结构，不读磁盘、不依赖 Pillow —— 保证离线与零依赖。
    """
    import struct
    import zlib

    width = height = 8
    row = b"\\x00" + b"\\x80\\x90\\xa0" * width
    raw = row * height

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (b"\\x89PNG\\r\\n\\x1a\\n" + chunk(b"IHDR", header)
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def _probe_wav(seconds: float = 1.0, sample_rate: int = 16000) -> bytes:
    """生成一小段静音 WAV，用作语音服务连通性探针。"""
    import struct

    data = b"\\x00\\x00" * int(seconds * sample_rate)
    header = (b"RIFF" + struct.pack("<I", 36 + len(data)) + b"WAVE"
              + b"fmt " + struct.pack("<IHHIIHH", 16, 1, 1, sample_rate,
                                      sample_rate * 2, 2, 16)
              + b"data" + struct.pack("<I", len(data)))
    return header + data


'''

SELFTEST_METHOD = '''    def _handle_selftest(self) -> None:
        """POST /api/selftest —— 三个模型服务的配置与连通性自检。

        为什么需要：视觉与语音"配了但用不了"的情况（余额不足、密钥无效、
        模型名不对）只有在真正调用时才会暴露。这个接口把三态与**服务商原始
        错误**一次性回显给管理员，前端据此在点击前就给出明确状态。

        body: {"probe": true|false}  probe=true 时对每个已配置服务发一次真实请求。
        """
        import json as _json

        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
            body = self.rfile.read(length) if length > 0 else b"{}"
            payload = _json.loads(body.decode("utf-8") or "{}")
            if not isinstance(payload, dict):
                payload = {}
        except (ValueError, _json.JSONDecodeError):
            payload = {}

        want_probe = bool(payload.get("probe"))
        config = self.services.config
        model = getattr(self.services.engine, "model", None)
        report: dict[str, Any] = {
            "schema": "sitesaha-selftest/v1",
            "probe": want_probe,
            "services": {},
        }

        def record(name: str, configured: bool, detail: str) -> dict[str, Any]:
            entry = {"configured": configured, "ok": None, "detail": detail}
            report["services"][name] = entry
            return entry

        # ---- 生成模型 ----
        llm = record("llm", bool(config.model_configured),
                     f"模式 {config.llm_mode} · 模型 {config.llm_model or '未设置'}")
        # ---- 视觉 ----
        vision = record("vision", bool(config.vision_configured),
                        f"模型 {config.vision_model or '未设置'} · 接口风格 {config.vision_api_style}")
        # ---- 语音 ----
        asr = record("asr", bool(config.asr_configured),
                     f"模型 {config.asr_model or '未设置'} · 端点 {config.asr_endpoint_path}")

        if want_probe and model is not None:
            if llm["configured"]:
                try:
                    model.generate("自检：请回复两个字以内的确认。", [], mode="自检")
                    llm["ok"] = True
                    llm["detail"] += " · 实测通过"
                except ProviderError as exc:
                    llm["ok"] = False
                    llm["error_code"] = exc.code
                    llm["detail"] = exc.message
                    if exc.hint:
                        llm["hint"] = exc.hint
                    if exc.raw:
                        llm["upstream_message"] = exc.raw[:300]
                except Exception as exc:  # noqa: BLE001
                    llm["ok"] = False
                    llm["detail"] = f"实测异常：{type(exc).__name__}"

            if vision["configured"]:
                try:
                    model.inspect_image(_probe_png(), "image/png", "自检", [])
                    vision["ok"] = True
                    vision["detail"] += " · 实测通过"
                except ProviderError as exc:
                    vision["ok"] = False
                    vision["error_code"] = exc.code
                    vision["detail"] = exc.message
                    if exc.hint:
                        vision["hint"] = exc.hint
                    if exc.raw:
                        vision["upstream_message"] = exc.raw[:300]
                except Exception as exc:  # noqa: BLE001
                    vision["ok"] = False
                    vision["detail"] = f"实测异常：{type(exc).__name__}"

            if asr["configured"]:
                try:
                    model.transcribe_audio(_probe_wav(), mime_type="audio/wav",
                                           filename="selftest.wav")
                    asr["ok"] = True
                    asr["detail"] += " · 实测通过"
                except ProviderError as exc:
                    # 静音音频识别不出文字属正常，说明服务其实是通的
                    if exc.code == "audio_no_text":
                        asr["ok"] = True
                        asr["detail"] += " · 实测连通（静音探针无文字属正常）"
                    else:
                        asr["ok"] = False
                        asr["error_code"] = exc.code
                        asr["detail"] = exc.message
                        if exc.hint:
                            asr["hint"] = exc.hint
                        if exc.raw:
                            asr["upstream_message"] = exc.raw[:300]
                except Exception as exc:  # noqa: BLE001
                    asr["ok"] = False
                    asr["detail"] = f"实测异常：{type(exc).__name__}"

        self._write_json(report)

'''

ROUTE_OLD = '''        if path == "/healthz":'''
ROUTE_NEW = '''        if path == "/api/selftest":

            self._handle_selftest()

            return

        if path == "/healthz":'''

METHOD_ANCHOR = "    def _write_provider_error(self, exc: ProviderError) -> None:"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    text = WEBAPP.read_text(encoding="utf-8")
    changed = 0

    if "def _probe_png()" not in text:
        anchor = "def record_timing(path: str, started: float, status_code: int) -> None:"
        if anchor not in text:
            print("[FAIL] 找不到 record_timing 锚点")
            return 1
        text = text.replace(anchor, PROBE_FUNCS + anchor, 1)
        changed += 1
        print("[ok] 加入探针生成函数")
    else:
        print("[跳过] 探针函数已存在")

    if "/api/selftest" not in text:
        if ROUTE_OLD not in text:
            print("[FAIL] 找不到 /healthz 路由锚点")
            return 1
        text = text.replace(ROUTE_OLD, ROUTE_NEW, 1)
        changed += 1
        print("[ok] 加入 /api/selftest 路由")
    else:
        print("[跳过] 路由已存在")

    if "_handle_selftest" not in text:
        if METHOD_ANCHOR not in text:
            print("[FAIL] 找不到 _write_provider_error 锚点")
            return 1
        text = text.replace(METHOD_ANCHOR, SELFTEST_METHOD + METHOD_ANCHOR, 1)
        changed += 1
        print("[ok] 加入 _handle_selftest 方法")
    else:
        print("[跳过] 方法已存在")

    try:
        ast.parse(text)
    except SyntaxError as exc:
        print(f"[FAIL] 语法错误：{exc}")
        return 1
    print("[ok] 语法检查通过")

    if args.dry_run:
        print(f"（dry-run，未写入；共 {changed} 处改动）")
        return 0
    WEBAPP.write_text(text, encoding="utf-8")
    print(f"[ok] webapp.py 已更新（{changed} 处），{len(text)} 字符")
    return 0


if __name__ == "__main__":
    sys.exit(main())
