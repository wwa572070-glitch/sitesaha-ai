"""检查 structured 的真实数据结构（第 24 轮，渲染前必做）。

指令要求：先检查实际数据结构、字段类型和空值情况，再进行前端渲染。

用法：python inspect_structured.py
"""

from __future__ import annotations

import json
import struct
import sys
import urllib.request
import zlib
from pathlib import Path

APP = Path(__file__).resolve().parent.parent.parent
BASE = "http://127.0.0.1:8504"
BOUNDARY = "----StructProbe44b1"


def png(width: int, height: int) -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))
    rows = []
    for y in range(height):
        row = bytearray(b"\x00")
        for x in range(width):
            row += bytes(((x * 3) % 256, (y * 5) % 256, 180))
        rows.append(bytes(row))
    raw = b"".join(rows)
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw))
            + chunk(b"IEND", b""))


def post(image: bytes, name: str, mime: str):
    parts = [
        (f"--{BOUNDARY}\r\n"
         f'Content-Disposition: form-data; name="image"; filename="{name}"\r\n'
         f"Content-Type: {mime}\r\n\r\n").encode(),
        image, b"\r\n", f"--{BOUNDARY}--\r\n".encode(),
    ]
    request = urllib.request.Request(
        BASE + "/api/inspect-image", data=b"".join(parts),
        headers={"Content-Type": f"multipart/form-data; boundary={BOUNDARY}"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        return json.loads(response.read().decode("utf-8"))


def describe(value, indent: int = 0) -> None:
    pad = "  " * indent
    if isinstance(value, dict):
        for key, item in value.items():
            kind = type(item).__name__
            if isinstance(item, (dict, list)):
                size = len(item)
                print(f"{pad}{key}: {kind}({size})")
                if item:
                    describe(item[0] if isinstance(item, list) else item, indent + 1)
            else:
                shown = repr(item)
                print(f"{pad}{key}: {kind} = {shown[:100]}")
    elif isinstance(value, list):
        pass


def main() -> int:
    # 用真实截图（有内容，能触发较完整的结构化输出）
    shot = APP / "docs" / "ui-build" / "evidence" / "desktop-ask.png"
    if not shot.is_file():
        shot = APP / "docs" / "ui-build" / "evidence" / "desktop-home.png"
    image = shot.read_bytes()
    print(f"测试图片: {shot.name}  {len(image) // 1024} KB")
    print()

    data = post(image, shot.name, "image/png")

    print("=" * 78)
    print("顶层字段")
    print("=" * 78)
    for key, value in data.items():
        kind = type(value).__name__
        if isinstance(value, list):
            print(f"  {key:<18} list({len(value)})")
        elif isinstance(value, dict):
            print(f"  {key:<18} dict({len(value)})")
        else:
            print(f"  {key:<18} {kind} = {repr(value)[:80]}")

    print()
    print("=" * 78)
    print("structured 详细结构")
    print("=" * 78)
    structured = data.get("structured")
    if not isinstance(structured, dict):
        print(f"  structured 不是 dict：{type(structured).__name__}")
        print(f"  值：{repr(structured)[:200]}")
        return 1
    describe(structured)

    print()
    print("=" * 78)
    print("每个数组字段的首项样本（用于确定渲染字段名）")
    print("=" * 78)
    for key, value in structured.items():
        if isinstance(value, list):
            print(f"  --- {key}（{len(value)} 项）---")
            for index, item in enumerate(value[:3]):
                print(f"    [{index}] {type(item).__name__}: {repr(item)[:150]}")
            if not value:
                print("    （空数组）")
            print()
        elif isinstance(value, str):
            print(f"  --- {key}（字符串）---")
            print(f"    {repr(value)[:200]}")
            print()

    print("=" * 78)
    print("citations 样本")
    print("=" * 78)
    citations = data.get("citations")
    if isinstance(citations, list):
        print(f"  {len(citations)} 条")
        for item in citations[:2]:
            print(f"    {repr(item)[:160]}")
    else:
        print(f"  {type(citations).__name__}: {repr(citations)[:120]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
