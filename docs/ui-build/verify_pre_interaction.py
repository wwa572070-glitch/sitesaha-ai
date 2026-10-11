"""实测 §11 前端交互：勾条件 → 生成清单 → 分组渲染（第 16 轮）。

用法：python verify_pre_interaction.py
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
PORT = 9931

CLICK = r"""
(() => {
  const want = ['动火作业', '高温'];
  const clicked = [];
  document.querySelectorAll('.shift-chip').forEach((chip) => {
    if (want.indexOf(chip.textContent.trim()) >= 0) {
      chip.click();
      clicked.push(chip.textContent.trim());
    }
  });
  return 'clicked: ' + clicked.join('、');
})()
"""

READ = r"""
(() => {
  const out = [];
  out.push('shiftBadge = ' + JSON.stringify(
    (document.getElementById('shiftBadge') || {}).textContent));
  out.push('priorityBadge = ' + JSON.stringify(
    (document.getElementById('priorityBadge') || {}).textContent));
  out.push('checkLabel = ' + JSON.stringify(
    (document.getElementById('checkLabel') || {}).textContent));
  const pressed = [];
  document.querySelectorAll('.shift-chip[aria-pressed="true"]').forEach((c) => {
    pressed.push(c.textContent.trim().replace(/\s*✓$/, ''));
  });
  out.push('已选条件 = ' + JSON.stringify(pressed));
  out.push('--- 清单分组 ---');
  document.querySelectorAll('.check-group').forEach((group) => {
    const title = group.querySelector('.check-group-title');
    const note = group.querySelector('.check-group-note');
    const items = group.querySelectorAll('.check-item');
    out.push('  ' + (title ? title.textContent.trim() : '?')
      + ' [' + items.length + ' 条]  ' + (note ? note.textContent.trim() : ''));
  });
  out.push('--- 当班必查的命中理由 ---');
  document.querySelectorAll('.check-tag.is-source').forEach((tag) => {
    out.push('  ' + tag.textContent.trim());
  });
  return out;
})()
"""


def targets(port: int) -> list[dict]:
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def run(port: int, ws_url: str, expression: str):
    expr = Path(tempfile.gettempdir()) / f"_pre_{port}.js"
    expr.write_text(expression, encoding="utf-8")
    driver = Path(tempfile.gettempdir()) / f"_predrv_{port}.mjs"
    driver.write_text(
        "import fs from 'node:fs';\n"
        "const ws = new WebSocket(process.argv[2]);\n"
        "let id=0; const pend=new Map();\n"
        "function call(m,p){return new Promise((res,rej)=>{const i=++id;"
        "pend.set(i,{res,rej});ws.send(JSON.stringify({id:i,method:m,params:p||{}}));});}\n"
        "ws.onmessage=e=>{const m=JSON.parse(e.data);if(m.id&&pend.has(m.id)){"
        "const{res,rej}=pend.get(m.id);pend.delete(m.id);"
        "m.error?rej(new Error(JSON.stringify(m.error))):res(m.result);}};\n"
        "ws.onopen=async()=>{try{await new Promise(r=>setTimeout(r,3200));\n"
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
        return [f"求值失败：{(result.stderr or '')[-200:]}"]
    payload = json.loads(result.stdout.strip())
    value = payload.get("result", {}).get("value")
    return value if isinstance(value, list) else [str(value)]


def main() -> int:
    profile = Path(tempfile.gettempdir()) / f"_preprof_{PORT}"
    shutil.rmtree(profile, ignore_errors=True)
    profile.mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen(
        [EDGE, "--headless=new", "--disable-gpu", "--no-sandbox", "--disable-extensions",
         f"--remote-debugging-port={PORT}", f"--user-data-dir={profile}",
         "--window-size=1400,1000",
         "http://127.0.0.1:8504/?theme=light&view=pre"],
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

        wait = Path(tempfile.gettempdir()) / f"_prewait_{PORT}.mjs"
        wait.write_text(
            "const ws=new WebSocket(process.argv[2]);\n"
            "ws.onopen=()=>setTimeout(()=>{ws.close();process.exit(0);},3200);\n"
            "setTimeout(()=>process.exit(0),8000);\n",
            encoding="utf-8",
        )

        print("=== 初始状态 ===")
        for line in run(PORT, ws_url, READ):
            print("  " + line)

        print()
        print("=== 点击「动火作业」「高温」 ===")
        for line in run(PORT, ws_url, CLICK):
            print("  " + line)
        subprocess.run([NODE, str(wait), ws_url], capture_output=True, timeout=20)

        print()
        print("=== 生成后的状态 ===")
        for line in run(PORT, ws_url, READ):
            print("  " + line)
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=8)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    sys.exit(main())
