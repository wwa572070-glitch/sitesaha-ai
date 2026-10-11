"""给全部 5 个页面截图。

之前只截首页，因为视图切换是按钮点击驱动的（`showView`），`#hash` 不生效。
本脚本在页面里注入一段驱动代码：按 URL 的 ?view= 参数直接调用 showView 切页。

用法：
    python shot_pages.py                  # 全部页面，白天
    python shot_pages.py --theme dark     # 全部页面，夜间
    python shot_pages.py --only ask       # 只截一个页面
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

BUILD = Path(__file__).resolve().parent
OUT = BUILD / "_shot"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

PAGES = {
    "home": "首页",
    "ask": "问安全",
    "sos": "应急处置",
    "pre": "班前准备",
    "learn": "学习与资料",
}

# 页面内驱动代码：读 ?view= 并**点击对应导航按钮**来切页。
# 不要试图直接调 showView —— 它在 IIFE 里，外部访问不到；
# 也不要用改 class 的退化路径 —— 脚本内部状态（currentView 等）不会跟着更新。
DRIVER = """
<script>
(function () {
  var m = /[?&]view=([a-z]+)/.exec(location.search || "");
  if (!m) return;
  var name = m[1];
  var tabs = document.querySelectorAll(".nav-button");
  for (var i = 0; i < tabs.length; i++) {
    if (tabs[i].getAttribute("data-view") === name) {
      tabs[i].click();
      break;
    }
  }
  var sec = document.getElementById(name);
  // 把结果写进 title，截图后可用 --dump-dom 回读，确认切页真的发生了
  document.title = "READY:" + name + ":" +
    (sec && sec.classList.contains("active") ? "active" : "FAILED");
})();
</script>
"""


def build_page(html: str) -> str:
    """把驱动代码插到 </body> 之前，返回可直接打开的页面。"""
    index = html.rfind("</body>")
    if index < 0:
        return html
    return html[:index] + DRIVER + html[index:]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--theme", choices=["light", "dark"], default="light")
    parser.add_argument("--only", default="")
    parser.add_argument("--base", default="http://127.0.0.1:8504/")
    parser.add_argument("--width", type=int, default=1440)
    parser.add_argument("--height", type=int, default=2000)
    args = parser.parse_args()

    names = [args.only] if args.only else list(PAGES)
    OUT.mkdir(parents=True, exist_ok=True)

    # 直接走 HTTP，不用 file:// —— 后者跨源会把 /api/* 全部拦掉，
    # 于是页面只剩骨架屏和「读取失败」，看起来像渲染问题，其实是 CORS。
    # 切页由页面自身的 ?view= 深链支持（见 index_script_a.js 的 deepLinkView）。
    ok = 0
    for name in names:
        if name not in PAGES:
            print(f"[skip] 未知页面 {name}")
            continue
        url = f"{args.base}?theme={args.theme}&view={name}"
        target = OUT / f"page-{args.theme}-{name}.png"
        target.unlink(missing_ok=True)
        profile = Path(tempfile.gettempdir()) / f"_pgprof_{args.theme}_{name}"
        shutil.rmtree(profile, ignore_errors=True)
        profile.mkdir(parents=True, exist_ok=True)

        subprocess.run(
            [
                EDGE, "--headless=new", "--disable-gpu", "--no-sandbox",
                "--hide-scrollbars", "--disable-extensions",
                f"--user-data-dir={profile}",
                f"--window-size={args.width},{args.height}",
                f"--screenshot={target}",
                "--virtual-time-budget=9000",
                url,
            ],
            capture_output=True, text=True, timeout=200,
        )
        if target.is_file() and target.stat().st_size > 5000:
            print(f"[ok] {PAGES[name]:<8} {args.theme:<5} {target.stat().st_size // 1024:>4} KB  {target.name}")
            ok += 1
        else:
            print(f"[FAIL] {name} 截图未生成")

    print(f"\n完成 {ok}/{len(names)} 张，目录：{OUT}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
