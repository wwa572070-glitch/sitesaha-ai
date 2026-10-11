"""逐个视觉带量出元素的左右边界，判断哪一侧被裁。

用法：python measure_bands.py evidence/mobile-home.png [--step 10]
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

CANVAS = (244, 246, 247)
SURFACE = (255, 255, 255)
INK = (15, 18, 21)


def near(px, target, tol=8):
    return all(abs(a - b) <= tol for a, b in zip(px[:3], target))


def main() -> int:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "evidence/mobile-home.png")
    step = int(sys.argv[3]) if len(sys.argv) > 3 else 10
    im = Image.open(path).convert("RGB")
    width, height = im.size
    print(f"图像 {width}x{height}")
    print()
    print(f"{'y':>5}  {'该行主要底色':<12} {'左边界':>7} {'右边界':>7} {'左留白':>6} {'右留白':>6}  判定")
    print("-" * 78)
    for y in range(150, height, step):
        row = [im.getpixel((x, y))[:3] for x in range(width)]
        left = next((x for x in range(width) if not near(row[x], CANVAS)), None)
        right = next((x for x in range(width - 1, -1, -1) if not near(row[x], CANVAS)), None)
        if right is None:
            continue
        ink = sum(1 for px in row if near(px, INK, 14))
        surf = sum(1 for px in row if near(px, SURFACE))
        if ink > 200:
            desc = "Hero 深底"
        elif surf > 200:
            desc = "白卡片"
        else:
            desc = "混合"
        rpad = width - 1 - right
        verdict = ""
        if rpad == 0 and left and left > 0:
            verdict = "<-- 右侧被裁"
        elif left == 0 and right < width - 1:
            verdict = "<-- 左侧被裁"
        print(f"{y:>5}  {desc:<12} {left!s:>7} {right!s:>7} {left!s:>6} {rpad!s:>6}  {verdict}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
