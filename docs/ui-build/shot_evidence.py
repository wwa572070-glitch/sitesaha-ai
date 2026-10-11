"""按指令 §5 规范截图：桌面 1440×900、手机 390×844，用 CDP 设定真实视口。

为什么必须用 CDP：
  Windows 无头 Edge 的 --window-size 有最小尺寸（约 492x705），低于它会被缩放
  而不是真正缩小视口。于是「390x844 截图」其实是 492px 布局被压扁成 390px，
  文字看起来被裁切，实际是横向压缩 —— 这个假象误导了两轮排查。
  用 Emulation.setDeviceMetricsOverride 才能得到真实 390px 布局。

用法：
    python shot_evidence.py                    # 全部视图 × 桌面 + 手机
    python shot_evidence.py --view home
    python shot_evidence.py --theme dark
"""

from __future__ import annotations

import argparse
import base64
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
BUILD = Path(__file__).resolve().parent
OUT = BUILD / "evidence"

VIEWS = ["home", "ask", "sos", "pre", "learn"]
VIEW_NAMES = {"home": "首页", "ask": "问安全", "sos": "应急处置",
              "pre": "班前准备", "learn": "学习与资料"}
PROFILES = {"desktop": (1440, 900), "mobile": (390, 844)}

DRIVER = r"""
import fs from 'node:fs';

const wsUrl = process.argv[2];
const width = Number(process.argv[3]);
const height = Number(process.argv[4]);
const mobile = process.argv[5] === 'mobile';
const outPath = process.argv[6];

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
    await new Promise((r) => setTimeout(r, 3000));
    // 量一下文档实际高度，整页截取
    const metrics = await call('Page.getLayoutMetrics');
    const full = Math.ceil(
      (metrics.cssContentSize && metrics.cssContentSize.height) ||
      (metrics.contentSize && metrics.contentSize.height) || height
    );
    const shotHeight = Math.min(full, 6000);
    const shot = await call('Page.captureScreenshot', {
      format: 'png',
      captureBeyondViewport: true,
      clip: { x: 0, y: 0, width, height: shotHeight, scale: 1 },
    });
    fs.writeFileSync(outPath, Buffer.from(shot.data, 'base64'));
    console.log(JSON.stringify({ ok: true, width, height: shotHeight, bytes: fs.statSync(outPath).size }));
    ws.close();
    process.exit(0);
  } catch (err) {
    console.error('CDP 失败: ' + err.message);
    process.exit(1);
  }
};

setTimeout(() => { console.error('timeout'); process.exit(1); }, 60000);
"""


def targets(port: int) -> list[dict]:
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def shoot(view: str, theme: str, kind: str, base: str, port: int) -> bool:
    width, height = PROFILES[kind]
    target = OUT / f"{kind}-{view}.png"
    target.unlink(missing_ok=True)
    profile = Path(tempfile.gettempdir()) / f"_shot{port}"
    shutil.rmtree(profile, ignore_errors=True)
    profile.mkdir(parents=True, exist_ok=True)

    url = f"{base}?theme={theme}&view={view}"
    proc = subprocess.Popen(
        [EDGE, "--headless=new", "--disable-gpu", "--no-sandbox", "--disable-extensions",
         f"--remote-debugging-port={port}", f"--user-data-dir={profile}",
         "--window-size=1400,1000", url],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        ws_url = None
        for _ in range(40):
            time.sleep(0.5)
            try:
                for item in targets(port):
                    if item.get("type") == "page" and "127.0.0.1" in item.get("url", ""):
                        ws_url = item["webSocketDebuggerUrl"]
                        break
            except Exception:
                continue
            if ws_url:
                break
        if not ws_url:
            print(f"  [FAIL] {view} {kind}: 拿不到 CDP 目标")
            return False

        driver = Path(tempfile.gettempdir()) / f"_shotdrv_{port}.mjs"
        driver.write_text(DRIVER, encoding="utf-8")
        result = subprocess.run(
            [NODE, str(driver), ws_url, str(width), str(height), kind, str(target)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
        )
        if result.returncode != 0 or not target.is_file():
            print(f"  [FAIL] {view} {kind}: {(result.stderr or '')[-160:]}")
            return False
        info = json.loads(result.stdout.strip())
        print(f"  [ok] {VIEW_NAMES[view]:<8} {kind:<8} {info['width']}x{info['height']}  "
              f"{info['bytes'] // 1024:>4} KB  {target.name}")
        return True
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=8)
        except Exception:
            proc.kill()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--view", default="")
    parser.add_argument("--theme", default="light")
    parser.add_argument("--kind", default="", choices=["", "desktop", "mobile"])
    parser.add_argument("--base", default="http://127.0.0.1:8504/")
    args = parser.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    views = [args.view] if args.view else VIEWS
    kinds = [args.kind] if args.kind else list(PROFILES)
    print(f"截图主题 {args.theme}，输出 {OUT}")
    ok = 0
    total = 0
    port = 9360
    for view in views:
        for kind in kinds:
            total += 1
            if shoot(view, args.theme, kind, args.base, port):
                ok += 1
            port += 1
    print(f"\n完成 {ok}/{total}")
    return 0 if ok == total else 1


if __name__ == "__main__":
    sys.exit(main())
