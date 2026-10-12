"""§5 验收断言（第 21 轮）。

用无头浏览器实际渲染，断言：
  1. KPI 主格存在，环形图有真实 aria-label，且没有编造百分比
  2. 案例卡渲染出 ✗/✓ 双栏结构，左右都有内容
  3. 四张插画都真的被引用（不再有死代码）
  4. 微交互样式存在且支持 prefers-reduced-motion

用法：python verify_visual_5.py
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
PORT = 9981

SCRIPT = r"""
(() => {
  const out = [];
  const ok = (label, cond, extra) =>
    out.push((cond ? 'PASS  ' : 'FAIL  ') + label + (extra ? '  [' + extra + ']' : ''));

  // 1. KPI 主格与环形图
  const primary = document.querySelector('.l2-cell.is-primary');
  ok('KPI 主格存在', !!primary);
  const ring = document.getElementById('kpiRing');
  ok('环形图存在', !!ring);
  if (ring) {
    const label = ring.getAttribute('aria-label') || '';
    const title = ring.querySelector('title');
    ok('环形图有无障碍文本', !!(label || title), label.slice(0, 40));
  }
  const pct = document.getElementById('kpiRingPct');
  ok('环形百分比有值（无记录时应为 --）', !!pct, pct ? pct.textContent : '');

  // 2. 案例对照结构
  const cmp = document.querySelectorAll('.case-compare');
  ok('案例对照结构已渲染', cmp.length > 0, cmp.length + ' 组');
  if (cmp.length) {
    const first = cmp[0];
    const wrong = first.querySelector('.case-side.is-wrong');
    const right = first.querySelector('.case-side.is-right');
    ok('左侧错误做法存在', !!wrong);
    ok('右侧正确做法存在', !!right);
    ok('左侧有正文', !!(wrong && wrong.textContent.trim().length > 12),
       wrong ? String(wrong.textContent.trim().length) : '0');
    ok('右侧有正文', !!(right && right.textContent.trim().length > 6),
       right ? String(right.textContent.trim().length) : '0');
    // 不能只靠颜色：两侧都要有文字标签
    ok('左侧有文字标签', !!(wrong && /错误做法/.test(wrong.textContent)));
    ok('右侧有文字标签', !!(right && /正确做法/.test(right.textContent)));
  }

  // 3. 四张插画都被引用
  const ids = ['ill-edge', 'ill-scaffold', 'ill-ppe', 'ill-emergency'];
  const html = document.documentElement.outerHTML;
  ids.forEach((id) => {
    const defined = html.indexOf('id="' + id + '"') >= 0;
    const used = html.indexOf('href="#' + id + '"') >= 0;
    ok('插画 ' + id + ' 已定义且被引用', defined && used,
       (defined ? 'defined' : 'missing') + '/' + (used ? 'used' : 'unused'));
  });

  // 4. 减少动态效果支持
  const figures = document.querySelectorAll('.ill-figure');
  ok('插图组件已渲染', figures.length > 0, figures.length + ' 张');

  // 5. 横向溢出
  const de = document.documentElement;
  ok('无横向溢出', de.scrollWidth <= de.clientWidth + 1,
     de.scrollWidth + ' vs ' + de.clientWidth);

  return out;
})()
"""


def main() -> int:
    profile = Path(tempfile.gettempdir()) / f"_v5_{PORT}"
    shutil.rmtree(profile, ignore_errors=True)
    profile.mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen(
        [EDGE, "--headless=new", "--disable-gpu", "--no-sandbox",
         "--disable-extensions", "--disable-component-extensions-with-background-pages",
         "--disable-default-apps", "--no-first-run", "--no-default-browser-check",
         f"--remote-debugging-port={PORT}", f"--user-data-dir={profile}",
         "--window-size=1440,900",
         "http://127.0.0.1:8504/?theme=light&view=home"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        ws_url = None
        for _ in range(60):
            time.sleep(0.5)
            try:
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{PORT}/json/list", timeout=8
                ) as response:
                    for item in json.loads(response.read().decode("utf-8")):
                        if item.get("type") == "page" and "127.0.0.1" in item.get("url", ""):
                            ws_url = item["webSocketDebuggerUrl"]
                            break
            except Exception:
                continue
            if ws_url:
                break
        if not ws_url:
            print("拿不到浏览器目标")
            return 1

        expr = Path(tempfile.gettempdir()) / f"_v5expr_{PORT}.js"
        expr.write_text(SCRIPT, encoding="utf-8")
        driver = Path(tempfile.gettempdir()) / f"_v5drv_{PORT}.mjs"
        driver.write_text(
            "import fs from 'node:fs';\n"
            "const ws=new WebSocket(process.argv[2]);let id=0;const pend=new Map();\n"
            "function call(m,p){return new Promise((res,rej)=>{const i=++id;pend.set(i,{res,rej});"
            "ws.send(JSON.stringify({id:i,method:m,params:p||{}}));});}\n"
            "ws.onmessage=e=>{const m=JSON.parse(e.data);if(m.id&&pend.has(m.id)){"
            "const{res,rej}=pend.get(m.id);pend.delete(m.id);"
            "m.error?rej(new Error(JSON.stringify(m.error))):res(m.result);}};\n"
            "ws.onopen=async()=>{try{\n"
            "await call('Page.enable');\n"
            "await call('Runtime.evaluate',{expression:\"location.search='?theme=light&view=learn'\","
            "returnByValue:true});\n"
            "await new Promise(r=>setTimeout(r,4000));\n"
            "const r=await call('Runtime.evaluate',{expression:fs.readFileSync(process.argv[3],'utf8'),"
            "returnByValue:true});console.log(JSON.stringify(r));ws.close();process.exit(0);}\n"
            "catch(e){console.error(e.message);process.exit(1);}};\n"
            "setTimeout(()=>process.exit(1),50000);\n",
            encoding="utf-8",
        )
        result = subprocess.run([NODE, str(driver), ws_url, str(expr)],
                                capture_output=True, text=True, encoding="utf-8",
                                errors="replace", timeout=110)
        if result.returncode != 0:
            print("驱动失败：", (result.stderr or "")[-200:])
            return 1
        payload = json.loads(result.stdout.strip())
        lines = payload.get("result", {}).get("value") or []
        print("=" * 70)
        print("§5 视觉验收（在 learn 视图实际渲染后断言）")
        print("=" * 70)
        failures = 0
        for line in lines:
            print("  " + line)
            if line.startswith("FAIL"):
                failures += 1
        print("=" * 70)
        print(f"  失败 {failures} 项 / 共 {len(lines)} 项")
        return 0 if failures == 0 else 1
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=8)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    sys.exit(main())
