"""dump 关键元素的最终计算样式，用于定位暗色模式下"深字压深底"的具体来源。

用法：python probe_dark_mode.py [light|dark]
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

BUILD = Path(__file__).resolve().parent
REPO = BUILD.parent.parent
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

PROBE = r"""
<script>
(function () {
  function run() {
    var targets = [
      "body", "header", ".hero", ".hero h2", ".hero-desc",
      ".panel-head", ".panel-head h2", ".panel-body",
      ".todo-item b", ".todo-item span", ".phase-title", ".phase-desc",
      ".role-chip", ".action-card strong", ".action-card p",
      ".nav-button", ".stat-cell b"
    ];
    var out = {};
    targets.forEach(function (sel) {
      var el = document.querySelector(sel);
      if (!el) { out[sel] = "（元素不存在）"; return; }
      var cs = getComputedStyle(el);
      out[sel] = {
        color: cs.color,
        bg: cs.backgroundColor,
        size: cs.fontSize,
        weight: cs.fontWeight
      };
    });
    out["__html_attr__"] = document.documentElement.getAttribute("data-theme") || "(无)";
    var pre = document.createElement("pre");
    pre.id = "__prob__";
    pre.textContent = JSON.stringify(out);
    document.body.appendChild(pre);
  }
  if (document.readyState === "complete") setTimeout(run, 600);
  else window.addEventListener("load", function () { setTimeout(run, 600); });
})();
</script>
"""


def main() -> int:
    theme = sys.argv[1] if len(sys.argv) > 1 else "dark"
    html_path = REPO / "webapp.py"
    sys.path.insert(0, str(REPO))
    import webapp  # noqa: PLC0415

    html = webapp.INDEX_HTML
    patched = html.replace("</body>", PROBE + "</body>")
    tmp = Path(tempfile.gettempdir()) / f"_probe_{theme}.html"
    tmp.write_text(patched, encoding="utf-8")

    url = tmp.as_uri() + (f"?theme={theme}" if theme != "light" else "")
    result = subprocess.run(
        [
            EDGE, "--headless=new", "--disable-gpu", "--no-sandbox", "--disable-extensions",
            f"--user-data-dir={Path(tempfile.gettempdir()) / f'_probeprof_{theme}'}",
            "--window-size=1440,900", "--virtual-time-budget=7000", "--dump-dom", url,
        ],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180,
    )
    match = re.search(r'<pre id="__prob__">(.*?)</pre>', result.stdout or "", re.S)
    if not match:
        print("[FAIL] 探针未执行（本地文件方式可能拿不到，属正常）")
        return 1

    text = match.group(1)
    for entity, char in (("&quot;", '"'), ("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">")):
        text = text.replace(entity, char)
    data = json.loads(text)

    print(f"主题参数 ?theme={theme}  →  html[data-theme] = {data.pop('__html_attr__')}")
    print()
    print(f"{'选择器':<26} {'文字色':<22} {'背景色':<22} {'字号'}")
    print("-" * 82)
    for selector, value in data.items():
        if isinstance(value, str):
            print(f"{selector:<26} {value}")
            continue
        print(f"{selector:<26} {value['color']:<22} {value['bg']:<22} {value['size']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
