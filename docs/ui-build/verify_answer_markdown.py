"""验证回答正文的 Markdown 渲染（第 16 轮）。

在真实浏览器里问一个问题，读回 .answer-body 的 HTML 与可见文本，
确认：
  · 页面上不再出现 ** 星号
  · 序号被渲染成 <ol><li>
  · 加粗被渲染成 <strong>
  · 没有未转义的 HTML 注入

用法：python verify_answer_markdown.py
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
PORT = 9941

ASK = r"""
(async () => {
  const input = document.getElementById('question');
  if (!input) return 'no input';
  input.value = '高处作业前要检查什么？';
  const button = document.getElementById('askButton');
  if (!button) return 'no button';
  button.click();
  return 'asked';
})()
"""

READ = r"""
(() => {
  const bodies = document.querySelectorAll('.answer-body');
  if (!bodies.length) return ['还没有回答'];
  const last = bodies[bodies.length - 1];
  const out = [];
  const text = last.innerText || '';
  out.push('可见文本长度 ' + text.length);
  out.push('含 ** 星号: ' + (text.indexOf('**') >= 0));
  out.push('含 <svg/<use: ' + (text.indexOf('<svg') >= 0 || text.indexOf('<use') >= 0));
  out.push('段落数 ' + last.querySelectorAll('.answer-line').length);
  out.push('有序列表 ' + last.querySelectorAll('ol.answer-list').length
    + ' / 条目 ' + last.querySelectorAll('ol.answer-list li').length);
  out.push('无序列表 ' + last.querySelectorAll('ul.answer-list').length
    + ' / 条目 ' + last.querySelectorAll('ul.answer-list li').length);
  out.push('加粗标签 ' + last.querySelectorAll('strong').length);
  out.push('--- 前 320 字可见文本 ---');
  out.push(text.slice(0, 320));
  return out;
})()
"""


def targets(port: int) -> list[dict]:
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def run(port: int, ws_url: str, expression: str):
    expr = Path(tempfile.gettempdir()) / f"_md_{port}.js"
    expr.write_text(expression, encoding="utf-8")
    driver = Path(tempfile.gettempdir()) / f"_mddrv_{port}.mjs"
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
        "returnByValue:true,awaitPromise:true});console.log(JSON.stringify(r));"
        "ws.close();process.exit(0);}\n"
        "catch(e){console.error(e.message);process.exit(1);}};\n"
        "setTimeout(()=>process.exit(1),60000);\n",
        encoding="utf-8",
    )
    result = subprocess.run([NODE, str(driver), ws_url, str(expr)],
                            capture_output=True, text=True, encoding="utf-8",
                            errors="replace", timeout=110)
    if result.returncode != 0:
        return [f"求值失败：{(result.stderr or '')[-200:]}"]
    payload = json.loads(result.stdout.strip())
    value = payload.get("result", {}).get("value")
    return value if isinstance(value, list) else [str(value)]


def main() -> int:
    profile = Path(tempfile.gettempdir()) / f"_mdprof_{PORT}"
    shutil.rmtree(profile, ignore_errors=True)
    profile.mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen(
        [EDGE, "--headless=new", "--disable-gpu", "--no-sandbox", "--disable-extensions",
         f"--remote-debugging-port={PORT}", f"--user-data-dir={profile}",
         "--window-size=1400,1000",
         "http://127.0.0.1:8504/?theme=light&view=ask"],
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

        print("=== 提问 ===")
        print("  " + str(run(PORT, ws_url, ASK)[0]))

        # 等回答（模型可能要 10 秒以上）
        print("  等待模型回答…")
        for attempt in range(14):
            time.sleep(4)
            probe = run(PORT, ws_url, "document.querySelectorAll('.answer-body').length")
            try:
                count = int(str(probe[0]))
            except (ValueError, IndexError):
                count = 0
            if count >= 2:
                # 再多等一会让内容渲染完
                time.sleep(2)
                break

        print()
        print("=== 渲染结果 ===")
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
