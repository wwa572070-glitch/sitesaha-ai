"""用无头 Edge 给本地页面截图，便于逐轮核对视觉效果。

支持三种视口（桌面 / 平板 / 手机）与指定视图切换（通过 URL hash）。

用法：
    python shot.py                    # 桌面 + 平板 + 手机 三张首页
    python shot.py --view training    # 截指定视图
    python shot.py --only mobile      # 只截手机
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

BUILD = Path(__file__).resolve().parent
OUT = BUILD / "_shot"
EDGE_CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]

VIEWPORTS = {
    "desktop": (1440, 2600),
    "tablet": (834, 1800),
    "mobile": (390, 2200),
    "wide": (1920, 1600),
}


def find_edge() -> str | None:
    for path in EDGE_CANDIDATES:
        if Path(path).is_file():
            return path
    return None


def shoot(edge: str, name: str, size: tuple[int, int], url: str) -> Path | None:
    target = OUT / f"{name}.png"
    target.unlink(missing_ok=True)
    profile = OUT / f"profile-{name}"
    profile.mkdir(parents=True, exist_ok=True)

    width, height = size
    args = [
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        "--hide-scrollbars",
        "--disable-extensions",
        "--disable-features=Translate,BackForwardCache",
        f"--user-data-dir={profile}",
        f"--window-size={width},{height}",
        f"--screenshot={target}",
        "--virtual-time-budget=9000",
        url,
    ]
    result = subprocess.run([edge, *args], capture_output=True, text=True, timeout=180)
    if target.is_file() and target.stat().st_size > 5000:
        print(f"[ok] {name:8} {width}x{height}  {target.stat().st_size // 1024} KB")
        return target
    print(f"[FAIL] {name}：截图未生成（退出码 {result.returncode}）")
    tail = (result.stderr or "")[-200:]
    if tail:
        print("      ", tail.replace("\n", " ")[:180])
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8504/")
    parser.add_argument("--view", default="", help="视图名，会拼成 #<view>")
    parser.add_argument("--only", default="", help="只截某个视口")
    parser.add_argument("--tag", default="", help="文件名前缀，便于区分多轮")
    args = parser.parse_args()

    edge = find_edge()
    if not edge:
        print("[FAIL] 未找到 Edge")
        return 1

    url = args.base + (f"#{args.view}" if args.view else "")
    OUT.mkdir(parents=True, exist_ok=True)
    print(f"目标：{url}")

    names = [args.only] if args.only else list(VIEWPORTS)
    ok = 0
    for name in names:
        if name not in VIEWPORTS:
            print(f"[skip] 未知视口 {name}")
            continue
        label = f"{args.tag}{name}" if args.tag else name
        if shoot(edge, label, VIEWPORTS[name], url):
            ok += 1
        time.sleep(0.4)

    print(f"\n完成 {ok}/{len(names)} 张，输出目录：{OUT}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
