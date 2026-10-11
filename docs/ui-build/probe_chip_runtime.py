"""读运行时真实的 chip 结构与计算样式（第 16 轮 §7 方向 5 排查）。

前几次都在猜，这次把 DOM 结构、计算样式、规则匹配结果一次性打出来。

用法：python probe_chip_runtime.py
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
PORT = 9921

JS = r"""
(() => {
  const out = [];
  const list = document.querySelector('.role-chip-list');
  out.push('role-chip-list 存在: ' + Boolean(list));
  if (list) {
    const ls = getComputedStyle(list);
    const lr = list.getBoundingClientRect();
    out.push('  标签名 <' + list.tagName.toLowerCase() + '> 尺寸 '
      + Math.round(lr.width) + 'x' + Math.round(lr.height)
      + ' display=' + ls.display + ' flex-wrap=' + ls.flexWrap);
    out.push('  子元素 ' + list.children.length + ' 个');
    const first = list.children[0];
    if (first) {
      const fs = getComputedStyle(first);
      const fr = first.getBoundingClientRect();
      out.push('  第一个子元素 <' + first.tagName.toLowerCase()
        + ' class="' + first.className + '">');
      out.push('    尺寸 ' + Math.round(fr.width) + 'x' + Math.round(fr.height));
      out.push('    display=' + fs.display + ' flex=' + fs.flex
        + ' width=' + fs.width + ' flex-basis=' + fs.flexBasis
        + ' align-self=' + fs.alignSelf);
      out.push('    matches(".role-chip-list .role-chip") = '
        + first.matches('.role-chip-list .role-chip'));
      out.push('    padding=' + fs.padding + ' font-size=' + fs.fontSize);
    }
  }

  // 所有 li.role-chip 的宽度分布
  const all = document.querySelectorAll('.role-chip');
  out.push('--- 全部 .role-chip 的宽度 ---');
  const widths = new Map();
  all.forEach((el) => {
    const w = Math.round(el.getBoundingClientRect().width);
    const key = w + 'px';
    widths.set(key, (widths.get(key) || 0) + 1);
  });
  widths.forEach((count, width) => out.push('  ' + width + ' × ' + count + ' 个'));

  // 具体看 role-chip-list 里的
  if (list) {
    out.push('--- role-chip-list 内的宽度 ---');
    Array.from(list.children).forEach((el, i) => {
      const r = el.getBoundingClientRect();
      out.push('  [' + i + '] ' + Math.round(r.width) + 'px  '
        + JSON.stringify(el.textContent.trim().slice(0, 16)));
    });
  }
  return out;
})()
"""

CLICK = r"""
(() => {
  const chips = document.querySelectorAll('#roleChips .role-chip');
  if (chips.length) chips[0].click();
  return 'clicked ' + chips.length;
})()
"""


def targets(port: int) -> list[dict]:
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def run(port: int, ws_url: str, expression: str):
    expr = Path(tempfile.gettempdir()) / f"_cr_{port}.js"
    expr.write_text(expression, encoding="utf-8")
    driver = Path(tempfile.gettempdir()) / f"_crdrv_{port}.mjs"
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
        return [f"求值失败：{(result.stderr or '')[-200:]}"]
    payload = json.loads(result.stdout.strip())
    value = payload.get("result", {}).get("value")
    return value if isinstance(value, list) else [str(value)]


def main() -> int:
    profile = Path(tempfile.gettempdir()) / f"_crprof_{PORT}"
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
        print("  " + str(run(PORT, ws_url, CLICK)[0]))
        time.sleep(1.5)
        for line in run(PORT, ws_url, JS):
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
