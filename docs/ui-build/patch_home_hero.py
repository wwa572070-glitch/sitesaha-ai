"""第 24 轮 B：首页 Hero 以 AI 图像识别为主角。

做法（避免重复逻辑的关键）：
  **把「拍照问安全」面板整体搬到 Hero 右侧**，而不是在首页再写一套上传。
  这样全站只有一套 id（sitePhoto / photoButton / photoStage …）和一套处理函数
  （inspectPhoto / renderPhotoResult），行为不可能不一致。

改动：
  1. .tier-l1 改为两栏：左「价值主张 + 次要入口」，右「AI 识别工作台」
  2. 主标题换成「上传现场照片，AI 识别安全风险」
  3. 安全问答降为次要入口（保留按钮，data-jump 跳转不变）
  4. 原 ask 页的照片面板搬走，留一个跳转到首页工作台的入口
  5. 新增 hero-split 栅格样式；窄屏自动堆叠

用法：python patch_home_hero.py [--dry-run]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
BODY = BUILD / "index_body.html"
TIERS = BUILD / "v16_tiers.css"

TAG = re.compile(r"<(/?)(div)\b[^>]*?(/?)>")


def block_span(html: str, needle: str, open_marker: str):
    """找到包含 needle 的、以 open_marker 开头的 div 块边界。"""
    index = html.find(needle)
    if index < 0:
        return None
    start = html.rfind(open_marker, 0, index)
    if start < 0:
        return None
    depth = 0
    position = start
    while position < len(html):
        match = TAG.search(html, position)
        if not match:
            break
        position = match.end()
        if match.group(1) == "/":
            depth -= 1
            if depth == 0:
                return start, match.end()
        elif match.group(3) != "/":
            depth += 1
    return None


HERO_OLD = '''      <div class="tier-l1">
        <div class="l1-kicker">'''

HERO_NEW = '''      <div class="tier-l1 hero-split">
        <div class="hero-copy">
        <div class="l1-kicker">'''

H2_OLD = '''        <h2>上工前，先问一句</h2>'''
H2_NEW = '''        <h2>上传现场照片，AI 识别安全风险</h2>'''

LEAD_OLD = '''        <p class="l1-lead">不懂就问。你告诉我<em>准备做什么、看到什么、哪里不确定</em>，我用现场能听懂的话说。回答优先给能立刻执行的动作，再附规范依据和来源。</p>'''
LEAD_NEW = '''        <p class="l1-lead">把作业面、防护设施和周边环境拍进一张照片，几十秒内得到：<em>识别到的作业场景、可见风险的位置与现象、每条风险的立即动作、以及需要你补充确认的内容</em>。不想拍照也可以直接打字问安全。</p>'''

# 左栏收尾：把 rolehint 之后闭合 hero-copy
COPY_CLOSE_OLD = '''        <div id="homeRoleHint" class="l1-rolehint">还没有选择工种 —— 未选择时按通用要点回答，选择后会自动带上本工种的主要风险与必守规矩。</div>
      </div>'''
COPY_CLOSE_NEW = '''        <div id="homeRoleHint" class="l1-rolehint">还没有选择工种 —— 未选择时按通用要点回答，选择后会自动带上本工种的主要风险与必守规矩。</div>
        </div><!-- /hero-copy -->

        <div class="hero-workbench" id="heroWorkbench">
          <!-- AI 识别工作台：从「问安全」页整体搬来，全站共用一套逻辑 -->
        </div>
      </div>'''

# ask 页搬走后留的入口
ASK_PLACEHOLDER = '''      <div class="panel">
        <div class="panel-head"><h2>需要看图判断？</h2><span class="head-spacer"></span><span class="head-note">用首页的识别工作台</span></div>
        <div class="panel-body">
          <p class="lead">照片识别需要上传图片，在首页的 AI 工作台完成。文字问答不受影响，可以继续在这里提问。</p>
          <button class="secondary-button ico-button" data-jump="home" type="button">
            <svg class="ico" aria-hidden="true"><use href="#i-camera"/></svg>去首页拍照识别
          </button>
        </div>
      </div>
'''

CSS = """

/* ==========================================================================
   第 24 轮 B · 首页 Hero 双栏（左价值 / 右 AI 工作台）
   --------------------------------------------------------------------------
   评委打开首页第一眼就要看到核心能力：上传照片 → AI 识别风险。
   工作台是从「问安全」页整体搬来的同一套 DOM，逻辑不分叉。
   ========================================================================== */
.hero-split {
  display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1.05fr);
  gap: 32px; align-items: start;
}
.hero-copy { min-width: 0; }
.hero-workbench { min-width: 0; }
/* 工作台里的面板本来就是卡片，Hero 内不再套一层边框 */
.hero-workbench > .panel {
  margin: 0; border-radius: var(--r-lg);
  box-shadow: var(--shadow-md, 0 8px 24px rgba(12, 43, 74, .08));
}

@media (max-width: 1040px) {
  .hero-split { grid-template-columns: 1fr; gap: 24px; }
}
@media (max-width: 640px) {
  .hero-split { gap: 20px; }
}
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    body = BODY.read_text(encoding="utf-8")
    tiers = TIERS.read_text(encoding="utf-8")
    applied = 0

    if "hero-split" in body:
        print("  [跳过] Hero 已改造")
        return 0

    # ---- 1) 摘出 ask 页的照片面板 ----
    span = block_span(body, 'id="sitePhoto"', '<div class="panel"')
    if not span:
        print("  [FAIL] 找不到照片面板")
        return 1
    start, end = span
    panel = body[start:end]
    print(f"  [信息] 照片面板 {len(panel)} 字符")

    # 用入口替代它
    body = body[:start] + ASK_PLACEHOLDER.rstrip("\n") + body[end:]
    print("  [ok] ask 页照片面板已换成跳转入口")

    # ---- 2) Hero 结构 ----
    for note, old, new in [
        ("Hero 改双栏", HERO_OLD, HERO_NEW),
        ("主标题换成图像识别", H2_OLD, H2_NEW),
        ("价值说明改写", LEAD_OLD, LEAD_NEW),
        ("左栏收尾 + 工作台容器", COPY_CLOSE_OLD, COPY_CLOSE_NEW),
    ]:
        if old in body:
            body = body.replace(old, new, 1)
            applied += 1
            print(f"  [ok] {note}")
        else:
            print(f"  [FAIL] {note} 锚点未匹配")
            return 1

    # ---- 3) 把面板放进工作台容器 ----
    marker = '''        <div class="hero-workbench" id="heroWorkbench">
          <!-- AI 识别工作台：从「问安全」页整体搬来，全站共用一套逻辑 -->
        </div>'''
    if marker in body:
        # 面板原本缩进 6 空格，容器内再缩进两级
        indented = "\n".join(
            ("  " + line) if line.strip() else line
            for line in panel.split("\n")
        )
        body = body.replace(marker, '''        <div class="hero-workbench" id="heroWorkbench">
          <!-- AI 识别工作台：从「问安全」页整体搬来，全站共用一套逻辑 -->
''' + indented + '''
        </div>''', 1)
        applied += 1
        print("  [ok] 工作台已放入 Hero 右侧")
    else:
        print("  [FAIL] 找不到工作台容器")
        return 1

    if "第 24 轮 B · 首页 Hero 双栏" not in tiers:
        tiers = tiers.rstrip() + CSS
        applied += 1
        print("  [ok] 样式已加入")

    if body.count(chr(92)):
        print("[FAIL] body 含反斜杠")
        return 1
    # 关键：确认 id 只出现一次，没搬重
    for sid in ("sitePhoto", "photoButton", "photoStage", "photoResult"):
        count = len(re.findall(rf'id="{sid}"', body))
        if count != 1:
            print(f"  [FAIL] {sid} 出现 {count} 次（应为 1）")
            return 1
    print("  [ok] 关键 id 各出现 1 次，无重复逻辑")

    if args.dry_run:
        print(f"（dry-run，未写入；{applied} 处）")
        return 0
    BODY.write_text(body, encoding="utf-8")
    TIERS.write_text(tiers, encoding="utf-8")
    print(f"[ok] 已写入（{applied} 处）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
