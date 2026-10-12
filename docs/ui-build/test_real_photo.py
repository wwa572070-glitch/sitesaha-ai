"""用真实工地照片跑一次识别，看答辩时评委会看到什么（第 24 轮）。

用法：python test_real_photo.py
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

APP = Path(__file__).resolve().parent.parent.parent
BUILD = Path(__file__).resolve().parent
BASE = "http://127.0.0.1:8504"
BOUNDARY = "----RealSitePhoto5a1"

PHOTO = BUILD / "evidence" / "real-site.jpg"


def main() -> int:
    if not PHOTO.is_file():
        print(f"找不到照片：{PHOTO}")
        return 1
    data = PHOTO.read_bytes()
    print(f"照片：{PHOTO.name}  {len(data) // 1024} KB")
    print()

    parts = [
        (f"--{BOUNDARY}\r\n"
         f'Content-Disposition: form-data; name="image"; filename="real-site.jpg"\r\n'
         f"Content-Type: image/jpeg\r\n\r\n").encode(),
        data, b"\r\n", f"--{BOUNDARY}--\r\n".encode(),
    ]
    request = urllib.request.Request(
        BASE + "/api/inspect-image",
        data=b"".join(parts),
        headers={"Content-Type": f"multipart/form-data; boundary={BOUNDARY}"},
        method="POST",
    )

    started = time.time()
    try:
        with urllib.request.urlopen(request, timeout=240) as response:
            payload = json.loads(response.read().decode("utf-8"))
            status = response.status
    except urllib.error.HTTPError as exc:
        print(f"HTTP {exc.code}")
        print(exc.read().decode("utf-8", "replace")[:400])
        return 1
    elapsed = time.time() - started

    print("=" * 78)
    print(f"识别结果（HTTP {status} · 耗时 {elapsed:.1f}s）")
    print("=" * 78)

    print(f"  image_quality = {payload.get('image_quality')}")
    if payload.get("rejected"):
        print("  ** 被防幻觉闸门拒绝 **")
    print()

    structured = payload.get("structured") or {}
    print("--- A 识别结论 ---")
    print(f"  作业场景: {structured.get('work_type') or '（未识别）'}")
    risks = structured.get("risks") or []
    uncertain = structured.get("uncertain") or []
    print(f"  可见风险: {len(risks)} 条")
    print(f"  待确认:   {len(uncertain)} 项")
    print()

    if risks:
        print("--- B 风险位置与现象 / C 整改建议 ---")
        for index, item in enumerate(risks, 1):
            if not isinstance(item, dict):
                continue
            print(f"  [{index}] 位置：{item.get('where') or '（未给出）'}")
            print(f"      现象：{item.get('what') or '（未给出）'}")
            action = (item.get("action") or "").strip()
            print(f"      动作：{action if action else '（未给出）'}")
            print()

    if uncertain:
        print("--- D 待确认 ---")
        for index, text in enumerate(uncertain, 1):
            print(f"  [{index}] {text}")
        print()

    print("--- 模型原始文本 ---")
    print(payload.get("text") or "（空）")
    print()

    warnings = payload.get("warnings") or []
    if warnings:
        print("--- 告警 ---")
        for warning in warnings:
            print(f"  · {warning}")
        print()

    sources = payload.get("sources") or []
    print(f"--- 引用来源 {len(sources)} 条 ---")
    for index, item in enumerate(sources[:5], 1):
        title = item.get("title") if isinstance(item, dict) else str(item)
        print(f"  [{index}] {str(title)[:70]}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
