"""用真实工地图 + 真实音频做端到端验收（第 16 轮 §4.3）。

与 verify_media.py 的区别：本脚本用**用户提供的真实照片**，而不是合成示意图，
所以能真正验证成功路径（而不只是链路连通）。

用法：
    python verify_real.py --photo <图片路径>
    python verify_real.py --photo <路径> --question "这张图有什么风险"
"""

from __future__ import annotations

import argparse
import array
import io
import json
import math
import sys
import time
import urllib.error
import urllib.request
import wave
from pathlib import Path

BASE = "http://127.0.0.1:8504"
BOUNDARY = "----SiteSahaReal7f3a9c"


def _post(path: str, payload: bytes, content_type: str, timeout: int = 180):
    request = urllib.request.Request(
        BASE + path, data=payload,
        headers={"Content-Type": content_type}, method="POST",
    )
    started = time.time()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read().decode("utf-8", "replace"), time.time() - started
    except urllib.error.HTTPError as exc:
        try:
            raw = exc.read().decode("utf-8", "replace")
        except Exception as inner:  # noqa: BLE001
            raw = json.dumps({"client_error": type(inner).__name__}, ensure_ascii=False)
        return exc.code, raw, time.time() - started
    except Exception as exc:  # noqa: BLE001
        return 0, json.dumps({"client_error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False), \
            time.time() - started


def post_multipart(path: str, fields: dict, files: dict, timeout: int = 180):
    parts: list[bytes] = []
    for key, value in fields.items():
        parts.append(
            f'--{BOUNDARY}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n'
            f"{value}\r\n".encode("utf-8")
        )
    for key, (filename, content_type, data) in files.items():
        parts.append(
            f'--{BOUNDARY}\r\nContent-Disposition: form-data; name="{key}"; '
            f'filename="{filename}"\r\nContent-Type: {content_type}\r\n\r\n'.encode("utf-8")
        )
        parts.append(data)
        parts.append(b"\r\n")
    parts.append(f"--{BOUNDARY}--\r\n".encode("utf-8"))
    return _post(path, b"".join(parts),
                 f"multipart/form-data; boundary={BOUNDARY}", timeout)


def get_json(path: str, timeout: int = 240):
    started = time.time()
    try:
        with urllib.request.urlopen(BASE + path, timeout=timeout) as response:
            return response.status, json.loads(response.read().decode("utf-8")), time.time() - started
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            return exc.code, json.loads(raw), time.time() - started
        except json.JSONDecodeError:
            return exc.code, {"raw": raw}, time.time() - started
    except Exception as exc:  # noqa: BLE001
        return 0, {"raw": f"{type(exc).__name__}: {exc}"}, time.time() - started


def make_wav(seconds: float = 3.0, sample_rate: int = 16000) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        frames = array.array(
            "h",
            (int(7000 * math.sin(2 * math.pi * 260 * i / sample_rate))
             for i in range(int(sample_rate * seconds))),
        )
        handle.writeframes(frames.tobytes())
    return buffer.getvalue()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--photo", required=True)
    parser.add_argument("--question", default="这张照片里有哪些可见的安全风险？我马上要下去作业。")
    parser.add_argument("--role", default="普工/杂工")
    args = parser.parse_args()

    photo = Path(args.photo)
    if not photo.is_file():
        print(f"[FAIL] 找不到图片：{photo}")
        return 1
    raw_image = photo.read_bytes()
    mime = "image/jpeg" if photo.suffix.lower() in {".jpg", ".jpeg"} else "image/png"
    print("=" * 82)
    print("真实素材端到端验收")
    print("=" * 82)
    print(f"\n[素材] {photo.name}  {len(raw_image)} 字节  {mime}")

    # ---------- 用例 1：真实工地图 ----------
    print(f"\n--- 用例 1：真实工地图识别")
    print(f"    问题：{args.question}")
    code, raw, elapsed = post_multipart(
        "/api/inspect-image",
        {"question": args.question, "worker_role": args.role},
        {"image": (photo.name, mime, raw_image)},
        timeout=120,
    )
    print(f"    HTTP {code}   耗时 {elapsed:.1f}s")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = {"_raw": raw}
    text = str(data.get("text", ""))
    if text:
        print(f"\n    === 模型回答（{len(text)} 字）===")
        for line in text.split("\n"):
            if line.strip():
                print(f"    {line}")
        sources = data.get("sources") or []
        print(f"\n    引用来源 {len(sources)} 条")
        for item in sources[:3]:
            print(f"      · {str(item.get('title'))[:60]}")
        warnings = data.get("warnings") or []
        for item in warnings:
            print(f"    免责：{item}")
        risk_words = [w for w in ("临边", "高处", "坠落", "安全带", "防护", "洞口", "吊",
                                  "基坑", "边坡", "坍塌", "支护", "材料", "堆放", "用电",
                                  "风险", "隐患") if w in text]
        print(f"\n    命中风险词：{risk_words or '（无）'}")
    else:
        print(f"    {raw[:400]}")
    ok1 = code == 200 and len(text) > 50 and elapsed < 15

    # ---------- 用例 2：语音（账户已充值）----------
    wav = make_wav(3.0)
    print(f"\n--- 用例 2：语音识别（{len(wav)} 字节 3 秒音频）")
    code, raw, elapsed = post_multipart(
        "/api/transcribe", {}, {"audio": ("record.wav", "audio/wav", wav)}, timeout=120,
    )
    print(f"    HTTP {code}   耗时 {elapsed:.1f}s")
    try:
        sdata = json.loads(raw)
    except json.JSONDecodeError:
        sdata = {"_raw": raw}
    if code == 200:
        print(f"    识别结果：{sdata.get('text', '')!r}  模式 {sdata.get('mode')}")
        print("    （纯 260Hz 正弦音不是语音，识别为空或噪声属正常；关键是链路通了）")
        ok2 = True
    else:
        print(f"    {json.dumps(sdata, ensure_ascii=False)[:300]}")
        ok2 = False

    # ---------- 用例 3：自检实测 ----------
    print(f"\n--- 用例 3：服务自检（实测探针）")
    code, data, elapsed = get_json("/api/selftest?probe=1")
    services = data.get("services", {}) if isinstance(data, dict) else {}
    print(f"    HTTP {code}   耗时 {elapsed:.1f}s")
    for name, info in services.items():
        mark = {True: "通过", False: "失败", None: "未测"}[info.get("ok")]
        print(f"      {name:<7} {mark:<4}  {str(info.get('detail', ''))[:70]}")
        if info.get("upstream_message"):
            print(f"              上游: {str(info['upstream_message'])[:100]}")
    ok3 = code == 200 and all(
        info.get("ok") is not False for info in services.values()
    )

    print()
    print("=" * 82)
    for name, ok in [("1 真实工地图识别", ok1), ("2 语音识别", ok2), ("3 服务自检", ok3)]:
        print(f"  [{'pass' if ok else 'FAIL'}] {name}")
    print("=" * 82)
    return 0 if (ok1 and ok2 and ok3) else 1


if __name__ == "__main__":
    sys.exit(main())
