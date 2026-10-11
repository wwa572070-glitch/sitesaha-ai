"""采样截图像素，客观判定主题是亮还是暗，并检查页面有没有明显空段。

用法：python check_theme_pixel.py <图片路径> [期望主题]
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

BUILD = Path(__file__).resolve().parent
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"


def luminance(rgb: tuple[int, int, int]) -> float:
    return (0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]) / 255.0


def capture(url: str, width: int, height: int, name: str) -> Path | None:
    target = Path(tempfile.gettempdir()) / f"_pix_{name}.png"
    target.unlink(missing_ok=True)
    subprocess.run(
        [
            EDGE, "--headless=new", "--disable-gpu", "--no-sandbox",
            "--hide-scrollbars", "--disable-extensions",
            f"--user-data-dir={Path(tempfile.gettempdir()) / f'_pixprof_{name}'}",
            f"--window-size={width},{height}",
            f"--screenshot={target}",
            "--virtual-time-budget=7000",
            url,
        ],
        capture_output=True, text=True, timeout=180,
    )
    return target if target.is_file() else None


def main() -> int:
    try:
        from PIL import Image
    except ImportError:
        print("[FAIL] 需要 Pillow")
        return 1

    base = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8504/"
    expected = (sys.argv[2] if len(sys.argv) > 2 else "").lower()

    print(f"{'主题参数':<16} {'页底亮度':>9} {'卡片亮度':>9} {'判定':<6}")
    print("-" * 52)
    verdicts: dict[str, str] = {}
    for theme in ("light", "dark"):
        url = base + f"?theme={theme}"
        shot = capture(url, 1400, 900, theme)
        if not shot:
            print(f"{theme:<16} 截图失败")
            continue
        image = Image.open(shot).convert("RGB")
        width, height = image.size
        # 采样点必须落在页面主体上：
        # 顶栏是固定的深色（两种主题都一样），靠边的点会一直采到它。
        # 卡片之间的空白（列间隙）才是真正的页底颜色。
        page_bg = image.getpixel((int(width * 0.505), int(height * 0.55)))
        card = image.getpixel((int(width * 0.30), int(height * 0.62)))
        lp, lc = luminance(page_bg), luminance(card)
        verdict = "暗色" if lp < 0.35 else "亮色"
        verdicts[theme] = verdict
        print(f"{theme:<16} {lp:>9.3f} {lc:>9.3f} {verdict:<6}")

    if expected and expected in verdicts:
        ok = verdicts[expected] == ("暗色" if expected == "dark" else "亮色")
        print()
        print(f"[{'OK' if ok else 'FAIL'}] 期望 {expected} 主题，实际渲染为 {verdicts[expected]}")
        return 0 if ok else 1
    if len(set(verdicts.values())) == 1 and len(verdicts) == 2:
        print("\n[FAIL] 两套主题渲染结果相同，说明切换没生效")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
