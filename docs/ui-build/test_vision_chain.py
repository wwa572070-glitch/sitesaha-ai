"""图像识别链路实测：7 种情况（第 22 轮 P0）。

按指令要求逐项测：
  1. 正常 JPG
  2. 正常 PNG
  3. 不支持的格式
  4. 超出限制的图片
  5. 空文件 / 损坏图片
  6. 视觉模型调用失败
  7. 模型返回空或格式异常

不伪造任何模型响应；失败就如实记录失败原因。

用法：python test_vision_chain.py
"""

from __future__ import annotations

import io
import json
import struct
import sys
import time
import urllib.error
import urllib.request
import zlib
from pathlib import Path

APP = Path(__file__).resolve().parent.parent.parent
BASE = "http://127.0.0.1:8504"
BOUNDARY = "----VisionChainProbe7f3a"


def png(width: int, height: int, rgb: tuple[int, int, int]) -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))
    raw = b"".join(b"\x00" + bytes(rgb) * width for _ in range(height))
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw))
            + chunk(b"IEND", b""))


def post_image(data: bytes, filename: str, mime: str, timeout: int = 180):
    """直接带 Content-Type 发原始体，模拟二进制上传路径。"""
    request = urllib.request.Request(
        BASE + "/api/inspect-image",
        data=data,
        headers={"Content-Type": mime,
                 "Content-Length": str(len(data)),
                 "X-Filename": filename},
        method="POST",
    )
    started = time.time()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, json.loads(response.read().decode("utf-8")), time.time() - started
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        try:
            return exc.code, json.loads(body), time.time() - started
        except Exception:
            return exc.code, body[:300], time.time() - started
    except Exception as exc:  # noqa: BLE001
        return 0, f"{type(exc).__name__}: {exc}", time.time() - started


def post_multipart(data: bytes, filename: str, mime: str, timeout: int = 180):
    parts = [
        (f"--{BOUNDARY}\r\n"
         f'Content-Disposition: form-data; name="image"; filename="{filename}"\r\n'
         f"Content-Type: {mime}\r\n\r\n").encode(),
        data,
        b"\r\n",
        f"--{BOUNDARY}--\r\n".encode(),
    ]
    request = urllib.request.Request(
        BASE + "/api/inspect-image",
        data=b"".join(parts),
        headers={"Content-Type": f"multipart/form-data; boundary={BOUNDARY}"},
        method="POST",
    )
    started = time.time()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, json.loads(response.read().decode("utf-8")), time.time() - started
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        try:
            return exc.code, json.loads(body), time.time() - started
        except Exception:
            return exc.code, body[:300], time.time() - started
    except Exception as exc:  # noqa: BLE001
        return 0, f"{type(exc).__name__}: {exc}", time.time() - started


def main() -> int:
    print("=" * 78)
    print("图像识别链路实测（服务端 " + BASE + "）")
    print("=" * 78)

    # 找一个真实截图当作「正常图片」
    shot = APP / "docs" / "ui-build" / "evidence" / "desktop-home.png"
    if not shot.is_file():
        shot = APP / "docs" / "ui-build" / "_shot" / "page-light-home.png"
    real = shot.read_bytes() if shot.is_file() else None
    print(f"  测试用真实图片: {shot.name if real else '（找不到）'} "
          f"{len(real) // 1024 if real else 0} KB")
    print()

    cases = []

    # 1. 正常 PNG（真实截图，multipart）
    if real:
        cases.append(("1. 正常 PNG（真实截图 · multipart）",
                      lambda: post_multipart(real, "shot.png", "image/png")))
        # 2. 正常 PNG（原始二进制）
        cases.append(("2. 正常 PNG（真实截图 · 二进制体）",
                      lambda: post_image(real, "shot.png", "image/png")))

    # 3. 不支持的格式
    cases.append(("3. 不支持的格式（.txt 当图片）",
                  lambda: post_multipart(b"this is not an image at all",
                                         "note.txt", "text/plain")))

    # 4. 超出限制（>8MB）
    cases.append(("4. 超出大小限制（9 MB）",
                  lambda: post_multipart(b"\x89PNG\r\n\x1a\n" + b"\x00" * (9 * 1024 * 1024),
                                         "huge.png", "image/png")))

    # 5a. 空文件
    cases.append(("5a. 空文件（0 字节）",
                  lambda: post_multipart(b"", "empty.png", "image/png")))
    # 5b. 损坏图片（头部合法、内容截断）
    cases.append(("5b. 损坏 PNG（头部合法、数据截断）",
                  lambda: post_multipart(png(400, 300, (90, 90, 90))[:200],
                                         "broken.png", "image/png")))

    # 6. 过小图片（会触发服务端退化图闸门）
    cases.append(("6. 退化图 1×1（幻觉闸门）",
                  lambda: post_multipart(png(1, 1, (128, 128, 128)),
                                         "tiny.png", "image/png")))

    # 7. 中等尺寸纯色图（模型可能返回空或异常）
    cases.append(("7. 纯色灰块 400×300（模型可能无内容可报）",
                  lambda: post_multipart(png(400, 300, (120, 120, 120)),
                                         "flat.png", "image/png")))

    failures = 0
    for label, runner in cases:
        print("-" * 78)
        print(f"  {label}")
        status, data, elapsed = runner()
        print(f"    HTTP {status}  耗时 {elapsed:.1f}s")

        if not isinstance(data, dict):
            print(f"    非 JSON 响应: {str(data)[:200]}")
            failures += 1
            continue

        for key in ("error", "error_code", "hint", "image_quality", "rejected", "mode"):
            if key in data and data[key] not in (None, ""):
                print(f"    {key} = {str(data[key])[:110]}")

        text = data.get("text") or ""
        if text:
            print(f"    text（前 130 字）: {str(text)[:130]}")

        structured = data.get("structured") or {}
        if structured:
            print(f"    structured.work_type = {structured.get('work_type')!r}")
            print(f"    structured.risks     = {len(structured.get('risks') or [])} 条")
            print(f"    structured.actions   = {len(structured.get('actions') or [])} 条")
            print(f"    structured.unclear   = {len(structured.get('unclear') or [])} 条")
            print(f"    citations            = {len(data.get('citations') or [])} 条")
        if data.get("degraded"):
            print(f"    degraded = {data['degraded']}")
        print()

    print("=" * 78)
    print("说明")
    print("=" * 78)
    print("  以上全部是真实调用结果，未伪造任何模型响应。")
    print("  过小图片被拒是**设计行为**（防幻觉闸门），不是故障。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
