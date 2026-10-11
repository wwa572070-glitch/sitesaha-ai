"""探明无头 Edge 的最小视口宽度：试多种参数组合，打印真实 innerWidth。

用法：python probe_viewport.py
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

PAGE = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"></head><body>
<pre id="r">pending</pre>
<script>
document.getElementById("r").textContent = JSON.stringify({
  innerWidth: window.innerWidth,
  clientWidth: document.documentElement.clientWidth,
  outerWidth: window.outerWidth,
  dpr: window.devicePixelRatio
});
</script></body></html>"""


def run(label: str, extra: list[str], width: int) -> str:
    tmp = Path(tempfile.gettempdir()) / "_vwprobe.html"
    tmp.write_text(PAGE, encoding="utf-8")
    cmd = [
        EDGE, "--disable-gpu", "--no-sandbox", "--disable-extensions",
        f"--window-size={width},800", *extra, "--dump-dom", tmp.as_uri(),
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=120,
        )
    except subprocess.TimeoutExpired:
        return "超时"
    text = result.stdout or ""
    match = re.search(r'<pre id="r">(.*?)</pre>', text, re.S)
    if not match:
        return f"无结果（退出码 {result.returncode}，stdout {len(text)} 字符）"
    raw = match.group(1).strip()
    try:
        data = json.loads(raw)
        return f"innerWidth={data['innerWidth']} clientWidth={data['clientWidth']} outerWidth={data['outerWidth']} dpr={data['dpr']}"
    except json.JSONDecodeError:
        return f"原始：{raw[:80]}"


def main() -> int:
    width = 390
    combos = [
        ("--headless=new", ["--headless=new"]),
        ("--headless=old", ["--headless=old"]),
        ("--headless", ["--headless"]),
        ("new + device-scale 1", ["--headless=new", "--force-device-scale-factor=1"]),
        ("new + scale 0.8", ["--headless=new", "--force-device-scale-factor=0.8"]),
        ("new + no-first-run", ["--headless=new", "--no-first-run", "--no-default-browser-check"]),
        ("old + scale 1", ["--headless=old", "--force-device-scale-factor=1"]),
    ]
    print(f"目标窗口宽度 {width}px\n")
    for label, extra in combos:
        print(f"{label:<24} -> {run(label, extra, width)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
