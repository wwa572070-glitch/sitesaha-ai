"""测量手机端各区块高度，定位该收哪几块（第 20 轮 §3）。

只测 pre 与 learn 两个未达标的页面，按区块列出高度。

用法：python measure_block_heights.py
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
PORT = 9973

MEASURE = r"""
(() => {
  const view = new URLSearchParams(location.search).get('view') || 'home';
  const section = document.getElementById(view);
  if (!section) return ['找不到视图 ' + view];
  const out = [];
  const total = document.documentElement.scrollHeight;
  out.push('页面总高 ' + total + 'px  (' + (total / 844).toFixed(1) + ' 屏)');
  out.push('');
  out.push('区块'.padEnd(34) + '高度'.padStart(8) + '  屏');
  section.querySelectorAll(':scope > *').forEach((el) => {
    const h = Math.round(el.getBoundingClientRect().height);
    if (h < 20) return;
    let name = '';
    const h2 = el.querySelector('h2');
    const sum = el.querySelector(':scope > summary');
    if (sum) name = '[折叠] ';
    if (h2) name += h2.textContent.trim();
    else if (sum) name += sum.textContent.trim();
    else name += el.className || el.tagName.toLowerCase();
    name = name.slice(0, 32);
    out.push(name.padEnd(34) + String(h).padStart(6) + 'px' + (h / 844).toFixed(1).padStart(6));
  });
  return out;
})()
"""


def targets(port: int) -> list[dict]:
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def run(ws_url: str, expression: str) -> list[str]:
    expr = Path(tempfile.gettempdir()) / f"_bh_{PORT}.js"
    expr.write_text(expression, encoding="utf-8")
    driver = Path(tempfile.gettempdir()) / f"_bhdrv_{PORT}.mjs"
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
        "deviceScaleFactor:3,mobile:true});\n"
        "await new Promise(r=>setTimeout(r,3000));\n"
        "const r=await call('Runtime.evaluate',{expression:fs.readFileSync(process.argv[3],'utf8'),"
        "returnByValue:true});console.log(JSON.stringify(r));ws.close();process.exit(0);}\n"
        "catch(e){console.error(e.message);process.exit(1);}};\n"
        "setTimeout(()=>process.exit(1),45000);\n",
        encoding="utf-8",
    )
    result = subprocess.run([NODE, str(driver), ws_url, str(expr)],
                            capture_output=True, text=True, encoding="utf-8",
                            errors="replace", timeout=90)
    if result.returncode != 0:
        return [f"失败：{(result.stderr or '')[-120:]}"]
    payload = json.loads(result.stdout.strip())
    value = payload.get("result", {}).get("value")
    return value if isinstance(value, list) else [str(value)]


def main() -> int:
    for view in ("pre", "learn"):
        profile = Path(tempfile.gettempdir()) / f"_bhprof_{PORT}_{view}"
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
            for _ in range(60):
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
                print(f"### {view}: 拿不到目标")
                continue
            print("=" * 62)
            print(f"### {view}")
            print("=" * 62)
            for line in run(ws_url, MEASURE):
                print("  " + line)
            print()
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=8)
            except Exception:
                proc.kill()
    return 0


if __name__ == "__main__":
    sys.exit(main())
