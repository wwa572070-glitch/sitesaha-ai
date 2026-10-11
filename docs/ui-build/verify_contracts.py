"""验证 §3.2 与 §3.3 的接口契约（第 16 轮 v2）。

§3.2 验收：/api/ask 的响应体不得含 Python 异常原文
  · 空 body
  · 非法 JSON
  · 正常问题
§3.3 验收：/api/inspect-image 返回 structured 字段
  · 真实工地照 → structured.work_type 非空、risks 有 where/what/action
  · 1x1 像素图 → image_quality = low

用法：python verify_contracts.py [--photo 路径]
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = "http://127.0.0.1:8504"
BOUNDARY = "----SiteSahaContract7f3a9c"
FORBIDDEN = ["Expecting value", "Traceback", "RuntimeError", "KeyError",
             "AttributeError", "TypeError", "json.decoder"]


def post_raw(path: str, data: bytes, content_type: str, timeout: int = 90):
    request = urllib.request.Request(
        BASE + path, data=data, headers={"Content-Type": content_type}, method="POST"
    )
    started = time.time()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read().decode("utf-8", "replace"), time.time() - started
    except urllib.error.HTTPError as exc:
        try:
            raw = exc.read().decode("utf-8", "replace")
        except Exception as inner:  # noqa: BLE001
            raw = f'{{"client_error": "{type(inner).__name__}"}}'
        return exc.code, raw, time.time() - started
    except Exception as exc:  # noqa: BLE001
        return 0, json.dumps({"client_error": f"{type(exc).__name__}: {exc}"}), time.time() - started


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
    return post_raw(path, b"".join(parts),
                    f"multipart/form-data; boundary={BOUNDARY}", timeout)


def check_no_leak(label: str, status: int, body: str) -> bool:
    leaked = [token for token in FORBIDDEN if token in body]
    mark = "pass" if not leaked else "FAIL"
    print(f"  [{mark}] {label}：HTTP {status}")
    if leaked:
        print(f"         泄漏了 {leaked}")
        print(f"         响应体：{body[:180]}")
        return False
    print(f"         响应体：{body[:150]}")
    return True


def tiny_png() -> bytes:
    """1x1 像素 PNG —— 用来验证幻觉防护。"""
    import struct
    import zlib

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    header = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    raw = b"\x00\x80\x80\x80"
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header)
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--photo", default="")
    args = parser.parse_args()

    results: list[tuple[str, bool]] = []

    print("=" * 78)
    print("§3.2 /api/ask 不得泄漏 Python 异常原文")
    print("=" * 78)
    results.append(("ask 空 body", check_no_leak(
        "空 body", *post_raw("/api/ask", b"", "application/json")[:2]
    )))
    results.append(("ask 非法 JSON", check_no_leak(
        "非法 JSON", *post_raw("/api/ask", b"not json at all", "application/json")[:2]
    )))
    results.append(("ask 正常问题", check_no_leak(
        "正常问题",
        *post_raw("/api/ask",
                  json.dumps({"question": "高处作业前要检查什么？"}).encode("utf-8"),
                  "application/json")[:2]
    )))

    print()
    print("=" * 78)
    print("§3.3 /api/inspect-image 返回 structured")
    print("=" * 78)

    code, body, elapsed = post_multipart(
        "/api/inspect-image", {"question": "这张照片里有哪些可见的安全风险？"},
        {"image": ("tiny.png", "image/png", tiny_png())},
    )
    data = json.loads(body) if body.startswith("{") else {}
    quality = data.get("image_quality")
    print(f"  1x1 像素图：HTTP {code}  耗时 {elapsed:.1f}s  image_quality={quality}")
    structured = data.get("structured") or {}
    print(f"    structured.work_type={structured.get('work_type')!r} "
          f"risks={len(structured.get('risks') or [])}")
    text = str(data.get("text", ""))
    print(f"    text 前 120 字：{text[:120]}")
    # 幻觉防护：退化图不应给出具体作业场景
    fake_scenes = ["深基坑", "脚手架", "塔吊", "模板支撑", "临边"]
    invented = [word for word in fake_scenes if word in (structured.get("work_type") or "")]
    ok_tiny = (quality == "low") and not invented
    print(f"    [{'pass' if ok_tiny else 'FAIL'}] 质量标记 low 且未编造作业类型")
    results.append(("退化图防护", ok_tiny))

    if args.photo and Path(args.photo).is_file():
        photo = Path(args.photo)
        raw = photo.read_bytes()
        mime = "image/jpeg" if photo.suffix.lower() in {".jpg", ".jpeg"} else "image/png"
        code, body, elapsed = post_multipart(
            "/api/inspect-image", {"question": "这张照片里有哪些可见的安全风险？"},
            {"image": (photo.name, mime, raw)},
        )
        data = json.loads(body) if body.startswith("{") else {}
        structured = data.get("structured") or {}
        risks = structured.get("risks") or []
        print()
        print(f"  真实工地照：HTTP {code}  耗时 {elapsed:.1f}s  "
              f"image_quality={data.get('image_quality')}")
        print(f"    work_type={structured.get('work_type')!r}")
        for item in risks:
            print(f"    · 位置={item.get('where')!r}")
            print(f"      现象={item.get('what')!r}")
            print(f"      动作={item.get('action')!r}")
        print(f"    uncertain={structured.get('uncertain')}")
        print(f"    citations={[c.get('title') for c in (structured.get('citations') or [])][:3]}")
        ok_real = code == 200 and bool(structured.get("work_type")) and bool(risks) \
            and all(item.get("action") for item in risks)
        print(f"    [{'pass' if ok_real else 'FAIL'}] 作业类型非空、风险有位置与动作")
        results.append(("真实照结构化", ok_real))

    print()
    print("=" * 78)
    for name, ok in results:
        print(f"  [{'pass' if ok else 'FAIL'}] {name}")
    passed = sum(1 for _, ok in results if ok)
    print(f"\n通过 {passed}/{len(results)}")
    print("=" * 78)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
