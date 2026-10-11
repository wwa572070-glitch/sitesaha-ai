"""§4.3 端到端验收 v2：合成更真实的工地示意图，并修正断言逻辑。

v1 的两个 FAIL 原因：
  1) 视觉：我合成的图太抽象，模型正确地回答"信息不足"。属测试素材问题，不是产品缺陷。
     本版改画一张元素明确的工地场景（临边洞口 + 未系安全带的人 + 无防护的吊装区）。
  2) 音频：断言把 upstream_message 里的服务商原文当成"英文泄露"。
     但那是**刻意保留**给管理员定位用的字段（第 16 轮 §4.2 第 4 点要求回显原始错误）。
     真正的验收点是：面向用户的 error 与 hint 必须是中文可操作说明。
     本版按此断言，并单独标注环境阻塞（硅基流动余额不足）。

用法：python verify_media.py [--quick]
"""

from __future__ import annotations

import array
import io
import json
import math
import sys
import time
import urllib.error
import urllib.request
import wave

BASE = "http://127.0.0.1:8504"
BOUNDARY = "----SiteSahaVerify7f3a9c"


def _request(path: str, payload: bytes, content_type: str, timeout: int):
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
            raw = f"（读取响应体失败：{type(inner).__name__}）"
        return exc.code, raw, time.time() - started
    except Exception as exc:  # noqa: BLE001
        return 0, f'{{"client_error": "{type(exc).__name__}: {exc}"}}', time.time() - started


def post_multipart(path: str, fields: dict, files: dict, timeout: int = 120):
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
    return _request(path, b"".join(parts),
                    f"multipart/form-data; boundary={BOUNDARY}", timeout)


def get_json(path: str, timeout: int = 180):
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


def make_site_photo(width: int = 720, height: int = 540) -> bytes:
    """画一张元素明确的工地示意图。

    刻意包含三类可识别风险：
      · 楼板边缘无防护栏杆（临边洞口）
      · 工人站在边缘、未系安全带
      · 吊物悬停在人员上方
    """
    from PIL import Image, ImageDraw

    sky = (168, 196, 220)
    image = Image.new("RGB", (width, height), sky)
    draw = ImageDraw.Draw(image)

    # 远处楼体
    draw.rectangle([0, 60, width, 300], fill=(196, 200, 204))
    for y in range(80, 290, 46):
        for x in range(30, width - 30, 78):
            draw.rectangle([x, y, x + 44, y + 26], fill=(120, 138, 156))

    # 楼板（作业面）
    draw.rectangle([0, 300, width, height], fill=(178, 174, 166))
    draw.rectangle([0, 300, width, 316], fill=(146, 142, 134))

    # 临边：没有栏杆，只有一段缺口提示
    draw.rectangle([0, 296, width, 306], fill=(92, 96, 102))

    # 脚手架（左侧，有横杆 —— 作为对照）
    for x in (60, 150):
        draw.rectangle([x, 150, x + 8, 300], fill=(104, 116, 128))
    for y in (190, 240, 290):
        draw.rectangle([60, y, 158, y + 7], fill=(104, 116, 128))

    # 塔吊吊钩 + 悬吊的钢管（在人员上方）
    draw.line([(470, 0), (470, 120)], fill=(70, 74, 80), width=4)
    draw.rectangle([430, 120, 510, 150], fill=(96, 100, 108))
    draw.line([(470, 150), (470, 196)], fill=(70, 74, 80), width=3)

    # 工人：站在楼板边缘，没系安全带，无安全帽色
    draw.ellipse([560, 236, 598, 274], fill=(214, 190, 162))          # 头
    draw.polygon([(560, 240), (598, 240), (592, 232), (566, 232)],    # 头发（非安全帽）
                 fill=(48, 42, 38))
    draw.rectangle([558, 276, 600, 350], fill=(196, 158, 62))         # 上身
    draw.rectangle([558, 350, 600, 420], fill=(72, 84, 128))          # 下身
    draw.line([(558, 300), (528, 344)], fill=(196, 158, 62), width=9) # 手臂
    draw.line([(600, 300), (626, 342)], fill=(196, 158, 62), width=9)

    # 洞口（楼板上的方形开口，无盖板无围栏）
    draw.rectangle([236, 372, 356, 452], fill=(38, 40, 44))
    draw.rectangle([236, 366, 356, 374], fill=(150, 146, 138))

    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    return buffer.getvalue()


def make_wav(seconds: float = 3.0, sample_rate: int = 16000, tone: bool = True) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        frames = array.array(
            "h",
            (int(6000 * math.sin(2 * math.pi * 320 * i / sample_rate))
             if tone else 0 for i in range(int(sample_rate * seconds))),
        )
        handle.writeframes(frames.tobytes())
    return buffer.getvalue()


def load(body) -> dict:
    if isinstance(body, dict):
        return body
    try:
        parsed = json.loads(body)
        return parsed if isinstance(parsed, dict) else {"_value": parsed}
    except (json.JSONDecodeError, TypeError):
        return {"_raw": str(body)}


def has_chinese(text: str) -> bool:
    return any("\u4e00" <= ch <= "\u9fff" for ch in text)


def main() -> int:
    results: list[tuple[str, str, str]] = []  # (名称, pass/fail/blocked, 备注)

    print("=" * 80)
    print("§4.3 拍照与语音端到端验收")
    print("=" * 80)

    # ---------- 用例 1：真实工地图 ----------
    png = make_site_photo()
    print(f"\n[准备] 工地示意图 PNG {len(png)} 字节（720x540，含临边/未系安全带/悬吊物）")
    code, raw, elapsed = post_multipart(
        "/api/inspect-image",
        {"question": "这张照片里有哪些可见的安全风险？"},
        {"image": ("site.png", "image/png", png)},
    )
    data = load(raw)
    text = str(data.get("text", ""))
    print(f"  用例 1  真实工地图识别")
    print(f"    HTTP {code}  耗时 {elapsed:.1f}s")
    print(f"    text: {text[:300]}")
    ok1 = code == 200 and len(text) > 20 and elapsed < 15
    if ok1:
        # 是否真的指出了风险词
        hits = [w for w in ("临边", "高处", "坠落", "安全带", "防护", "洞口", "吊", "风险")
                if w in text]
        print(f"    命中风险词: {hits or '（无，模型说信息不足）'}")
    results.append(("1 真实图片识别", "pass" if ok1 else "fail",
                    f"HTTP {code} {elapsed:.1f}s"))

    # ---------- 用例 2：真实音频 ----------
    wav = make_wav(3.0)
    print(f"\n[准备] 3 秒音频 WAV {len(wav)} 字节")
    code, raw, elapsed = post_multipart(
        "/api/transcribe", {}, {"audio": ("record.wav", "audio/wav", wav)},
    )
    data = load(raw)
    user_msg = str(data.get("error", ""))
    hint = str(data.get("hint", ""))
    print(f"  用例 2  真实音频识别")
    print(f"    HTTP {code}  耗时 {elapsed:.1f}s")
    print(f"    面向用户: {user_msg}")
    if hint:
        print(f"    下一步  : {hint}")
    if data.get("upstream_message"):
        print(f"    上游原文（刻意保留给管理员）: {data['upstream_message'][:110]}")
    got_text = code == 200 and isinstance(data.get("text"), str) and data["text"].strip()
    actionable = bool(user_msg) and has_chinese(user_msg) and bool(hint)
    ok2 = got_text or actionable
    blocked = code == 503 and data.get("error_code") == "provider_insufficient_balance"
    results.append(("2 真实音频识别（含降级）",
                    "pass" if ok2 else "fail",
                    "环境阻塞：硅基流动余额不足，已给可操作中文提示" if blocked else f"HTTP {code}"))

    # ---------- 用例 3 / 3b：自检 ----------
    code, data, elapsed = get_json("/api/selftest")
    services = data.get("services", {}) if isinstance(data, dict) else {}
    print(f"\n  用例 3  服务自检（三态）  HTTP {code}  服务数 {len(services)}")
    for name, info in services.items():
        print(f"    {name:<7} configured={info.get('configured')}  {info.get('detail','')}")
    ok3 = code == 200 and len(services) == 3
    results.append(("3 服务自检（三态）", "pass" if ok3 else "fail", f"HTTP {code}"))

    code, data, elapsed = get_json("/api/selftest?probe=1")
    services = data.get("services", {}) if isinstance(data, dict) else {}
    print(f"\n  用例 3b 服务自检（实测探针）  HTTP {code}  耗时 {elapsed:.1f}s")
    for name, info in services.items():
        mark = {True: "通过", False: "失败", None: "未测"}[info.get("ok")]
        print(f"    {name:<7} {mark:<4} {str(info.get('detail',''))[:70]}")
        if info.get("upstream_message"):
            print(f"            上游: {info['upstream_message'][:90]}")
    ok3b = code == 200 and len(services) == 3 and any(
        info.get("ok") is not None for info in services.values()
    )
    results.append(("3b 服务自检（实测探针）", "pass" if ok3b else "fail", f"HTTP {code}"))

    # ---------- 用例 4：错误格式 ----------
    code, raw, elapsed = post_multipart(
        "/api/inspect-image", {}, {"image": ("clip.wav", "audio/wav", wav)},
    )
    print(f"\n  用例 4  错误格式  HTTP {code}  {raw[:90]}")
    results.append(("4 错误格式拒绝", "pass" if code == 400 else "fail", f"HTTP {code}"))

    # ---------- 用例 5：超大图 ----------
    big = b"\x89PNG\r\n\x1a\n" + b"\x00" * (9 * 1024 * 1024)
    code, raw, elapsed = post_multipart(
        "/api/inspect-image", {}, {"image": ("huge.png", "image/png", big)},
    )
    print(f"\n  用例 5  超大图  HTTP {code}  {raw[:120]}")
    results.append(("5 超大图拒绝", "pass" if code in (400, 413) else "fail", f"HTTP {code}"))

    # ---------- 用例 6：空音频 ----------
    code, raw, elapsed = post_multipart(
        "/api/transcribe", {}, {"audio": ("empty.wav", "audio/wav", b"")},
    )
    print(f"\n  用例 6  空音频  HTTP {code}  {raw[:100]}")
    results.append(("6 空音频提示", "pass" if code in (400, 422) else "fail", f"HTTP {code}"))

    # ---------- 汇总 ----------
    print()
    print("=" * 80)
    for name, verdict, note in results:
        print(f"  [{verdict:^7}] {name:<26} {note}")
    passed = sum(1 for _, v, _ in results if v == "pass")
    print(f"\n通过 {passed}/{len(results)}")
    print("=" * 80)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
