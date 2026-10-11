"""在无头 Edge 里测量页面横向溢出：找出比视口宽的元素。

思路：用 headless Edge 打开一个注入脚本的本地页面副本，
脚本把测量结果写进 document.title，再用 --dump-dom 取回。

用法：python check_overflow.py [view] [width]
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
    var vw = document.documentElement.clientWidth;
    var out = [];
    var all = document.querySelectorAll("body *");
    for (var i = 0; i < all.length; i++) {
      var el = all[i];
      var r = el.getBoundingClientRect();
      if (r.width > vw + 1 || r.right > vw + 1) {
        var id = el.id ? "#" + el.id : "";
        var cls = el.className && typeof el.className === "string"
          ? "." + el.className.trim().split(/\s+/).join(".") : "";
        out.push({
          sel: el.tagName.toLowerCase() + id + cls,
          w: Math.round(r.width),
          right: Math.round(r.right)
        });
      }
    }
    out.sort(function (a, b) { return b.right - a.right; });
    var payload = {
      viewport: vw,
      scrollWidth: document.documentElement.scrollWidth,
      offenders: out.slice(0, 25)
    };
    var pre = document.createElement("pre");
    pre.id = "__overflow_report__";
    pre.textContent = JSON.stringify(payload);
    document.body.appendChild(pre);
  }
  if (document.readyState === "complete") setTimeout(run, 400);
  else window.addEventListener("load", function () { setTimeout(run, 400); });
})();
</script>
"""


def main() -> int:
    view = sys.argv[1] if len(sys.argv) > 1 else ""
    width = sys.argv[2] if len(sys.argv) > 2 else "390"
    outer = int(width)
    # 无头 Edge 有最小窗口宽度（约 477px）。
    # 要真正测 390px 这类窄屏，就得把窗口开得更宽、再用浏览器缩放把 CSS 视口压到目标值：
    # CSS 视口宽度 ≈ 外层宽度 / 缩放比，所以这里直接按目标宽度反推 zoom。
    zoom = max(1.0, 477.0 / outer) if outer < 477 else 1.0
    window_width = max(outer, 477)

    page = REPO / "webapp.py"
    # 直接导入模块取常量，比正则可靠（模板里还有别的三引号文档字符串）
    sys.path.insert(0, str(REPO))
    try:
        import webapp  # noqa: PLC0415
    except Exception as exc:  # noqa: BLE001
        print(f"[FAIL] 无法导入 webapp：{type(exc).__name__}: {exc}")
        return 1
    content = webapp.INDEX_HTML

    patched = content.replace("</body>", PROBE + "</body>")
    if patched == content:
        print("[FAIL] 未找到 </body>，无法注入探针")
        return 1

    tmp = Path(tempfile.gettempdir()) / f"_overflow_{width}.html"
    tmp.write_text(patched, encoding="utf-8")

    url = tmp.as_uri() + (f"#{view}" if view else "")
    result = subprocess.run(
        [
            EDGE, "--headless=new", "--disable-gpu", "--no-sandbox",
            "--disable-extensions", "--virtual-time-budget=6000",
            f"--window-size={window_width},1400",
            f"--force-device-scale-factor={1 / zoom:.4f}" if zoom > 1.0 else "--force-device-scale-factor=1",
            "--dump-dom", url,
        ],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180,
    )

    match = re.search(
        r'<pre id="__overflow_report__">(.*?)</pre>', result.stdout or "", re.S
    )
    if not match:
        print("[FAIL] 没拿到测量结果")
        print((result.stdout or "")[:400])
        return 1

    text = match.group(1)
    for entity, char in (("&quot;", '"'), ("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">")):
        text = text.replace(entity, char)
    data = json.loads(text)

    print(f"视口宽 {data['viewport']}px，文档实际宽 {data['scrollWidth']}px")
    if data["scrollWidth"] <= data["viewport"] + 1:
        print("[OK] 没有横向溢出")
        return 0

    print(f"[FAIL] 横向溢出 {data['scrollWidth'] - data['viewport']}px，超宽元素：")
    print(f"{'元素':<58} {'宽':>6} {'右边界':>7}")
    for item in data["offenders"]:
        print(f"{item['sel'][:56]:<58} {item['w']:>6} {item['right']:>7}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
