"""把首页按「作业流程」重组成 5 个阶段，并把侧栏收进首页。

重组前的结构问题：
  · 首页内容平铺在 6 个 module 里，没有分组，眼睛找不到落点
  · <aside> 挂在所有 <section> 外面，切到"安全培训"页也照样显示"服务状态"

重组后：
  阶段 ① 上工前准备 —— 工种选择、上工前三件事、安全底线
  阶段 ② 现场作业   —— 拍照识隐患 + 跳转入口
  阶段 ③ 出事怎么办 —— 语音提问 + 跳转入口
  阶段 ④ 培训与测验 —— 培训模块、警示案例
  阶段 ⑤ 查标准     —— 知识领域分布、在线知识库、服务状态

用法：python restructure_home.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
BODY = BUILD / "index_body.html"
MARK = "<!-- ===== V13 PHASES BEGIN ===== -->"

PHASE_CSS = """
<!-- ===== V13 PHASES BEGIN ===== -->
<style>
.phase { margin:32px 0 0; }
.phase:first-of-type { margin-top:24px; }
.phase-head { display:flex; align-items:baseline; gap:12px; margin-bottom:14px; flex-wrap:wrap; }
.phase-no {
  flex:0 0 auto; width:26px; height:26px; border-radius:50%;
  background:var(--green-700); color:#fff; font-size:13px; font-weight:700;
  display:inline-grid; place-items:center; font-family:var(--mono); line-height:1;
}
.phase-title { font-size:18px; font-weight:700; color:var(--ink-800); letter-spacing:-.01em; }
.phase-desc { font-size:13px; color:var(--ink-400); flex:1 1 240px; min-width:0; }
.phase-rule { height:1px; background:var(--ink-100); margin:0 0 16px; }
.phase-cols { display:grid; grid-template-columns:minmax(0,1fr) 340px; gap:24px; align-items:start; }
.phase-cols > .phase-main { display:grid; gap:20px; min-width:0; }
.phase-cols > .phase-side { display:grid; gap:20px; min-width:0; }
.phase-single { display:grid; gap:20px; }
@media (max-width:1200px) {
  .phase-cols { grid-template-columns:1fr; }
  .phase-cols > .phase-side { grid-template-columns:repeat(2,minmax(0,1fr)); }
}
@media (max-width:900px) {
  .phase-cols > .phase-side { grid-template-columns:1fr; }
  .phase { margin-top:24px; }
  .phase-title { font-size:16px; }
}
@media (max-width:640px) {
  .phase-head { gap:9px; }
  .phase-no { width:23px; height:23px; font-size:12px; }
}
</style>
"""


def extract_section(body: str, section_id: str) -> tuple[str, int, int]:
    """取出一个 <section id="...">…</section> 的完整文本与位置。"""
    start = body.find(f'<section id="{section_id}"')
    if start < 0:
        raise SystemExit(f"找不到 section #{section_id}")
    depth = 0
    i = start
    while i < len(body):
        nxt = re.search(r"<(/?)section\b[^>]*>", body[i:])
        if not nxt:
            break
        depth += -1 if nxt.group(1) == "/" else 1
        i += nxt.end()
        if depth == 0:
            break
    return body[start:i], start, i


def extract_panel(text: str, title: str) -> str:
    """按 <h2> 文本取出一个 .panel 的完整块。"""
    for match in re.finditer(r'<div class="panel"', text):
        depth = 0
        i = match.start()
        while i < len(text):
            nxt = re.search(r"<(/?)div\b[^>]*>", text[i:])
            if not nxt:
                break
            depth += -1 if nxt.group(1) == "/" else 1
            i += nxt.end()
            if depth == 0:
                break
        block = text[match.start():i]
        if title in block:
            return block
    raise SystemExit(f"找不到模块：{title}")


def extract_aside(body: str) -> tuple[str, int, int]:
    start = body.find("<aside")
    if start < 0:
        raise SystemExit("找不到 <aside>")
    depth = 0
    i = start
    while i < len(body):
        nxt = re.search(r"<(/?)aside\b[^>]*>", body[i:])
        if not nxt:
            break
        depth += -1 if nxt.group(1) == "/" else 1
        i += nxt.end()
        if depth == 0:
            break
    return body[start:i], start, i


def phase(number: int, title: str, desc: str, inner: str, cols: str = "single") -> str:
    if cols == "two":
        body = f'<div class="phase-cols">{inner}</div>'
    else:
        body = f'<div class="phase-single">{inner}</div>'
    return f"""      <div class="phase">
        <div class="phase-head">
          <span class="phase-no" aria-hidden="true">{number}</span>
          <span class="phase-title">{title}</span>
          <span class="phase-desc">{desc}</span>
        </div>
        <div class="phase-rule"></div>
        {body}
      </div>"""


def main() -> int:
    body = BODY.read_text(encoding="utf-8")
    if MARK in body:
        print("[跳过] 已经重组过了")
        return 0

    home, home_start, home_end = extract_section(body, "home")
    aside, aside_start, aside_end = extract_aside(body)

    # aside 必须排在 home 之后，删除时才不会串位
    if aside_start < home_end:
        raise SystemExit("aside 位置与首页重叠，脚本需要调整")

    # --- 取出要搬迁的模块 ---
    blocks = {
        "todo": extract_panel(home, "今天上工前的三件事"),
        "role": extract_panel(home, "我是哪个工种"),
        "training": extract_panel(home, "培训与知识模块"),
        "cases": extract_panel(home, "今日警示案例"),
        "domains": extract_panel(home, "知识领域分布"),
        "baseline": extract_panel(home, "安全底线"),
    }
    aside_metrics = extract_panel(aside, "在线知识库")
    aside_status = extract_panel(aside, "服务状态")

    # 首页非模块部分：hero + 主行动卡
    hero_start = home.find('<div class="hero"')
    grid_start = home.find('<div class="home-grid"')
    if hero_start < 0 or grid_start < 0:
        raise SystemExit("首页结构不符合预期（找不到 hero 或 home-grid）")
    hero_and_actions = home[hero_start:grid_start].rstrip()

    phases = "\n\n".join([
        phase(1, "上工前准备", "先把工种和三件事确认好，再进现场。", "\n".join([
            '          <div class="phase-cols">',
            f'            <div class="phase-main">\n{blocks["todo"]}\n            </div>',
            f'            <div class="phase-side">\n{blocks["role"]}\n{blocks["baseline"]}\n            </div>',
            "          </div>",
        ])),
        phase(2, "现场作业", "拍下作业面，先看有没有看得见的隐患。", "\n".join([
            '          <div class="phase-cols">',
            '            <div class="phase-main"><div class="panel"><div class="panel-head">'
            '<h2>拍照识隐患</h2><span class="head-spacer"></span>'
            '<span class="head-note">照片不能替代现场安全员检查</span></div>'
            '<div class="panel-body"><p class="lead">在下面的「现场问答」里可以直接拍照上传，'
            '系统会指出画面里可见的风险点。</p>'
            '<button class="primary-button" type="button" data-goto="interview">去拍照检查 →</button>'
            '</div></div></div>',
            f'            <div class="phase-side">\n{blocks["training"]}\n            </div>',
            "          </div>",
        ])),
        phase(3, "出事怎么办", "受伤、火灾、触电、坍塌的处置步骤与报警入口。", "\n".join([
            '          <div class="phase-single">',
            '            <div class="panel"><div class="panel-head"><h2>应急求助</h2>'
            '<span class="head-spacer"></span><span class="head-note">先停、先撤、先报</span></div>'
            '<div class="panel-body"><p class="lead">不要为了取东西返回危险区域，'
            '不接受未经训练人员冒险施救。</p>'
            '<button class="danger-button" type="button" data-goto="emergency">打开应急处置指引 →</button>'
            '</div></div>',
            "          </div>",
        ])),
        phase(4, "培训与测验", "新人 5 步路线、20 题自检、学习积分与可打印记录单。", "\n".join([
            '          <div class="phase-single">',
            f'{blocks["cases"]}',
            "          </div>",
        ])),
        phase(5, "查标准与知识库", f"已入库文档与现行国家标准；风险领域分布用于班组培训选题。", "\n".join([
            '          <div class="phase-cols">',
            f'            <div class="phase-main">\n{aside_metrics}\n            </div>',
            f'            <div class="phase-side">\n{blocks["domains"]}\n{aside_status}\n            </div>',
            "          </div>",
        ])),
    ])

    new_home = (
        '<section id="home" class="view active" aria-label="首页">\n\n'
        + hero_and_actions
        + "\n\n"
        + PHASE_CSS
        + phases
        + "\n\n    </section>"
    )

    # 先删 aside（在后），再替换 home（在前），避免偏移
    body = body[:aside_start] + body[aside_end:]
    body = body[:home_start] + new_home + body[home_end:]

    BODY.write_text(body, encoding="utf-8")
    print("[ok] 首页已重组为 5 个阶段，侧栏已收进首页")
    print(f"index_body.html：{len(home) + len(aside)} → {len(new_home)} 字符（首页部分）")

    # 自检：关键 id 不能丢
    required = [
        "todoList", "homeRoleChips", "homeRoleHint", "homeCaseGrid", "sideDomains",
        "documentCount", "chunkCount", "caseCount", "roleCount",
        "kvVision", "kvAsr", "kvMode", "kvAccess",
    ]
    missing = [x for x in required if f'id="{x}"' not in body]
    if missing:
        print(f"[FAIL] 丢失 id：{missing}")
        return 1
    print(f"[ok] {len(required)} 个关键 id 全部保留")
    return 0


if __name__ == "__main__":
    sys.exit(main())
