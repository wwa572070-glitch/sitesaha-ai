"""验证趋势图与热力格在**有数据**时的渲染（第 16 轮 §7）。

空状态已经确认过。这个脚本往 localStorage 注入构造数据，
再看图表是否真的画出了折线和有色格子 —— 否则「空状态正常」会掩盖渲染 bug。

用法：python verify_charts_data.py
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
PORT = 9541

SEED_JS = r"""
(() => {
  /* 构造 5 次测验记录与 7 天活动，验证图表真的会画 */
  const today = new Date();
  function key(offset) {
    const d = new Date(today.getTime());
    d.setDate(d.getDate() - offset);
    const p = (n) => (n < 10 ? '0' + n : String(n));
    return d.getFullYear() + '-' + p(d.getMonth() + 1) + '-' + p(d.getDate());
  }
  const activity = {};
  [0, 1, 2, 4, 6].forEach((offset, i) => { activity[key(offset)] = i + 1; });

  const history = [
    { percent: 45, correct: 9, at: '2026-05-01T10:00:00Z' },
    { percent: 60, correct: 12, at: '2026-05-05T10:00:00Z' },
    { percent: 70, correct: 14, at: '2026-05-12T10:00:00Z' },
    { percent: 85, correct: 17, at: '2026-05-18T10:00:00Z' },
    { percent: 90, correct: 18, at: '2026-05-25T10:00:00Z' },
  ];
  const quiz = {
    attempts: history.length, bestPercent: 90, bestCorrect: 18, total: 20,
    lastCorrect: 18, lastAt: '2026-05-25T10:00:00Z',
    wrongDomains: {}, seen: {}, history: history,
  };
  localStorage.setItem('sitesaha-activity-v1', JSON.stringify(activity));
  localStorage.setItem('sitesaha-quiz-v1', JSON.stringify(quiz));
  return 'seeded';
})()
"""

READ_JS = r"""
(() => {
  const out = [];
  const heat = document.getElementById('studyHeat');
  if (heat) {
    const cells = heat.querySelectorAll('.heat-cell');
    out.push('热力格格子数 ' + cells.length);
    const levels = [];
    cells.forEach((c) => levels.push(c.getAttribute('data-level')));
    out.push('  各级别 ' + levels.join(','));
    const colored = Array.from(cells).filter((c) => c.getAttribute('data-level') !== '0').length;
    out.push('  有色格子 ' + colored + ' / ' + cells.length);
  }
  const note = document.getElementById('studyHeatNote');
  if (note) out.push('热力格说明: ' + note.textContent.trim());
  const trend = document.getElementById('quizTrend');
  if (trend) {
    const svg = trend.querySelector('svg');
    const poly = trend.querySelector('polyline');
    const circles = trend.querySelectorAll('circle.pt');
    out.push('趋势图 svg ' + (svg ? '有' : '无') + '，折线 ' + (poly ? '有' : '无')
             + '，数据点 ' + circles.length);
    if (poly) out.push('  折线坐标 ' + poly.getAttribute('points').slice(0, 90));
    const meta = trend.querySelector('.answer-meta');
    if (meta) out.push('  ' + meta.textContent.trim());
  }
  return out;
})()
"""


def targets(port: int) -> list[dict]:
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def run_cdp(port: int, ws_url: str, expression: str) -> list[str] | str:
    expr_file = Path(tempfile.gettempdir()) / f"_chart_{port}.js"
    expr_file.write_text(expression, encoding="utf-8")
    driver = Path(tempfile.gettempdir()) / f"_chartdrv_{port}.mjs"
    driver.write_text(
        "import fs from 'node:fs';\n"
        "const ws = new WebSocket(process.argv[2]);\n"
        "let id=0; const pend=new Map();\n"
        "function call(m,p){return new Promise((res,rej)=>{const i=++id;"
        "pend.set(i,{res,rej});ws.send(JSON.stringify({id:i,method:m,params:p||{}}));});}\n"
        "ws.onmessage=e=>{const m=JSON.parse(e.data);if(m.id&&pend.has(m.id)){"
        "const{res,rej}=pend.get(m.id);pend.delete(m.id);"
        "m.error?rej(new Error(JSON.stringify(m.error))):res(m.result);}};\n"
        "ws.onopen=async()=>{try{await new Promise(r=>setTimeout(r,2500));\n"
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
        raise RuntimeError((result.stderr or "")[-200:])
    payload = json.loads(result.stdout.strip())
    return payload.get("result", {}).get("value")


def main() -> int:
    profile = Path(tempfile.gettempdir()) / f"_chartprof_{PORT}"
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

        print("=== 先注入构造数据 ===")
        print("  ", run_cdp(PORT, ws_url, SEED_JS))

        # 重新加载让图表按新数据渲染
        reload_driver = Path(tempfile.gettempdir()) / f"_reload_{PORT}.mjs"
        reload_driver.write_text(
            "const ws = new WebSocket(process.argv[2]);\n"
            "let id=0;\n"
            "ws.onopen=()=>{ws.send(JSON.stringify({id:++id,method:'Page.reload',"
            "params:{ignoreCache:true}}));setTimeout(()=>{ws.close();process.exit(0);},6000);};\n",
            encoding="utf-8",
        )
        subprocess.run([NODE, str(reload_driver), ws_url], capture_output=True, timeout=40)
        time.sleep(4)

        print("\n=== 有数据时的图表渲染 ===")
        lines = run_cdp(PORT, ws_url, READ_JS)
        for line in lines or []:
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
