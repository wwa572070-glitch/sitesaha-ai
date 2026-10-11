"""按指定主题截图：把 data-theme 直接写进页面副本，避免依赖 localStorage。

用法：
    python shot_theme.py --theme dark   --only desktop
    python shot_theme.py --theme light  --only mobile
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

BUILD = Path(__file__).resolve().parent
REPO = BUILD.parent.parent
OUT = BUILD / "_shot"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

VIEWPORTS = {
    "desktop": (1440, 2600),
    "tablet": (900, 2000),
    "mobile": (492, 2400),
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--theme", choices=["dark", "light"], required=True)
    parser.add_argument("--only", default="desktop")
    parser.add_argument("--view", default="", help="切到某个视图（如 training）")
    parser.add_argument("--base", default="http://127.0.0.1:8504/")
    args = parser.parse_args()

    # 走服务地址，并用 ?theme= 查询参数强制主题（只影响本次渲染，不写 localStorage）
    url = f"{args.base}?theme={args.theme}" + (f"#{args.view}" if args.view else "")
    name = args.only if args.only in VIEWPORTS else "desktop"
    width, height = VIEWPORTS[name]
    target = OUT / f"{args.theme}-{name}.png"
    OUT.mkdir(parents=True, exist_ok=True)
    target.unlink(missing_ok=True)

    profile = Path(tempfile.gettempdir()) / f"_shotprof_{args.theme}_{name}"
    shutil.rmtree(profile, ignore_errors=True)
    profile.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [
            EDGE, "--headless=new", "--disable-gpu", "--no-sandbox",
            "--hide-scrollbars", "--disable-extensions",
            f"--user-data-dir={profile}",
            f"--window-size={width},{height}",
            f"--screenshot={target}",
            "--virtual-time-budget=9000",
            url,
        ],
        capture_output=True, text=True, timeout=180,
    )
    if target.is_file() and target.stat().st_size > 5000:
        print(f"[ok] {args.theme}/{name} {width}x{height}  {target.stat().st_size // 1024} KB")
        print(f"     {target}")
        return 0
    print(f"[FAIL] 截图未生成（退出码 {result.returncode}）")
    print((result.stderr or "")[-300:])
    return 1


if __name__ == "__main__":
    sys.exit(main())
