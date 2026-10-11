"""实测 §5 五处残留状态（第 16 轮 v2）。

不猜 CSS，直接读运行时几何：谁占了高度、谁可见、谁的内容是空标题。

用法：python probe_residual_state.py
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
PORT = 9801

PROBE = r"""
(() => {
  const out = [];
  const q = (id) => document.getElementById(id);

  function box(id) {
    const el = q(id);
    if (!el) return id + ' = 不存在';
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    return id + ' hidden=' + el.hidden + ' display=' + cs.display
      + ' 尺寸=' + Math.round(r.width) + 'x' + Math.round(r.height)
      + ' 文本=' + JSON.stringify((el.textContent || '').trim().slice(0, 44));
  }

  out.push('=== 1/2 拍照区 ===');
  ['cameraStage', 'cameraVideo', 'photoStage', 'photoPreview',
   'photoProgress', 'photoFacts', 'photoError'].forEach((id) => out.push('  ' + box(id)));

  // 谁在拍照面板里占了高度
  const panel = q('cameraStage') ? q('cameraStage').closest('.panel') : null;
  if (panel) {
    out.push('  拍照面板总高 ' + Math.round(panel.getBoundingClientRect().height));
    panel.querySelectorAll(':scope > *, :scope > * > *').forEach((el) => {
      const r = el.getBoundingClientRect();
      if (r.height > 40) {
        out.push('    占位 ' + Math.round(r.height) + 'px  <' + el.tagName.toLowerCase()
          + ' class="' + (el.className || '') + '" id="' + (el.id || '') + '">');
      }
    });
  }

  out.push('=== 3 录音行 ===');
  out.push('  ' + box('recordingRow'));

  out.push('=== 4 工种专项 ===');
  const detail = q('roleDetail');
  if (detail) {
    const kids = Array.from(detail.children);
    out.push('  roleDetail 子元素 ' + kids.length);
    kids.forEach((k) => {
      const r = k.getBoundingClientRect();
      out.push('    <' + k.tagName.toLowerCase() + ' class="' + (k.className || '')
        + '"> 高 ' + Math.round(r.height) + ' 文本 ' + JSON.stringify((k.textContent || '').trim().slice(0, 40)));
    });
  }
  document.querySelectorAll('#quickList details').forEach((d, i) => {
    out.push('  quickList details[' + i + '] open=' + d.open
      + ' 内部元素 ' + d.querySelectorAll('.quick-button').length
      + ' 文本 ' + JSON.stringify(d.textContent.trim().slice(0, 50)));
  });

  out.push('=== 5 顶栏胶囊 ===');
  ['headerRole', 'modelStatus'].forEach((id) => {
    const el = q(id);
    if (!el) { out.push('  ' + id + ' 不存在'); return; }
    const cs = getComputedStyle(el);
    out.push('  ' + id + ' 文本=' + JSON.stringify(el.textContent.trim())
      + ' display=' + cs.display + ' class=' + el.className
      + ' title=' + JSON.stringify(el.title || ''));
  });

  out.push('=== 可见文本异常检查 ===');
  const txt = document.body.innerText || '';
  ['<svg', '<use', 'undefined', 'NaN', 'Expecting value'].forEach((t) => {
    if (txt.indexOf(t) >= 0) out.push('  命中 ' + JSON.stringify(t));
  });
  out.push('  检查完成');
  return out;
})()
"""


def targets(port: int) -> list[dict]:
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def run(port: int, ws_url: str, expression: str):
    expr = Path(tempfile.gettempdir()) / f"_res_{port}.js"
    expr.write_text(expression, encoding="utf-8")
    driver = Path(tempfile.gettempdir()) / f"_resdrv_{port}.mjs"
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
        return [f"求值失败：{(result.stderr or '')[-160:]}"]
    payload = json.loads(result.stdout.strip())
    value = payload.get("result", {}).get("value")
    return value if isinstance(value, list) else [str(value)]


def main() -> int:
    for view in ("ask", "learn"):
        profile = Path(tempfile.gettempdir()) / f"_resprof_{PORT}_{view}"
        shutil.rmtree(profile, ignore_errors=True)
        profile.mkdir(parents=True, exist_ok=True)
        proc = subprocess.Popen(
            [EDGE, "--headless=new", "--disable-gpu", "--no-sandbox", "--disable-extensions",
             f"--remote-debugging-port={PORT}", f"--user-data-dir={profile}",
             "--window-size=1400,1000",
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
                print(f"[FAIL] {view}：拿不到 CDP 目标")
                continue
            print("=" * 78)
            print(f"视图 {view}")
            print("=" * 78)
            for line in run(PORT, ws_url, PROBE):
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
