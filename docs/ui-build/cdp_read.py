"""用 CDP 读取页面上的真实文本与计数，用于核对界面数字与接口是否一致。

用法：
    python cdp_read.py --view pre --sql "#checkLabel"
    python cdp_read.py --view home --sql ".l2-num span"
"""

from __future__ import annotations

import argparse
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

DRIVER = r"""
const wsUrl = process.argv[2];
const exprFile = process.argv[3];
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
    const fs = await import('node:fs');
    await new Promise((r) => setTimeout(r, 3200));
    const res = await call('Runtime.evaluate', {
      expression: fs.readFileSync(exprFile, 'utf8'),
      returnByValue: true, awaitPromise: true,
    });
    console.log(JSON.stringify(res));
    ws.close(); process.exit(0);
  } catch (err) { console.error('CDP 失败: ' + err.message); process.exit(1); }
};
setTimeout(() => { console.error('timeout'); process.exit(1); }, 45000);
"""


def cdp_targets(port: int) -> list[dict]:
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--view", default="home")
    parser.add_argument("--theme", default="light")
    parser.add_argument("--sql", default="", help="要读取的选择器；留空则输出一批关键文本")
    parser.add_argument("--base", default="http://127.0.0.1:8504/")
    parser.add_argument("--port", type=int, default=9401)
    args = parser.parse_args()

    if args.sql:
        expression = (
            "(() => { const out = [];"
            f" document.querySelectorAll({args.sql!r}).forEach((el) => out.push("
            "  (el.id ? '#' + el.id : el.tagName.toLowerCase()) + ' = ' + "
            "  JSON.stringify((el.textContent || '').trim().slice(0, 120)) + "
            "  ' | hidden=' + el.hidden + ' display=' + getComputedStyle(el).display + "
            "  ' w=' + Math.round(el.getBoundingClientRect().width)"
            ")); return out.length ? out : ['（无匹配元素）']; })()"
        )
    else:
        expression = r"""
(() => {
  const out = [];
  const sels = ['#checkLabel','#priorityBadge','#kpiChunks','#kpiDocs','#kpiCases','#kpiQuiz',
                '#todoLabel','#modelStatus','#headerRole','#homeDailyCase','#inspectionChecks',
                '#photoStage','#photoProgress','#cameraStage','#photoResult','#photoError',
                '.count-badge','.progress-label','.tier-l2 .l2-num','.head-note'];
  for (const sel of sels) {
    const els = document.querySelectorAll(sel);
    if (!els.length) { out.push(sel + ' -> 无匹配'); continue; }
    els.forEach((el) => {
      const cs = getComputedStyle(el);
      const r = el.getBoundingClientRect();
      out.push(sel + ' -> ' + JSON.stringify((el.textContent || '').trim().slice(0, 90))
               + '  [hidden=' + el.hidden + ' display=' + cs.display
               + ' w=' + Math.round(r.width) + ' h=' + Math.round(r.height) + ']');
    });
  }
  // 数一遍各容器里的复选框
  for (const sel of ['#priorityChecks','#todoList','#inspectionChecks','#checklist']) {
    const n = document.querySelectorAll(sel + ' input[type=checkbox]').length;
    out.push(sel + ' 复选框 = ' + n + (document.querySelector(sel) ? '' : '  （容器不存在）'));
  }
  return out;
})()
"""

    profile = Path(tempfile.gettempdir()) / f"_cdpread{args.port}"
    shutil.rmtree(profile, ignore_errors=True)
    profile.mkdir(parents=True, exist_ok=True)
    url = f"{args.base}?theme={args.theme}&view={args.view}"
    proc = subprocess.Popen(
        [EDGE, "--headless=new", "--disable-gpu", "--no-sandbox", "--disable-extensions",
         f"--remote-debugging-port={args.port}", f"--user-data-dir={profile}",
         "--window-size=1400,1000", url],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        ws_url = None
        for _ in range(40):
            time.sleep(0.5)
            try:
                for item in cdp_targets(args.port):
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
        expr_file = Path(tempfile.gettempdir()) / f"_cdpread_{args.port}.js"
        expr_file.write_text(expression, encoding="utf-8")
        driver = Path(tempfile.gettempdir()) / f"_cdpreaddrv_{args.port}.mjs"
        driver.write_text(DRIVER, encoding="utf-8")
        result = subprocess.run([NODE, str(driver), ws_url, str(expr_file)],
                                capture_output=True, text=True, encoding="utf-8",
                                errors="replace", timeout=90)
        if result.returncode != 0:
            print("[FAIL]", (result.stderr or "")[-300:])
            return 1
        payload = json.loads(result.stdout.strip())
        lines = payload.get("result", {}).get("value") or []
        print(f"=== 视图 {args.view} ===")
        for line in lines:
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
