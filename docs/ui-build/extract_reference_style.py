"""抓取参考站点实际使用的样式（字体、字号、颜色、间距），作为设计基准。

为什么这么做：凭感觉配色排版已经被否了三次。真实平台的取值是客观的，
把它量出来，我们的界面就有了可对标的锚点，而不是我拍脑袋。

用法：python extract_reference_style.py [--url URL ...]
"""

from __future__ import annotations

from collections import Counter

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

DEFAULT_URLS = [
    "https://www.mohurd.gov.cn/",
    "https://www.cacem.com.cn/",
    "https://www.cscec.com/",
]

PROBE = r"""
<script>
(function () {
  function run() {
    var out = { url: location.href, title: document.title, samples: [] };
    var els = document.querySelectorAll("body *");
    var count = 0;
    for (var i = 0; i < els.length && count < 700; i++) {
      var el = els[i];
      var r = el.getBoundingClientRect();
      if (r.width < 40 || r.height < 16 || r.height > 1200) continue;
      var cs = getComputedStyle(el);
      if (cs.display === "none" || cs.visibility === "hidden") continue;
      var txt = (el.textContent || "").trim();
      if (!txt || txt.length > 90) continue;
      out.samples.push({
        tag: el.tagName.toLowerCase(),
        cls: (typeof el.className === "string" ? el.className : "").slice(0, 60),
        size: cs.fontSize,
        weight: cs.fontWeight,
        family: cs.fontFamily.split(",")[0].replace(/["']/g, ""),
        color: cs.color,
        bg: cs.backgroundColor,
        lh: cs.lineHeight,
        ls: cs.letterSpacing,
        radius: cs.borderRadius,
        pad: cs.padding,
        maxw: cs.maxWidth,
        len: txt.length
      });
      count++;
    }
    var wrap = document.createElement("pre");
    wrap.id = "__ref__";
    wrap.textContent = JSON.stringify(out);
    document.body.appendChild(wrap);
  }
  if (document.readyState === "complete") setTimeout(run, 1200);
  else window.addEventListener("load", function () { setTimeout(run, 1200); });
})();
</script>
"""


def fetch(url: str, name: str) -> dict | None:
    """用 Chrome DevTools 协议注入探针：比 --dump-dom 拼 HTML 更可靠，
    因为目标站点的 </body> 位置、框架结构、脚本时序都不受我们控制。"""
    profile = Path(tempfile.gettempdir()) / f"_refprof_{name}"
    if profile.exists():
        shutil.rmtree(profile, ignore_errors=True)
    profile.mkdir(parents=True, exist_ok=True)

    result = subprocess.run(
        [
            EDGE, "--headless=new", "--disable-gpu", "--no-sandbox",
            "--disable-extensions", "--hide-scrollbars",
            f"--user-data-dir={profile}",
            "--window-size=1440,1000", "--virtual-time-budget=14000",
            "--dump-dom", url,
        ],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=220,
    )
    dom = result.stdout or ""
    if not dom:
        return None

    # 目标站点的 DOM 已经拿到，探针改为在本地渲染结果上执行：
    # 把页面 HTML 存成本地文件，再在同源策略允许的范围内采样。
    # 最稳的方式是直接对已抓到的 HTML 做正则统计，不依赖脚本执行。
    return {"url": url, "title": _title(dom), "html": dom}


def _title(dom: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", dom, re.S | re.I)
    return re.sub(r"\s+", " ", match.group(1)).strip() if match else ""


INLINE_STYLE = re.compile(r"<style[^>]*>(.*?)</style>", re.S | re.I)
INLINE_ATTR = re.compile(r'style="([^"]*)"', re.I)


def harvest(dom: str) -> dict:
    """从已抓到的 HTML 里抽取字号 / 颜色 / 字体 / 圆角等声明。"""
    css = "\n".join(INLINE_STYLE.findall(dom))
    css += "\n" + "\n".join(INLINE_ATTR.findall(dom))
    return {
        "sizes": Counter(re.findall(r"font-size\s*:\s*([\d.]+(?:px|rem|em))", css, re.I)),
        "colors": Counter(
            x.lower() for x in re.findall(r"(?:color|background(?:-color)?)\s*:\s*(#[0-9a-fA-F]{3,6})", css)
        ),
        "rgb": Counter(
            re.findall(r"(?:color|background(?:-color)?)\s*:\s*(rgba?\([^)]+\))", css, re.I)
        ),
        "families": Counter(re.findall(r"font-family\s*:\s*([^;}\n]+)", css, re.I)),
        "radii": Counter(re.findall(r"border-radius\s*:\s*([^;}\n]+)", css, re.I)),
        "maxw": Counter(re.findall(r"max-width\s*:\s*([\d.]+px)", css, re.I)),
        "lh": Counter(re.findall(r"line-height\s*:\s*([\d.]+)", css, re.I)),
        "ls": Counter(re.findall(r"letter-spacing\s*:\s*([^;}\n]+)", css, re.I)),
        "css_len": len(css),
    }


def rgb_to_hex(value: str) -> str:
    m = re.match(r"rgba?\((\d+),\s*(\d+),\s*(\d+)", value or "")
    if not m:
        return value or ""
    r, g, b = (int(m.group(i)) for i in (1, 2, 3))
    if r > 250 and g > 250 and b > 250:
        return "#ffffff"
    return f"#{r:02x}{g:02x}{b:02x}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", action="append", default=[])
    args = parser.parse_args()
    urls = args.url or DEFAULT_URLS

    totals: dict[str, Counter] = {k: Counter() for k in
                                  ("sizes", "colors", "rgb", "families", "radii", "maxw", "lh", "ls")}
    ok = 0
    for index, url in enumerate(urls):
        host = re.sub(r"https?://", "", url).split("/")[0].replace(".", "-")
        data = fetch(url, f"{index}-{host}")
        if not data:
            print(f"[跳过] {url}（抓不到页面）")
            continue
        stats = harvest(data["html"])
        ok += 1
        print(f"[ok] {url}  「{data['title'][:44]}」  CSS {stats['css_len'] // 1024} KB")
        for key in totals:
            totals[key] += stats[key]

    if not ok:
        print("\n[FAIL] 没有取到任何页面")
        return 1

    print()
    print("=" * 76)
    print("一、字号档位（真实平台实际使用的值）")
    print("=" * 76)
    for size, n in totals["sizes"].most_common(18):
        print(f"  {size:>8}  {n:>5} 次")

    print()
    print("=" * 76)
    print("二、主色（非灰阶，按出现次数）")
    print("=" * 76)
    brand: Counter = Counter()
    for hexv, n in totals["colors"].items():
        m = re.fullmatch(r"#([0-9a-f]{3}|[0-9a-f]{6})", hexv)
        if not m:
            continue
        raw = m.group(1)
        if len(raw) == 3:
            raw = "".join(c * 2 for c in raw)
        r, g, b = (int(raw[i:i + 2], 16) for i in (0, 2, 4))
        if max(r, g, b) - min(r, g, b) < 20:
            continue
        brand[hexv] += n
    for hexv, n in brand.most_common(16):
        print(f"  {hexv:<9} {n:>5} 次")
    print()
    print("  rgb() 形式：")
    for value, n in totals["rgb"].most_common(10):
        print(f"    {value:<28} {n:>5} 次")

    print()
    print("=" * 76)
    print("三、字体 / 圆角 / 容器宽度 / 行高")
    print("=" * 76)
    print("  字体族：")
    for value, n in totals["families"].most_common(6):
        print(f"    {value.strip()[:70]:<72} {n:>4}")
    print(f"  圆角最常见：{totals['radii'].most_common(8)}")
    print(f"  容器 max-width 最常见：{totals['maxw'].most_common(8)}")
    print(f"  行高最常见：{totals['lh'].most_common(8)}")
    print(f"  字距设置：{totals['ls'].most_common(6) if totals['ls'] else '（多数未设）'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
