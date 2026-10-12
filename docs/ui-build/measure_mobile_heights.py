"""实测手机端页面高度（第 20 轮 §7 第 8 条）。

用 CDP 的 Emulation.setDeviceMetricsOverride 设真实 390×844 视口
（Windows 无头浏览器 --window-size 有最小宽度限制，不可靠）。

用法：python measure_mobile_heights.py
"""

from __future__ import annotations

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
PORT = 9951
VIEWS = ["home", "ask", "pre", "sos", "learn"]
VIEWPORT_H = 844

MEASURE = r"""
(() => {
  const doc = document.documentElement;
  return String(doc.scrollHeight);
})()
"""


def targets(port: int) -> list[dict]:
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def run_driver(ws_url: str, expression: str, mobile: bool) -> str:
    mobile_flag = "true" if mobile else "false"
    expr_file = Path(tempfile.gettempdir()) / f"_mh_{PORT}.js"
    expr_file.write_text(expression, encoding="utf-8")
    driver = Path(tempfile.gettempdir()) / f"_mhdrv_{PORT}.mjs"
    driver.write_text(
        "import fs from 'node:fs';\n"
        "const ws = new WebSocket(process.argv[2]);\n"
        "let id=0; const pend=new Map();\n"
        "function call(m,p){return new Promise((res,rej)=>{const i=++id;"
        "pend.set(i,{res,rej});ws.send(JSON.stringify({id:i,method:m,params:p||{}}));});}\n"
        "ws.onmessage=e=>{const m=JSON.parse(e.data);if(m.id&&pend.has(m.id)){"
        "const{res,rej}=pend.get(m.id);pend.delete(m.id);"
        "m.error?rej(new Error(JSON.stringify(m.error))):res(m.result);}};\n"
        "ws.onopen=async()=>{try{\n"
        "await call('Emulation.setDeviceMetricsOverride',{width:390,height:844,"
        "deviceScaleFactor:3,mobile:" + mobile_flag + "});\n"
        "await new Promise(r=>setTimeout(r,2500));\n"
        "const r=await call('Runtime.evaluate',{expression:fs.readFileSync(process.argv[3],'utf8'),"
        "returnByValue:true});console.log(JSON.stringify(r));ws.close();process.exit(0);}\n"
        "catch(e){console.error(e.message);process.exit(1);}};\n"
        "setTimeout(()=>process.exit(1),40000);\n",
        encoding="utf-8",
    )
    result = subprocess.run([NODE, str(driver), ws_url, str(expr_file)],
                            capture_output=True, text=True, encoding="utf-8",
                            errors="replace", timeout=90)
    if result.returncode != 0:
        return f"失败:{(result.stderr or '')[-100:]}"
    payload = json.loads(result.stdout.strip())
    return str(payload.get("result", {}).get("value"))


def main() -> int:
    print("=" * 70)
    print(f"手机端 390×844 实测页面高度（每屏 {VIEWPORT_H}px）")
    print("=" * 70)
    print(f"{'页面':<10}{'CSS 高度':>10}{'屏数':>8}   目标")
    print("-" * 70)

    results: dict[str, int] = {}
    for view in VIEWS:
        profile = Path(tempfile.gettempdir()) / f"_mhprof_{PORT}_{view}"
        shutil.rmtree(profile, ignore_errors=True)
        profile.mkdir(parents=True, exist_ok=True)
        proc = subprocess.Popen(
            [EDGE, "--headless=new", "--disable-gpu", "--no-sandbox",
             "--disable-extensions",
             "--disable-component-extensions-with-background-pages",
             "--disable-default-apps", "--no-first-run", "--no-default-browser-check",
             f"--remote-debugging-port={PORT}", f"--user-data-dir={profile}",
             "--window-size=900,900",
             f"http://127.0.0.1:8504/?theme=light&view={view}"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        try:
            ws_url = None
            for _ in range(40):
                time.sleep(0.5)
                try:
                    for item in targets(PORT):
                        if item.get("type") == "page" and "127.0.0.1" in item.get("url", ""):
                            ws_url = item["webSocketDebuggerUrl"]
                            break
                except Exception:
                    continue
                if ws_url:
                    break
            if not ws_url:
                print(f"{view:<10}{'—':>10}   拿不到目标")
                continue
            raw = run_driver(ws_url, MEASURE, True)
            try:
                height = int(float(raw))
            except ValueError:
                print(f"{view:<10}{raw:>10}")
                continue
            results[view] = height
            screens = height / VIEWPORT_H
            target = 4 if view == "home" else 6
            mark = "达标" if screens <= target else f"超出（目标 ≤{target} 屏）"
            print(f"{view:<10}{height:>10}{screens:>7.1f}   {mark}")
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=8)
            except Exception:
                proc.kill()

    print("-" * 70)
    print("目标：首页 ≤4 屏（约 3400px），其余 ≤6 屏（约 5100px）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
