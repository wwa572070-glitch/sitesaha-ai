"""检查 AI 图像识别工作台现状（竞赛级 UI 升级 第 1 步）。

用法：python inspect_workbench.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent


def main() -> int:
    body = (BUILD / "index_body.html").read_text(encoding="utf-8")
    script_b = (BUILD / "index_script_b.js").read_text(encoding="utf-8")

    print("=" * 78)
    print("一、ask 视图的 DOM 结构")
    print("=" * 78)
    start = body.find('<section id="ask"')
    end = body.find('<section id="', start + 10)
    section = body[start:end]
    print(f"  区块大小 {len(section)} 字符")
    for line_no, line in enumerate(section.split("\n"), 1):
        stripped = line.strip()
        if stripped.startswith("<") and any(
            key in stripped for key in ("<h2", "<h3", "class=", "id=", "<section", "<input", "<button", "<figure")
        ):
            print(f"  {line_no:>4} {stripped[:104]}")

    print()
    print("=" * 78)
    print("二、图片上传相关元素")
    print("=" * 78)
    for key in ("photoInput", "photoPreview", "cameraStage", "inspectButton",
                "photoButton", "capture", "camera"):
        for match in re.finditer(re.escape(key), body):
            line = body[: match.start()].count("\n") + 1
            print(f"  {key:<16} body:{line}")
            break

    print()
    print("=" * 78)
    print("三、上传流程 JS")
    print("=" * 78)
    for key in ("photoInput", "accept", "image/", "MAX_IMAGE", "inspect-image"):
        for match in re.finditer(re.escape(key), script_b):
            line = script_b[: match.start()].count("\n") + 1
            segment = " ".join(script_b[max(0, match.start() - 120): match.start() + 200].split())
            print(f"  [{line}] ({key}) {segment[:190]}")
            break

    print()
    print("=" * 78)
    print("四、识别结果渲染")
    print("=" * 78)
    for key in ("renderInspection", "inspectionResult", "photoResult", "structured"):
        for match in re.finditer(re.escape(key), script_b):
            line = script_b[: match.start()].count("\n") + 1
            print(f"  {key:<20} 行 {line}")
            break
    return 0


if __name__ == "__main__":
    sys.exit(main())
