"""从截图像素里量出各元素的水平边界，定位裁剪。

为什么需要：body 上有 overflow-x:hidden，超宽内容会被静默裁掉而不是产生滚动条，
所以 scrollWidth 检测天然看不见。只能从渲染结果反推几何。

用法：python measure_screenshot.py evidence/mobile-home.png
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

# 页面关键底色（取自 V15/V16 令牌）
CANVAS = (244, 246, 247)   # --canvas 页底
SURFACE = (255, 255, 255)  # --surface 卡片
INK = (15, 18, 21)         # --i950 Hero 底


def near(px: tuple[int, int, int], target: tuple[int, int, int], tol: int = 8) -> bool:
    return all(abs(a - b) <= tol for a, b in zip(px[:3], target))


def scan_row(img: Image.Image, y: int, label: str) -> None:
    width = img.size[0]
    row = [img.getpixel((x, y))[:3] for x in range(width)]

    # 找最左/最右的非页底像素
    left = next((x for x in range(width) if not near(row[x], CANVAS)), None)
    right = next((x for x in range(width - 1, -1, -1) if not near(row[x], CANVAS)), None)

    # 统计各类底色占比
    counts = {"canvas": 0, "surface": 0, "ink": 0, "other": 0}
    for px in row:
        if near(px, CANVAS):
            counts["canvas"] += 1
        elif near(px, SURFACE):
            counts["surface"] += 1
        elif near(px, INK, 14):
            counts["ink"] += 1
        else:
            counts["other"] += 1

    edge_left_touch = left == 0
    print(
        f"  y={y:<5} {label:<20} 内容 x=[{left},{right}]  "
        f"canvas={counts['canvas']:>4} surface={counts['surface']:>4} "
        f"ink={counts['ink']:>4} other={counts['other']:>4}"
        + ("   ← 左边界贴 0，说明该行内容顶到视口左边" if edge_left_touch else "")
    )


def main() -> int:
    if len(sys.argv) < 2:
        print("用法：python measure_screenshot.py <png>")
        return 1
    path = Path(sys.argv[1])
    img = Image.open(path).convert("RGB")
    w, h = img.size
    print(f"图像 {w}×{h}")
    print()

    # 找每一行的"内容左边界"，据此判断是否有元素顶到 0
    print("=== 逐扫描线：内容是否顶到视口左右边缘 ===")
    for y in range(60, min(h, 900), 40):
        scan_row(img, y, "")

    print()
    print("=== 结论线索 ===")
    # 若存在连续多行 left==0 且 right==w-1，说明有元素满宽（可能被裁）
    full_rows = 0
    for y in range(0, h, 10):
        row = [img.getpixel((x, y))[:3] for x in range(w)]
        left = next((x for x in range(w) if not near(row[x], CANVAS)), None)
        right = next((x for x in range(w - 1, -1, -1) if not near(row[x], CANVAS)), None)
        if left == 0 and right == w - 1:
            full_rows += 1
    print(f"  满宽（左右都贴边）的扫描线：{full_rows} / {h // 10}")

    # 找 Hero 深色块的左右边界
    print()
    print("=== 深色 Hero 块的左右边界（应留出页边距）===")
    found = 0
    for y in range(60, min(h, 700), 20):
        row = [img.getpixel((x, y))[:3] for x in range(w)]
        xs = [x for x in range(w) if near(row[x], INK, 14)]
        if len(xs) > w * 0.5:
            print(f"  y={y:<5} 深色区 x=[{xs[0]},{xs[-1]}]  宽 {xs[-1]-xs[0]+1}px  "
                  f"左留白 {xs[0]}px  右留白 {w-1-xs[-1]}px")
            found += 1
        if found >= 4:
            break
    if not found:
        print("  未找到大面积深色区")
    return 0


if __name__ == "__main__":
    sys.exit(main())
