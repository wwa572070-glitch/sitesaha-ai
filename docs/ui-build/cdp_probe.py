"""用 CDP 在真实浏览器里测量布局几何，并支持真正的移动端视口。

为什么不用别的方法：
  · --window-size 在 Windows 无头 Edge 上有最小尺寸（约 492x705），低于它会被
    缩放而不是真正缩小视口 —— 于是「390x844 截图」其实是 492px 布局被压扁，
    看起来像文字被裁，实际是压缩。这个坑踩了两次。
  · body 上有 overflow-x:hidden，超宽内容被静默裁掉，滚动条检测看不见。
  · file:// + iframe 读不了 http:// 的 contentDocument（跨源）。

用 Emulation.setDeviceMetricsOverride 才能真正设定 390x844 视口。

用法：
    python cdp_probe.py --width 390 --height 844 --view home
    python cdp_probe.py --width 1440 --height 900 --view learn
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
NODE = r"C:\Users\sht18\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\node\bin\node.exe"

MEASURE_JS = r"""
(() => {
  const de = document.documentElement;
  const out = {
    viewport: {
      innerWidth: window.innerWidth, innerHeight: window.innerHeight,
      clientWidth: de.clientWidth, scrollWidth: de.scrollWidth,
      bodyScrollWidth: document.body.scrollWidth,
      mq640: window.matchMedia('(max-width: 640px)').matches,
      mq992: window.matchMedia('(max-width: 992px)').matches,
      dpr: window.devicePixelRatio,
    },
    elements: [], selfOverflow: [], clipped: [],
  };
  const sels = ['body', 'header', '.header-inner', 'nav', '.nav-inner', 'main',
                '#home', '#ask', '#sos', '#pre', '#learn',
                '.tier-l1', '.tier-l2', '.tier-l3', '.tier-l4', '.tier-l5',
                '.tier-l1 h2', '.l1-foot', '.role-chips', '.todo-item', 'footer'];
  for (const sel of sels) {
    const el = document.querySelector(sel);
    if (!el) { out.elements.push({ sel, missing: true }); continue; }
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    out.elements.push({
      sel, left: Math.round(r.left), right: Math.round(r.right),
      width: Math.round(r.width), height: Math.round(r.height),
      padL: cs.paddingLeft, padR: cs.paddingRight,
      maxW: cs.maxWidth, display: cs.display,
      scrollW: el.scrollWidth, clientW: el.clientWidth,
      visible: !el.hidden && cs.display !== 'none' && r.height > 0,
    });
  }
  for (const el of document.querySelectorAll('*')) {
    if (el.scrollWidth > el.clientWidth + 1 && el.clientWidth > 0) {
      const cs = getComputedStyle(el);
      out.selfOverflow.push({
        tag: el.tagName.toLowerCase(), id: el.id || '',
        cls: String(el.className || '').split(' ').slice(0, 2).join('.'),
        scrollW: el.scrollWidth, clientW: el.clientWidth, overflowX: cs.overflowX,
        text: (el.textContent || '').trim().slice(0, 28),
      });
    }
  }
  out.selfOverflow = out.selfOverflow.slice(0, 20);
  const limit = de.clientWidth;
  for (const el of document.querySelectorAll('*')) {
    const r = el.getBoundingClientRect();
    if (r.width === 0 && r.height === 0) continue;
    if (r.right > limit + 1 || r.left < -1) {
      const cs = getComputedStyle(el);
      if (cs.position === 'fixed') continue;
      out.clipped.push({
        tag: el.tagName.toLowerCase(), id: el.id || '',
        cls: String(el.className || '').split(' ').slice(0, 2).join('.'),
        left: Math.round(r.left), right: Math.round(r.right), width: Math.round(r.width),
        text: (el.textContent || '').trim().slice(0, 28),
      });
    }
  }
  out.clipped = out.clipped.slice(0, 20);
  return out;
})()
"""

CDP_DRIVER = r"""
import fs from 'node:fs';

const wsUrl = process.argv[2];
const width = Number(process.argv[3]);
const height = Number(process.argv[4]);
const mobile = process.argv[5] === 'mobile';
const exprFile = process.argv[6];

const ws = new WebSocket(wsUrl);
let id = 0;
const pending = new Map();

function call(method, params) {
  return new Promise((resolve, reject) => {
    const myId = ++id;
    pending.set(myId, { resolve, reject });
    ws.send(JSON.stringify({ id: myId, method, params: params || {} }));
  });
}

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  if (msg.id && pending.has(msg.id)) {
    const { resolve, reject } = pending.get(msg.id);
    pending.delete(msg.id);
    if (msg.error) reject(new Error(JSON.stringify(msg.error)));
    else resolve(msg.result);
  }
};

ws.onerror = () => { console.error('WS error'); process.exit(1); };

ws.onopen = async () => {
  try {
    await call('Emulation.setDeviceMetricsOverride', {
      width, height,
      deviceScaleFactor: mobile ? 3 : 1,
      mobile,
      screenWidth: width,
      screenHeight: height,
    });
    await new Promise((r) => setTimeout(r, 2500));
    const res = await call('Runtime.evaluate', {
      expression: fs.readFileSync(exprFile, 'utf8'),
      returnByValue: true,
      awaitPromise: true,
    });
    console.log(JSON.stringify(res));
    ws.close();
    process.exit(0);
  } catch (err) {
    console.error('CDP 失败: ' + err.message);
    process.exit(1);
  }
};

setTimeout(() => { console.error('timeout'); process.exit(1); }, 40000);
"""


def cdp_targets(port: int) -> list[dict]:
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--width", type=int, default=390)
    parser.add_argument("--height", type=int, default=844)
    parser.add_argument("--view", default="home")
    parser.add_argument("--theme", default="light")
    parser.add_argument("--base", default="http://127.0.0.1:8504/")
    parser.add_argument("--port", type=int, default=9345)
    args = parser.parse_args()

    profile = Path(tempfile.gettempdir()) / f"_cdp{args.port}"
    shutil.rmtree(profile, ignore_errors=True)
    profile.mkdir(parents=True, exist_ok=True)

    url = f"{args.base}?theme={args.theme}&view={args.view}"
    # 开一个明显大于最小尺寸的窗口，再用 Emulation 覆盖到目标视口
    proc = subprocess.Popen(
        [EDGE, "--headless=new", "--disable-gpu", "--no-sandbox", "--disable-extensions",
         f"--remote-debugging-port={args.port}", f"--user-data-dir={profile}",
         "--window-size=1200,900", "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        ws_url = None
        for _ in range(40):
            time.sleep(0.5)
            try:
                for target in cdp_targets(args.port):
                    if target.get("type") == "page":
                        ws_url = target["webSocketDebuggerUrl"]
                        break
            except Exception:
                continue
            if ws_url:
                break
        if not ws_url:
            print("[FAIL] 拿不到 CDP 目标")
            return 1

        expr_file = Path(tempfile.gettempdir()) / f"_cdpexpr_{args.port}.js"
        expr_file.write_text(MEASURE_JS, encoding="utf-8")
        driver_file = Path(tempfile.gettempdir()) / f"_cdpdrv_{args.port}.mjs"
        driver_file.write_text(CDP_DRIVER, encoding="utf-8")

        # 先导航到页面：用 Page.navigate 通过同一个连接不太好做，
        # 改为让 Edge 直接打开目标页（下面重启进程时带上 URL）。
        proc.terminate()
        try:
            proc.wait(timeout=8)
        except Exception:
            proc.kill()

        mobile = args.width <= 480
        proc = subprocess.Popen(
            [EDGE, "--headless=new", "--disable-gpu", "--no-sandbox", "--disable-extensions",
             f"--remote-debugging-port={args.port}", f"--user-data-dir={profile}",
             "--window-size=1200,900", url],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        ws_url = None
        for _ in range(40):
            time.sleep(0.5)
            try:
                for target in cdp_targets(args.port):
                    if target.get("type") == "page" and "127.0.0.1" in target.get("url", ""):
                        ws_url = target["webSocketDebuggerUrl"]
                        break
            except Exception:
                continue
            if ws_url:
                break
        if not ws_url:
            print("[FAIL] 拿不到页面目标")
            return 1

        result = subprocess.run(
            [NODE, str(driver_file), ws_url, str(args.width), str(args.height),
             "mobile" if mobile else "desktop", str(expr_file)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90,
        )
        if result.returncode != 0:
            print("[FAIL] CDP 求值失败")
            print((result.stderr or "")[-400:])
            return 1
        payload = json.loads(result.stdout.strip())
        data = payload.get("result", {}).get("value")
        if not data:
            print("[FAIL] 无返回数据")
            print(json.dumps(payload)[:400])
            return 1

        vp = data["viewport"]
        print(f"=== 视口 @ {args.view}  请求 {args.width}x{args.height} ===")
        for key, value in vp.items():
            print(f"  {key:<18} {value}")
        print()
        print(f"{'选择器':<16} {'L':>6} {'R':>6} {'W':>6} {'padL/R':>13} {'maxW':>8} {'disp':>7} {'可视':>5}")
        print("-" * 86)
        for item in data["elements"]:
            if item.get("missing"):
                print(f"{item['sel']:<16} 不存在")
                continue
            print(f"{item['sel']:<16} {item['left']:>6} {item['right']:>6} {item['width']:>6} "
                  f"{item['padL'] + '/' + item['padR']:>13} {item['maxW']:>8} "
                  f"{item['display']:>7} {'是' if item['visible'] else '否':>5}")
        print()
        if data["clipped"]:
            print(f"=== 越界元素（{len(data['clipped'])} 个，会被 body 的 overflow-x:hidden 裁掉）===")
            for item in data["clipped"]:
                label = item["tag"] + (f"#{item['id']}" if item["id"] else "") + (f".{item['cls']}" if item["cls"] else "")
                print(f"  {label:<38} L={item['left']:>5} R={item['right']:>5} W={item['width']:>5}  {item['text']!r}")
        else:
            print("=== 无越界元素 ===")
        print()
        if data["selfOverflow"]:
            print(f"=== 内容宽于自身的元素（{len(data['selfOverflow'])} 个）===")
            for item in data["selfOverflow"]:
                label = item["tag"] + (f"#{item['id']}" if item["id"] else "") + (f".{item['cls']}" if item["cls"] else "")
                print(f"  {label:<38} scrollW={item['scrollW']:>5} clientW={item['clientW']:>5} "
                      f"overflowX={item['overflowX']:<8} {item['text']!r}")
        else:
            print("=== 无内容溢出元素 ===")
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=8)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    sys.exit(main())
