"""诊断「工种专项风险要点」区块的实际渲染（第 16 轮 v2 用户反馈）。

用户在页面上看到该区块有问题。可能的表现：
  · 未选工种时只剩空标题
  · 选了工种后四项小标题显示成 <svg> 源码
  · 内容为空 / 结构缺失

本脚本在真实浏览器里：先读未选工种态，再模拟选一个工种，再读一次。

用法：python diagnose_role_block.py
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
PORT = 9701

READ_JS = r"""
(() => {
  const out = [];
  const detail = document.getElementById('roleDetail');
  const chips = document.getElementById('roleChips');
  out.push('=== 未选/当前态 ===');
  out.push('roleChips 子元素: ' + (chips ? chips.children.length : 'null'));
  out.push('roleDetail 子元素: ' + (detail ? detail.children.length : 'null'));
  out.push('roleDetail 文本: ' + JSON.stringify((detail ? detail.textContent : '').trim().slice(0, 200)));
  const head = document.querySelector('#roleDetail h4');
  if (head) out.push('第一个 h4 的 innerHTML: ' + JSON.stringify(head.innerHTML.slice(0, 120)));
  const html = detail ? detail.innerHTML : '';
  out.push('roleDetail 含裸 svg 标签文本: ' + (html.indexOf('&lt;svg') >= 0));
  out.push('全页 innerText 含 "<svg": ' + (document.body.innerText.indexOf('<svg') >= 0));
  out.push('全页 innerText 含 "<use": ' + (document.body.innerText.indexOf('<use') >= 0));
  if (document.body.innerText.indexOf('<svg') >= 0) {
    const i = document.body.innerText.indexOf('<svg');
    out.push('  上下文: ' + JSON.stringify(document.body.innerText.slice(Math.max(0, i - 40), i + 90)));
  }
  return out;
})()
"""

SELECT_JS = r"""
(() => {
  const chips = document.querySelectorAll('#roleChips .role-chip');
  if (!chips.length) return '没有工种 chip';
  chips[0].click();
  return '已点击工种: ' + chips[0].textContent.trim();
})()
"""


def targets(port: int) -> list[dict]:
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def run(port: int, ws_url: str, expression: str):
    expr = Path(tempfile.gettempdir()) / f"_diag_{port}.js"
    expr.write_text(expression, encoding="utf-8")
    driver = Path(tempfile.gettempdir()) / f"_diagdrv_{port}.mjs"
    driver.write_text(
        "import fs from 'node:fs';\n"
        "const ws = new WebSocket(process.argv[2]);\n"
        "let id=0; const pend=new Map();\n"
        "function call(m,p){return new Promise((res,rej)=>{const i=++id;"
        "pend.set(i,{res,rej});ws.send(JSON.stringify({id:i,method:m,params:p||{}}));});}\n"
        "ws.onmessage=e=>{const m=JSON.parse(e.data);if(m.id&&pend.has(m.id)){"
        "const{res,rej}=pend.get(m.id);pend.delete(m.id);"
        "m.error?rej(new Error(JSON.stringify(m.error))):res(m.result);}};\n"
        "ws.onopen=async()=>{try{await new Promise(r=>setTimeout(r,2000));\n"
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
        return [f"求值失败: {(result.stderr or '')[-160:]}"]
    payload = json.loads(result.stdout.strip())
    value = payload.get("result", {}).get("value")
    return value if isinstance(value, list) else [str(value)]


def main() -> int:
    profile = Path(tempfile.gettempdir()) / f"_diagprof_{PORT}"
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

        time.sleep(3)
        for line in run(PORT, ws_url, READ_JS):
            print("  " + line)

        print()
        print("=== 点第一个工种 chip 后 ===")
        for line in run(PORT, ws_url, SELECT_JS):
            print("  " + line)
        time.sleep(1.5)
        for line in run(PORT, ws_url, READ_JS):
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
