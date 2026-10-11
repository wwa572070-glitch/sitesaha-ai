"""截图并裁出工种专项对照区（第 16 轮 §7 方向 5 验证）。

需要先点一个工种 chip 才会渲染对照区，所以这里用 CDP 点击后再截。

用法：python shot_role_compare.py
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
PORT = 9901
OUT = Path(__file__).resolve().parent / "evidence" / "_role_compare.png"

CLICK = r"""
(() => {
  const chips = document.querySelectorAll('#roleChips .role-chip');
  if (!chips.length) return 'no chips';
  chips[0].click();
  return 'clicked ' + chips[0].textContent.trim();
})()
"""

MEASURE = r"""
(() => {
  const out = [];
  const cmp = document.querySelector('.role-compare');
  if (!cmp) { out.push('role-compare 不存在'); return out; }
  const r = cmp.getBoundingClientRect();
  out.push('对照区尺寸 ' + Math.round(r.width) + 'x' + Math.round(r.height));
  cmp.querySelectorAll('.role-compare-col').forEach((col) => {
    const cr = col.getBoundingClientRect();
    const head = col.querySelector('.role-compare-head');
    out.push('  ' + (head ? head.textContent.trim() : '?')
      + ' 宽 ' + Math.round(cr.width) + ' 条目 ' + col.querySelectorAll('li').length);
  });
  const chips = document.querySelectorAll('.role-chip');
  out.push('风险/防护标签数 ' + chips.length);
  const rect = cmp.getBoundingClientRect();
  out.push('截图区域 y=' + Math.round(rect.top + window.scrollY));
  return out;
})()
"""


def targets(port: int) -> list[dict]:
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def run(port: int, ws_url: str, expression: str):
    expr = Path(tempfile.gettempdir()) / f"_rc_{port}.js"
    expr.write_text(expression, encoding="utf-8")
    driver = Path(tempfile.gettempdir()) / f"_rcdrv_{port}.mjs"
    driver.write_text(
        "import fs from 'node:fs';\n"
        "const ws = new WebSocket(process.argv[2]);\n"
        "let id=0; const pend=new Map();\n"
        "function call(m,p){return new Promise((res,rej)=>{const i=++id;"
        "pend.set(i,{res,rej});ws.send(JSON.stringify({id:i,method:m,params:p||{}}));});}\n"
        "ws.onmessage=e=>{const m=JSON.parse(e.data);if(m.id&&pend.has(m.id)){"
        "const{res,rej}=pend.get(m.id);pend.delete(m.id);"
        "m.error?rej(new Error(JSON.stringify(m.error))):res(m.result);}};\n"
        "ws.onopen=async()=>{try{await new Promise(r=>setTimeout(r,3000));\n"
        "const r=await call('Runtime.evaluate',{expression:fs.readFileSync(process.argv[3],'utf8'),"
        "returnByValue:true});console.log(JSON.stringify(r));ws.close();process.exit(0);}\n"
        "catch(e){console.error(e.message);process.exit(1);}};\n"
        "setTimeout(()=>process.exit(1),40000);\n",
        encoding="utf-8",
    )
    result = subprocess.run([NODE, str(driver), ws_url, str(expr)],
                            capture_output=True, text=True, encoding="utf-8",
                            errors="replace", timeout=90)
    if result.returncode != 0:
        return [f"求值失败：{(result.stderr or '')[-160:]}"]
    payload = json.loads(result.stdout.strip())
    value = payload.get("result", {}).get("value")
    return value if isinstance(value, list) else [str(value)]


def main() -> int:
    profile = Path(tempfile.gettempdir()) / f"_rcprof_{PORT}"
    shutil.rmtree(profile, ignore_errors=True)
    profile.mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen(
        [EDGE, "--headless=new", "--disable-gpu", "--no-sandbox", "--disable-extensions",
         f"--remote-debugging-port={PORT}", f"--user-data-dir={profile}",
         "--window-size=1400,1000",
         "http://127.0.0.1:8504/?theme=light&view=learn"],
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
            print("[FAIL] 拿不到 CDP 目标")
            return 1

        time.sleep(2)
        for line in run(PORT, ws_url, CLICK):
            print("  " + line)
        time.sleep(1.5)
        for line in run(PORT, ws_url, MEASURE):
            print("  " + line)

        # 用 CDP 截图（限制高度，避免超长）
        shot = Path(tempfile.gettempdir()) / f"_rcshot_{PORT}.mjs"
        shot.write_text(
            "import fs from 'node:fs';\n"
            "const ws = new WebSocket(process.argv[2]);\n"
            "let id=0; const pend=new Map();\n"
            "function call(m,p){return new Promise((res,rej)=>{const i=++id;"
            "pend.set(i,{res,rej});ws.send(JSON.stringify({id:i,method:m,params:p||{}}));});}\n"
            "ws.onmessage=e=>{const m=JSON.parse(e.data);if(m.id&&pend.has(m.id)){"
            "const{res,rej}=pend.get(m.id);pend.delete(m.id);"
            "m.error?rej(new Error(JSON.stringify(m.error))):res(m.result);}};\n"
            "ws.onopen=async()=>{try{\n"
            "await call('Emulation.setDeviceMetricsOverride',{width:1400,height:1000,"
            "deviceScaleFactor:1,mobile:false});\n"
            "await call('Runtime.evaluate',{expression:"
            "\"document.querySelector('.role-compare').scrollIntoView({block:'center'})\"});\n"
            "await new Promise(r=>setTimeout(r,600));\n"
            "const r=await call('Page.captureScreenshot',{format:'png'});\n"
            "fs.writeFileSync(process.argv[3],Buffer.from(r.data,'base64'));\n"
            "ws.close();process.exit(0);}catch(e){console.error(e.message);process.exit(1);}};\n"
            "setTimeout(()=>process.exit(1),40000);\n",
            encoding="utf-8",
        )
        result = subprocess.run([NODE, str(shot), ws_url, str(OUT)],
                                capture_output=True, text=True, encoding="utf-8",
                                errors="replace", timeout=90)
        if result.returncode == 0 and OUT.is_file():
            print(f"  [ok] 截图 {OUT.name} {OUT.stat().st_size // 1024} KB")
        else:
            print(f"  [FAIL] 截图失败 {(result.stderr or '')[-120:]}")
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=8)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    sys.exit(main())
