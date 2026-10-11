"""量化当前页面的"工程指标"，与成熟平台对标时用得上。

对标维度：
  · 首屏在 1440x900（笔记本常见分辨率）里能看到什么、看不到什么
  · HTML 体积（含内联样式脚本）——影响首屏速度
  · 可交互元素数量与密度
  · CSS 规则条数、设计令牌数量、字号种类
  · 无障碍基础项（landmark、标题层级、alt、表单标签）

用法：python benchmark_page.py
"""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path

BUILD = Path(__file__).resolve().parent
REPO = BUILD.parent.parent
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

MEASURE = r"""
<script>
(function () {
  function run() {
    var vh = window.innerHeight, vw = window.innerWidth;
    var firstScreen = [];
    var all = document.querySelectorAll("body *");
    for (var i = 0; i < all.length; i++) {
      var el = all[i];
      if (!el.getBoundingClientRect) continue;
      var r = el.getBoundingClientRect();
      if (r.height < 8 || r.width < 8) continue;
      if (r.top >= 0 && r.bottom <= vh && r.width > 120) {
        var tag = el.tagName.toLowerCase();
        if (["section","div","header","nav","main","aside","form"].indexOf(tag) < 0) continue;
        var r2 = el.getBoundingClientRect();
        var childBoxes = 0;
        for (var j = 0; j < el.children.length; j++) {
          var cr = el.children[j].getBoundingClientRect();
          if (cr.height > 24) childBoxes++;
        }
        if (childBoxes > 0) {
          var id = el.id ? "#" + el.id : "";
          var cls = typeof el.className === "string" && el.className.trim()
            ? "." + el.className.trim().split(/\s+/).slice(0,2).join(".") : "";
          firstScreen.push({ sel: tag + id + cls, h: Math.round(r.height), top: Math.round(r.top) });
        }
      }
    }
    var seen = {};
    firstScreen = firstScreen.filter(function (x) { if (seen[x.sel]) return false; seen[x.sel] = 1; return true; });
    var doc = document.documentElement;
    var out = {
      viewport: vw + "x" + vh,
      docHeight: doc.scrollHeight,
      screens: Math.round(doc.scrollHeight / vh * 10) / 10,
      firstScreenBlocks: firstScreen.slice(0, 14)
    };
    var pre = document.createElement("pre");
    pre.id = "__bench__";
    pre.textContent = JSON.stringify(out);
    document.body.appendChild(pre);
  }
  if (document.readyState === "complete") setTimeout(run, 500);
  else window.addEventListener("load", function () { setTimeout(run, 500); });
})();
</script>
"""


def main() -> int:
    sys.path.insert(0, str(REPO))
    import webapp  # noqa: PLC0415

    html = webapp.INDEX_HTML
    print("=" * 66)
    print("一、体积（对标：单页应用首屏 HTML 通常 < 60KB）")
    print("=" * 66)
    total_kb = len(html.encode("utf-8")) / 1024
    css = re.findall(r"<style>(.*?)</style>", html, re.S)
    js = re.findall(r"<script>(.*?)</script>", html, re.S)
    css_kb = sum(len(x.encode()) for x in css) / 1024
    js_kb = sum(len(x.encode()) for x in js) / 1024
    dom_kb = total_kb - css_kb - js_kb
    print(f"  总 HTML      {total_kb:8.1f} KB")
    print(f"  ├ 内联 CSS   {css_kb:8.1f} KB  ({css_kb / total_kb * 100:.0f}%)")
    print(f"  ├ 内联 JS    {js_kb:8.1f} KB  ({js_kb / total_kb * 100:.0f}%)")
    print(f"  └ DOM 结构   {dom_kb:8.1f} KB  ({dom_kb / total_kb * 100:.0f}%)")

    print()
    print("=" * 66)
    print("二、设计系统复杂度（对标：成熟系统通常 20~40 个令牌、≤6 档字号）")
    print("=" * 66)
    css_all = "\n".join(css)
    tokens = set(re.findall(r"(--[\w-]+)\s*:", css_all))
    root_blocks = re.findall(r":root\s*\{(.*?)\}", css_all, re.S)
    root_tokens = set()
    for block in root_blocks:
        root_tokens |= set(re.findall(r"(--[\w-]+)\s*:", block))
    sizes = sorted({float(x) for x in re.findall(r"font-size:\s*([\d.]+)px", css_all)})
    colors = set(x.lower() for x in re.findall(r"#[0-9a-fA-F]{6}\b", css_all))
    rules = len(re.findall(r"[^{}]+\{[^{}]*\}", css_all))
    important = len(re.findall(r"!important", css_all))
    media = len(re.findall(r"@media", css_all))
    print(f"  设计令牌总数        {len(tokens)}")
    print(f"  ├ :root 定义        {len(root_tokens)}")
    print(f"  └ 其余为局部变量")
    print(f"  字号档数            {len(sizes)}   {sizes}")
    print(f"  十六进制颜色数      {len(colors)}")
    print(f"  CSS 规则条数        {rules}")
    print(f"  !important 次数     {important}")
    print(f"  媒体查询数          {media}")

    print()
    print("=" * 66)
    print("三、页面结构")
    print("=" * 66)
    print(f"  <section> 数        {len(re.findall(r'<section', html))}")
    print(f"  .panel 数           {len(re.findall(r'class=.panel', html))}")
    print(f"  按钮数              {len(re.findall(r'<button', html))}")
    print(f"  <input>/<textarea>  {len(re.findall(r'<input|<textarea', html))}")
    headings = re.findall(r"<h([1-6])", html)
    from collections import Counter
    print(f"  标题层级分布        {dict(sorted(Counter(headings).items()))}")
    print(f"  aria-label/role 数  {len(re.findall(r'aria-label=|role=', html))}")
    print(f"  alt 属性数          {len(re.findall(r'alt=', html))}")

    print()
    print("=" * 66)
    print("四、首屏（1440x900）实际能看到的块")
    print("=" * 66)
    patched = html.replace("</body>", MEASURE + "</body>")
    tmp = Path(tempfile.gettempdir()) / "_bench.html"
    tmp.write_text(patched, encoding="utf-8")
    result = subprocess.run(
        [
            EDGE, "--headless=new", "--disable-gpu", "--no-sandbox",
            "--disable-extensions", "--window-size=1440,900",
            "--virtual-time-budget=7000", "--dump-dom", tmp.as_uri(),
        ],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180,
    )
    match = re.search(r'<pre id="__bench__">(.*?)</pre>', result.stdout or "", re.S)
    if not match:
        print("  （本地文件方式拿不到测量结果，属正常：页面需要服务端接口）")
        return 0
    import json
    text = match.group(1)
    for entity, char in (("&quot;", '"'), ("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">")):
        text = text.replace(entity, char)
    data = json.loads(text)
    print(f"  视口 {data['viewport']}")
    print(f"  整页高度 {data['docHeight']}px ≈ {data['screens']} 屏")
    print(f"  首屏内可见的内容块 {len(data['firstScreenBlocks'])} 个：")
    for item in data["firstScreenBlocks"]:
        print(f"    top={item['top']:>4}  高={item['h']:>4}  {item['sel'][:52]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
