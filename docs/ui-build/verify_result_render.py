"""验证识别结果结构化渲染（第 24 轮）。

做法：在真实浏览器里加载 ask 页，先向后端取一份**真实**的 structured payload，
      再调用页面的 renderPhotoResult 渲染它，然后断言 DOM 结构。

这样验证的是真实数据 + 真实渲染函数，不是模拟。

用法：python verify_result_render.py
"""

from __future__ import annotations

import json
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import urllib.request
import zlib
from pathlib import Path

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
NODE = r"C:\Users\sht18\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\node\bin\node.exe"
PORT = 9993
BASE = "http://127.0.0.1:8504"
BOUNDARY = "----RenderProbe91c2"

SCRIPT = r"""
(async () => {
  const out = [];
  const ok = (label, cond, extra) =>
    out.push((cond ? 'PASS  ' : 'FAIL  ') + label + (extra ? '  [' + extra + ']' : ''));

  // 1) 取一份真实 payload
  const shot = await fetch('/?view=ask').then(() => null).catch(() => null);
  const img = await new Promise((resolve) => {
    const c = document.createElement('canvas');
    c.width = 480; c.height = 320;
    const g = c.getContext('2d');
    g.fillStyle = '#8a8f96'; g.fillRect(0, 0, 480, 320);
    g.fillStyle = '#c8cdd3'; g.fillRect(40, 40, 180, 240);
    g.fillStyle = '#3a4048'; g.fillRect(260, 120, 160, 120);
    c.toBlob(resolve, 'image/png');
  });

  const form = new FormData();
  form.append('image', img, 'probe.png');
  let payload;
  try {
    const resp = await fetch('/api/inspect-image', { method: 'POST', body: form });
    payload = await resp.json();
  } catch (e) {
    out.push('FAIL  调用 /api/inspect-image 失败: ' + e.message);
    return out;
  }
  ok('拿到真实识别响应', !!payload, 'image_quality=' + payload.image_quality);

  const st = payload.structured;
  ok('响应含 structured', !!st && typeof st === 'object',
     st ? Object.keys(st).join(',') : 'none');
  if (!st) return out;

  // 2) 用页面上的真实渲染函数
  ok('页面存在 renderPhotoResult', typeof renderPhotoResult === 'function');
  if (typeof renderPhotoResult !== 'function') return out;

  const host = document.createElement('div');
  document.body.appendChild(host);
  const used = renderPhotoResult(payload, host);
  ok('renderPhotoResult 返回 true（结构化渲染生效）', used === true);

  const wrap = host.querySelector('.ins-result');
  ok('渲染出结果容器', !!wrap);

  // 3) 断言各段
  const summary = host.querySelector('.ins-summary');
  ok('A 识别结论段存在', !!summary);
  const worktype = host.querySelector('.ins-worktype-value, .ins-worktype.is-empty');
  ok('A 作业场景有内容（确定或如实说明未确定）', !!worktype,
     worktype ? worktype.textContent.trim().slice(0, 30) : '');

  const metricNum = host.querySelector('.ins-metric-num');
  const realCount = Array.isArray(st.risks) ? st.risks.filter(
    (r) => r && ((r.what && r.what.trim()) || (r.where && r.where.trim()))).length : 0;
  ok('A 风险计数等于真实条数', !!metricNum && Number(metricNum.textContent) === realCount,
     'DOM=' + (metricNum ? metricNum.textContent : '?') + ' 真实=' + realCount);

  const riskItems = host.querySelectorAll('.ins-risk');
  ok('B 风险条目数与真实一致', riskItems.length === realCount,
     riskItems.length + ' vs ' + realCount);
  if (riskItems.length) {
    ok('B 有位置标签', !!riskItems[0].querySelector('.ins-risk-where'));
    ok('B 有现象描述', !!riskItems[0].querySelector('.ins-risk-what'));
  }

  const realActions = realCount ? st.risks.filter(
    (r) => r && r.action && r.action.trim()).length : 0;
  const domActions = host.querySelectorAll('.ins-risk-action').length;
  ok('C 整改建议数等于真实 action 条数', domActions === realActions,
     'DOM=' + domActions + ' 真实=' + realActions);

  const realUncertain = Array.isArray(st.uncertain)
    ? st.uncertain.filter((x) => typeof x === 'string' && x.trim()).length : 0;
  const pendingBlock = host.querySelector('.ins-pending');
  ok('D 待确认段与真实 uncertain 一致',
     realUncertain ? !!pendingBlock : !pendingBlock,
     'DOM=' + (pendingBlock ? '有' : '无') + ' 真实=' + realUncertain);

  ok('保留免责声明', !!host.querySelector('.ins-disclaimer'));

  // 4) 容错：structured 不可用时应回退（返回 false），不崩
  const t1 = document.createElement('div');
  ok('容错：无 structured 返回 false', renderPhotoResult({}, t1) === false);
  const t2 = document.createElement('div');
  ok('容错：structured 为空对象返回 false',
     renderPhotoResult({ structured: {} }, t2) === false);
  const t3 = document.createElement('div');
  ok('容错：risks 非数组不崩',
     renderPhotoResult({ structured: { risks: 'oops', uncertain: null } }, t3) === false);
  const t4 = document.createElement('div');
  const okEmpty = renderPhotoResult(
    { structured: { work_type: '', risks: [], uncertain: [] } }, t4) === false;
  ok('容错：全空返回 false（交由文本回退）', okEmpty);

  return out;
})()
"""


def main() -> int:
    profile = Path(tempfile.gettempdir()) / f"_rr_{PORT}"
    shutil.rmtree(profile, ignore_errors=True)
    profile.mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen(
        [EDGE, "--headless=new", "--disable-gpu", "--no-sandbox",
         "--disable-extensions", "--disable-component-extensions-with-background-pages",
         "--disable-default-apps", "--no-first-run", "--no-default-browser-check",
         f"--remote-debugging-port={PORT}", f"--user-data-dir={profile}",
         "--window-size=1440,900", BASE + "/?theme=light&view=ask"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        ws_url = None
        for _ in range(60):
            time.sleep(0.5)
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/list", timeout=8) as r:
                    for item in json.loads(r.read().decode("utf-8")):
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

        expr = Path(tempfile.gettempdir()) / f"_rr_{PORT}.js"
        expr.write_text(SCRIPT, encoding="utf-8")
        driver = Path(tempfile.gettempdir()) / f"_rrdrv_{PORT}.mjs"
        driver.write_text(
            "import fs from 'node:fs';\n"
            "const ws=new WebSocket(process.argv[2]);let id=0;const pend=new Map();\n"
            "function call(m,p){return new Promise((res,rej)=>{const i=++id;pend.set(i,{res,rej});"
            "ws.send(JSON.stringify({id:i,method:m,params:p||{}}));});}\n"
            "ws.onmessage=e=>{const m=JSON.parse(e.data);if(m.id&&pend.has(m.id)){"
            "const{res,rej}=pend.get(m.id);pend.delete(m.id);"
            "m.error?rej(new Error(JSON.stringify(m.error))):res(m.result);}};\n"
            "ws.onopen=async()=>{try{\n"
            "await new Promise(r=>setTimeout(r,3500));\n"
            "const r=await call('Runtime.evaluate',{expression:fs.readFileSync(process.argv[3],'utf8'),"
            "awaitPromise:true,returnByValue:true});console.log(JSON.stringify(r));"
            "ws.close();process.exit(0);}\n"
            "catch(e){console.error(e.message);process.exit(1);}};\n"
            "setTimeout(()=>process.exit(1),120000);\n",
            encoding="utf-8",
        )
        result = subprocess.run([NODE, str(driver), ws_url, str(expr)],
                                capture_output=True, text=True, encoding="utf-8",
                                errors="replace", timeout=180)
        if result.returncode != 0:
            print("驱动失败：", (result.stderr or "")[-250:])
            return 1
        payload = json.loads(result.stdout.strip())
        lines = payload.get("result", {}).get("value") or []
        print("=" * 74)
        print("识别结果结构化渲染验证（真实 payload + 页面真实渲染函数）")
        print("=" * 74)
        failures = 0
        for line in lines:
            print("  " + line)
            if line.startswith("FAIL"):
                failures += 1
        print("=" * 74)
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
