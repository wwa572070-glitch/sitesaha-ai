"""在真实渲染页面上探measure元素的可见性与计算样式，用于定位截图里"看不见"的元素。

用法：python probe_rendered.py --view ask [--theme light]
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

BUILD = Path(__file__).resolve().parent
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

TARGETS = [
    "#photoStage", "#photoPreview", "#cameraStage", "#cameraVideo",
    "#photoButton", "#photoResult", "#photoError", "#photoProgress",
    "#recordStopButton", "#recordButton",
    "#assistantView", "#ask", "#sos",
]

PROBE = """
<script>
(function () {
  function run() {
    var m = /[?&]view=([a-z]+)/.exec(location.search || "");
    if (m) {
      var tabs = document.querySelectorAll(".nav-button");
      for (var i = 0; i < tabs.length; i++) {
        if (tabs[i].dataset && tabs[i].dataset.view === m[1]) { tabs[i].click(); break; }
      }
    }
    setTimeout(function () {
      var targets = __TARGETS__;
      var out = {};
      targets.forEach(function (sel) {
        var el = document.querySelector(sel);
        if (!el) { out[sel] = "不存在"; return; }
        var cs = getComputedStyle(el);
        var r = el.getBoundingClientRect();
        out[sel] = {
          hidden: el.hidden,
          display: cs.display,
          visibility: cs.visibility,
          color: cs.color,
          bg: cs.backgroundColor,
          text: (el.textContent || "").trim().slice(0, 34),
          alt: el.getAttribute ? (el.getAttribute("alt") || "") : "",
          src: el.getAttribute ? (el.getAttribute("src") || "(无)") : "",
          w: Math.round(r.width), h: Math.round(r.height),
          visible: !el.hidden && cs.display !== "none" && cs.visibility !== "hidden" && r.height > 0
        };
      });
      var pre = document.createElement("pre");
      pre.id = "__probe__";
      pre.textContent = JSON.stringify(out);
      document.body.appendChild(pre);
    }, 900);
  }
  if (document.readyState === "complete") setTimeout(run, 400);
  else window.addEventListener("load", function () { setTimeout(run, 400); });
})();
</script>
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--view", default="ask")
    parser.add_argument("--theme", default="light")
    parser.add_argument("--base", default="http://127.0.0.1:8504/")
    args = parser.parse_args()

    with urllib.request.urlopen(args.base, timeout=30) as response:
        html = response.read().decode("utf-8", "replace")
    probe = PROBE.replace("__TARGETS__", json.dumps(TARGETS))
    html = html.replace("<head>", f'<head><base href="{args.base}">', 1)
    index = html.rfind("</body>")
    html = html[:index] + probe + html[index:]
    page = Path(tempfile.gettempdir()) / f"_probe_{args.view}.html"
    page.write_text(html, encoding="utf-8")

    profile = Path(tempfile.gettempdir()) / f"_probeprof_{args.view}"
    shutil.rmtree(profile, ignore_errors=True)
    profile.mkdir(parents=True, exist_ok=True)

    result = subprocess.run(
        [
            EDGE, "--headless=new", "--disable-gpu", "--no-sandbox", "--disable-extensions",
            f"--user-data-dir={profile}", "--window-size=1440,1200",
            "--virtual-time-budget=8000", "--dump-dom",
            page.as_uri() + f"?theme={args.theme}&view={args.view}",
        ],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=200,
    )
    match = re.search(r'<pre id="__probe__">(.*?)</pre>', result.stdout or "", re.S)
    if not match:
        print("[FAIL] 探针未执行")
        return 1
    text = match.group(1)
    for entity, char in (("&quot;", '"'), ("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">")):
        text = text.replace(entity, char)
    data = json.loads(text)

    print(f"视图 ?view={args.view}  主题 {args.theme}\n")
    print(f"{'选择器':<20} {'可见':<6} {'hidden':<8} {'display':<10} {'文字色':<20} {'背景'}")
    print("-" * 96)
    for selector, value in data.items():
        if isinstance(value, str):
            print(f"{selector:<20} {value}")
            continue
        print(
            f"{selector:<20} {'是' if value['visible'] else '否':<6} {str(value['hidden']):<8} "
            f"{value['display']:<10} {value['color']:<20} {value['bg']}"
        )
    print()
    print("=== 有文本或 alt 的项（用于核对文案与对比度）===")
    for selector, value in data.items():
        if isinstance(value, str):
            continue
        if value["text"] or value["alt"]:
            print(f"  {selector}")
            if value["text"]:
                print(f"     text: {value['text']!r}")
            if value["alt"]:
                print(f"     alt : {value['alt']!r}   src: {value['src']}")
            print(f"     可见={value['visible']}  尺寸 {value['w']}x{value['h']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
