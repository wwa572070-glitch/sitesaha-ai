"""第二轮 UI 精修：桌面宽度 + 首屏层级（第 27 轮）。

实测发现的核心问题：
  main { max-width: 1024px } —— 在 1440 屏上左右各空 208px，空间利用不足。

按指令「不要把所有页面都扩大到同一个宽度」分层设定：
  首页   1280px  工作台要横向空间
  问答页 1020px  阅读为主，太宽反而难看
  其他   1200px  卡片与表格

首屏层级：
  1. 左栏加入 ill-edge 临边防护线稿（已有素材，复用）
  2. 每日案例默认收起（次级信息，不再抢首屏下方的注意力）
  3. 辅助文字提升到可读尺寸

用法：python patch_round2_layout.py [--dry-run]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
BODY = BUILD / "index_body.html"
TIERS = BUILD / "v16_tiers.css"

CSS = """

/* ==========================================================================
   第 27 轮 · 桌面宽度分层 + 首屏层级
   --------------------------------------------------------------------------
   原来 main 固定 1024px，1440 屏两侧各空 208px。
   不同内容类型需要不同宽度：
     首页要宽（工作台横向布局）· 问答页要窄（阅读舒适）· 其他居中
   ========================================================================== */
:root {
  --w-home: 1280px;
  --w-ask: 1020px;
  --w-wide: 1200px;
}

main { max-width: var(--w-home); }
.header-inner, .nav-inner, footer { max-width: var(--w-home); }

/* 问答页：阅读为主，收窄并居中 */
#ask.view > .panel,
#ask.view > .notice {
  max-width: var(--w-ask);
  margin-left: auto;
  margin-right: auto;
}

/* 应急页：流程与卡片，比问答宽、比首页窄 */
#sos.view > .panel,
#sos.view > .sos-alert,
#sos.view > .ill-figure {
  max-width: 1080px;
  margin-left: auto;
  margin-right: auto;
}

/* 班前与学习：卡片与表格，用中宽 */
#pre.view > .panel,
#learn.view > .panel,
#pre.view > .disclosure,
#learn.view > .disclosure {
  max-width: var(--w-wide);
  margin-left: auto;
  margin-right: auto;
}

/* 首屏：左栏线稿作为辅助视觉，不与标题争注意力 */
.hero-copy .hero-ill {
  margin: 20px 0 0;
  padding: 12px 16px;
  border-radius: var(--r-md);
  background: rgba(255, 255, 255, .06);
  border: 1px solid rgba(255, 255, 255, .12);
}
.hero-copy .hero-ill svg {
  display: block; width: 100%; height: auto; max-width: 340px;
  fill: none; stroke: var(--i300); stroke-width: 1.4;
  stroke-linecap: round; stroke-linejoin: round;
}
.hero-copy .hero-ill figcaption {
  margin-top: 8px; font-size: var(--fs-xs); line-height: 1.6; color: var(--i400);
}

/* 辅助文字下限：保证在真实屏幕上可读 */
.answer-meta, .head-note, .l2-note, .disclosure-hint {
  font-size: max(var(--fs-xs), 12px);
}

@media (max-width: 1360px) {
  main { max-width: 1160px; }
}
@media (max-width: 1100px) {
  main { max-width: 100%; }
  #ask.view > .panel, #sos.view > .panel, #pre.view > .panel, #learn.view > .panel {
    max-width: 100%;
  }
}
"""

# 首屏左栏插入线稿
ILL_BLOCK = '''        <figure class="hero-ill">
          <svg viewBox="0 0 240 130" role="img" aria-labelledby="heroIllLabel">
            <title id="heroIllLabel">临边防护做法：栏杆 1.2 米、设中间防护、挡脚板不低于 180 毫米</title>
            <use href="#ill-edge"/>
          </svg>
          <figcaption>识别结果会指出风险在画面的哪个位置，方便你对着照片核对。</figcaption>
        </figure>

'''

COPY_CLOSE = '''        <div id="homeRoleHint" class="l1-rolehint">还没有选择工种 —— 未选择时按通用要点回答，选择后会自动带上本工种的主要风险与必守规矩。</div>
        </div><!-- /hero-copy -->'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    body = BODY.read_text(encoding="utf-8")
    tiers = TIERS.read_text(encoding="utf-8")
    applied = 0

    # 1) 左栏加线稿
    if "hero-ill" in body:
        print("  [跳过] 首屏线稿已存在")
    elif COPY_CLOSE in body:
        body = body.replace(
            COPY_CLOSE,
            '        <div id="homeRoleHint" class="l1-rolehint">还没有选择工种 —— 未选择时按通用要点回答，选择后会自动带上本工种的主要风险与必守规矩。</div>\n'
            + ILL_BLOCK
            + '        </div><!-- /hero-copy -->',
            1,
        )
        applied += 1
        print("  [ok] 首屏左栏加入临边防护线稿")
    else:
        print("  [注意] 找不到 hero-copy 结尾，跳过线稿")

    # 2) 每日案例默认收起
    if 'id="homeDailyCase"' in body and '每日警示案例' in body:
        marker = '<h2>每日警示案例</h2>'
        if marker in body and 'dailyCaseWrap' not in body:
            index = body.find(marker)
            start = body.rfind('<div class="tier-l4">', 0, index)
            if start > 0:
                tag = re.compile(r"<(/?)(div)\b[^>]*?(/?)>")
                depth = 0
                position = start
                end = None
                while position < len(body):
                    m = tag.search(body, position)
                    if not m:
                        break
                    position = m.end()
                    if m.group(1) == "/":
                        depth -= 1
                        if depth == 0:
                            end = m.end()
                            break
                    elif m.group(3) != "/":
                        depth += 1
                if end:
                    block = body[start:end]
                    body = (
                        body[:start]
                        + '<details class="disclosure daily-case" id="dailyCaseWrap">\n'
                        + '  <summary>每日警示案例<span class="disclosure-hint">每天轮换一条，点开看</span></summary>\n'
                        + '  <div class="disclosure-body">\n' + block + '\n  </div>\n'
                        + '</details>'
                        + body[end:]
                    )
                    applied += 1
                    print("  [ok] 每日警示案例改为默认收起")
                else:
                    print("  [注意] 找不到案例块边界")
            else:
                print("  [注意] 找不到 tier-l4 起点")
        else:
            print("  [跳过] 每日案例已处理")
    else:
        print("  [跳过] 未找到每日案例模块")

    # 3) 样式
    if "第 27 轮 · 桌面宽度分层" not in tiers:
        tiers = tiers.rstrip() + CSS
        applied += 1
        print("  [ok] 宽度分层与线稿样式已加入")

    for name, text in (("body", body), ("tiers", tiers)):
        if text.count(chr(92)):
            print(f"[FAIL] {name} 含反斜杠")
            return 1
    print("  [ok] 无反斜杠")

    if args.dry_run:
        print(f"（dry-run，未写入；{applied} 处）")
        return 0
    BODY.write_text(body, encoding="utf-8")
    TIERS.write_text(tiers, encoding="utf-8")
    print(f"[ok] 已写入（{applied} 处）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
