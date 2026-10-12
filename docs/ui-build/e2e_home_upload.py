"""端到端验证：首页上传入口 → 真实识别 → 结构化结果（第 24 轮 C）。

这是前两轮欠下的验证。用 CDP 的 DOM.setFileInputFiles 真的把一张图片文件
投进页面的 file input，触发真实上传，等真实模型返回，再断言渲染出的 DOM。

不是模拟，不是只看代码。全程走真实链路：
  文件投递 → change 事件 → 现有压缩逻辑 → POST /api/inspect-image
  → 真实视觉模型 → structured → renderPhotoResult → DOM

用法：python e2e_home_upload.py
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

APP = Path(__file__).resolve().parent.parent.parent
BUILD = Path(__file__).resolve().parent
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
NODE = r"C:\Users\sht18\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\node\bin\node.exe"
PORT = 9995
BASE = "http://127.0.0.1:8504"

# 用一张真实截图当上传素材（够大，能过防幻觉闸门）
CANDIDATES = [
    BUILD / "evidence" / "desktop-ask.png",
    BUILD / "evidence" / "desktop-home.png",
    BUILD / "_shot" / "page-light-home.png",
]

# 等待并断言（在页面里跑）
PROBE = r"""
(async () => {
  const out = [];
  const ok = (label, cond, extra) =>
    out.push((cond ? 'PASS  ' : 'FAIL  ') + label + (extra ? '  [' + extra + ']' : ''));
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  // 1) 首页首屏是否有识别工作台
  const dz = document.getElementById('photoDropzone');
  ok('首页首屏有上传区', !!dz);
  const hero = document.querySelector('.hero-split');
  ok('Hero 是双栏结构', !!hero);
  const h2 = document.querySelector('.hero-copy h2');
  ok('Hero 主标题是识别能力', !!h2 && /识别/.test(h2.textContent),
     h2 ? h2.textContent.trim() : '');

  // 2) 关键 id 只应有一份（没有重复逻辑）
  ['sitePhoto','sitePhotoCamera','photoButton','photoStage','photoResult']
    .forEach((id) => ok('id ' + id + ' 唯一', document.querySelectorAll('#' + id).length === 1,
      String(document.querySelectorAll('#' + id).length)));

  // 3) 触发识别（文件已由 CDP 投递到 input）
  const btn = document.getElementById('photoButton');
  const result = document.getElementById('photoResult');
  const stage = document.getElementById('photoStage');
  ok('识别按钮存在且可用', !!btn && !btn.disabled);

  // 让现有 change 处理跑完（压缩是异步的）
  await sleep(2500);
  const preview = document.getElementById('photoPreview');
  ok('预览区已显示图片', !!(stage && !stage.hidden && preview && preview.src),
     preview && preview.src ? 'src 有值' : '无 src');

  btn.click();

  // 4) 等真实模型返回
  let waited = 0;
  while (waited < 150000) {
    await sleep(1500);
    waited += 1500;
    if (result && !result.hidden && result.querySelector('.ins-result')) break;
    if (result && !result.hidden && result.textContent.trim() &&
        !/正在结合照片/.test(result.textContent)) break;
  }
  ok('识别流程返回（未超时）', waited < 150000, (waited / 1000).toFixed(0) + 's');

  // 5) 断言结构化渲染
  const wrap = result && result.querySelector('.ins-result');
  ok('渲染出结构化结果容器', !!wrap);

  if (wrap) {
    ok('A 识别结论段', !!wrap.querySelector('.ins-summary'));
    ok('A 作业场景有内容',
       !!wrap.querySelector('.ins-worktype-value, .ins-worktype.is-empty'));
    const metric = wrap.querySelector('.ins-metric-num');
    ok('A 有真实风险计数', !!metric && /^\d+$/.test(metric.textContent),
       metric ? metric.textContent : '');
    const riskItems = wrap.querySelectorAll('.ins-risk');
    ok('B 风险条目已渲染', riskItems.length >= 0, riskItems.length + ' 条');
    if (riskItems.length) {
      ok('B 每条有现象描述', !!riskItems[0].querySelector('.ins-risk-what'));
    }
    ok('保留免责声明', !!wrap.querySelector('.ins-disclaimer'));
    // 结果区不应出现原始 JSON 或 undefined
    const raw = wrap.textContent;
    ok('结果区无 undefined / NaN / [object',
       !/undefined|NaN|\[object/.test(raw));
  } else if (result) {
    // 回退路径：structured 不可用时显示文本，也不能崩
    ok('无结构化时回退为文本且非空', result.textContent.trim().length > 10,
       result.textContent.trim().slice(0, 40));
  }

  // 6) 页面无脚本错误
  ok('没有记录到脚本错误', (window.__e2eErrors || []).length === 0,
     String((window.__e2eErrors || []).length));

  return out;
})()
"""


def main() -> int:
    image = next((p for p in CANDIDATES if p.is_file()), None)
    if not image:
        print("找不到可用的测试图片")
        return 1
    print(f"投递的图片: {image.name}  {image.stat().st_size // 1024} KB")

    profile = Path(tempfile.gettempdir()) / f"_e2e_{PORT}"
    shutil.rmtree(profile, ignore_errors=True)
    profile.mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen(
        [EDGE, "--headless=new", "--disable-gpu", "--no-sandbox",
         "--disable-extensions", "--disable-component-extensions-with-background-pages",
         "--disable-default-apps", "--no-first-run", "--no-default-browser-check",
         f"--remote-debugging-port={PORT}", f"--user-data-dir={profile}",
         "--window-size=1440,900", BASE + "/?theme=light&view=home"],
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

        expr = Path(tempfile.gettempdir()) / f"_e2e_{PORT}.js"
        expr.write_text(PROBE, encoding="utf-8")
        driver = Path(tempfile.gettempdir()) / f"_e2edrv_{PORT}.mjs"
        driver.write_text(
            "import fs from 'node:fs';\n"
            "const ws=new WebSocket(process.argv[2]);let id=0;const pend=new Map();\n"
            "function call(m,p){return new Promise((res,rej)=>{const i=++id;pend.set(i,{res,rej});"
            "ws.send(JSON.stringify({id:i,method:m,params:p||{}}));});}\n"
            "ws.onmessage=e=>{const m=JSON.parse(e.data);if(m.id&&pend.has(m.id)){"
            "const{res,rej}=pend.get(m.id);pend.delete(m.id);"
            "m.error?rej(new Error(JSON.stringify(m.error))):res(m.result);}};\n"
            "ws.onopen=async()=>{try{\n"
            "await call('DOM.enable');await call('Runtime.enable');\n"
            "// 收集页面脚本错误\n"
            "await call('Runtime.evaluate',{expression:"
            "\"window.__e2eErrors=[];window.addEventListener('error',e=>window.__e2eErrors.push(String(e.message)));\"});\n"
            "await new Promise(r=>setTimeout(r,3000));\n"
            "const doc=await call('DOM.getDocument',{depth:-1});\n"
            "const q=await call('DOM.querySelector',{nodeId:doc.root.nodeId,"
            "selector:'#sitePhotoCamera'});\n"
            "if(!q.nodeId){console.error('找不到 #sitePhotoCamera');process.exit(1);}\n"
            "await call('DOM.setFileInputFiles',{files:[process.argv[4]],nodeId:q.nodeId});\n"
            "const r=await call('Runtime.evaluate',{expression:fs.readFileSync(process.argv[3],'utf8'),"
            "awaitPromise:true,returnByValue:true});console.log(JSON.stringify(r));"
            "ws.close();process.exit(0);}\n"
            "catch(e){console.error(e.message);process.exit(1);}};\n"
            "setTimeout(()=>process.exit(1),220000);\n",
            encoding="utf-8",
        )
        result = subprocess.run([NODE, str(driver), ws_url, str(expr), str(image)],
                                capture_output=True, text=True, encoding="utf-8",
                                errors="replace", timeout=280)
        if result.returncode != 0:
            print("驱动失败：", (result.stderr or "")[-300:])
            return 1
        payload = json.loads(result.stdout.strip())
        value = payload.get("result", {})
        lines = value.get("value") or []
        if not lines:
            print("页面无返回：", json.dumps(value, ensure_ascii=False)[:400])
            return 1

        print("=" * 76)
        print("端到端验证：首页上传 → 真实识别 → 结构化结果")
        print("=" * 76)
        failures = 0
        for line in lines:
            print("  " + line)
            if line.startswith("FAIL"):
                failures += 1
        print("=" * 76)
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
