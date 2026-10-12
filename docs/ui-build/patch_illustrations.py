"""§5-4 四张线稿插画：补第 4 张 + 把 4 张接进页面（第 21 轮）。

发现：现有 ill-edge / ill-scaffold / ill-ppe 三张**定义在雪碧图里但从未被引用**，
      等于死代码。所以本脚本做两件事：
        1. 补第 4 张 ill-emergency（应急三步骤）
        2. 把 4 张真正接进各页（空状态 / 引导图）

风格对齐现有 ill-edge：
  viewBox 240x130、纯 path 细线、currentColor、font-size 11 的中文标注。

应急三步骤用**项目自己已确认的流程**：停 → 撤 → 报
（来自应急页红警带的「停手 · 撤到安全区 · 报告负责人」），
不是外部编造的通用步骤。

用法：python patch_illustrations.py [--dry-run]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
BODY = BUILD / "index_body.html"
TIERS = BUILD / "v16_tiers.css"

# ---- 第 4 张：应急三步骤（停 → 撤 → 报）----
ILL_EMERGENCY = '''  <symbol id="ill-emergency" viewBox="0 0 240 130">
    <path d="M8 120h224"/>
    <!-- 第一步：停手 -->
    <path d="M30 100V70h6V56a4 4 0 0 1 8 0v14h4V52a4 4 0 0 1 8 0v18h4V58a4 4 0 0 1 8 0v16h4V66a4 4 0 0 1 8 0v20a14 14 0 0 1-14 14H44a14 14 0 0 1-14-14z"/>
    <path d="M24 44h44" stroke-width="2.5"/>
    <text x="24" y="36" font-size="11" fill="currentColor">1 停手</text>
    <text x="20" y="116" font-size="10" fill="currentColor">停止作业</text>
    <!-- 第二步：撤离 -->
    <path d="M104 104V82a5 5 0 0 1 10 0v22"/>
    <path d="M109 74a5 5 0 1 0 0-10 5 5 0 0 0 0 10z"/>
    <path d="M104 88l-8 10M114 88l8 10"/>
    <path d="M132 92h34"/>
    <path d="M158 84l10 8-10 8"/>
    <text x="100" y="36" font-size="11" fill="currentColor">2 撤离</text>
    <text x="98" y="116" font-size="10" fill="currentColor">撤到安全区</text>
    <!-- 第三步：报告 -->
    <path d="M186 78h30a4 4 0 0 1 4 4v24a4 4 0 0 1-4 4h-30a4 4 0 0 1-4-4V82a4 4 0 0 1 4-4z"/>
    <path d="M192 96h18"/>
    <path d="M196 66c0-6 4-10 9-10s9 4 9 10" />
    <path d="M205 56v6"/>
    <text x="184" y="36" font-size="11" fill="currentColor">3 报告</text>
    <text x="180" y="116" font-size="10" fill="currentColor">报告负责人</text>
  </symbol>

'''

# ---- 插图组件样式 ----
CSS = """

/* ==========================================================================
   §5-4 线稿插画（第 21 轮）
   --------------------------------------------------------------------------
   四张统一风格工程线稿：临边防护 / 脚手架 / PPE 六件套 / 应急三步骤。
   全部 currentColor，随主题变色，无外部图片依赖。
   ========================================================================== */
.ill-figure {
  margin: 0; padding: 12px 14px;
  border: 1px solid var(--line); border-radius: var(--r-sm);
  background: var(--surface-soft);
  color: var(--brand-600);
}
.ill-figure > svg {
  display: block; width: 100%; height: auto;
  max-width: 420px; margin: 0 auto;
  fill: none; stroke: currentColor; stroke-width: 1.6;
  stroke-linecap: round; stroke-linejoin: round;
}
.ill-figure figcaption {
  margin-top: 8px; font-size: var(--fs-xs); line-height: 1.6;
  color: var(--i600); text-align: center;
}
.ill-figure.is-compact > svg { max-width: 300px; }

/* 插画内的文字不要描边 */
.ill-figure > svg text { stroke: none; fill: currentColor; }

@media (max-width: 640px) {
  .ill-figure { padding: 10px; }
}
"""

# ---- 接入点 ----
# 1) 应急页：红警带之后（三步骤引导图）
EMERGENCY_ANCHOR = '''      <div class="panel">

        <div class="panel-head"><h2>选择发生的情况</h2>'''

EMERGENCY_FIGURE = '''      <figure class="ill-figure ill-emergency">
        <svg viewBox="0 0 240 130" role="img" aria-labelledby="illEmergencyLabel">
          <title id="illEmergencyLabel">应急处置三步骤：停手、撤离到安全区、报告负责人</title>
          <use href="#ill-emergency"/>
        </svg>
        <figcaption>出事先做这三步：停手 → 撤到安全区 → 报告负责人。具体以项目应急预案和现场指挥为准。</figcaption>
      </figure>

      <div class="panel">

        <div class="panel-head"><h2>选择发生的情况</h2>'''

# 2) 首页：安全底线之前插 PPE 六件套
HOME_ANCHOR = '''      <!-- ============ L5 引用块：安全底线（6 条必须保留） ============ -->'''

HOME_FIGURE = '''      <!-- ============ §5-4 引导图：PPE 六件套 ============ -->
      <figure class="ill-figure ill-ppe">
        <svg viewBox="0 0 240 130" role="img" aria-labelledby="illPpeLabel">
          <title id="illPpeLabel">个人防护用品：安全帽、安全带、防护手套、护目镜、反光背心、安全鞋</title>
          <use href="#ill-ppe"/>
        </svg>
        <figcaption>上工前对照检查个人防护用品是否齐全、完好。</figcaption>
      </figure>

      <!-- ============ L5 引用块：安全底线（6 条必须保留） ============ -->'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    body = BODY.read_text(encoding="utf-8")
    tiers = TIERS.read_text(encoding="utf-8")
    applied = 0

    # ---- 1) 补第 4 张插画 ----
    if 'id="ill-emergency"' in body:
        print("  [跳过] ill-emergency 已存在")
    else:
        marker = "  <!-- ===== 示意图用（较大、线稿） ===== -->\n"
        if marker in body:
            body = body.replace(marker, marker + "\n" + ILL_EMERGENCY, 1)
            applied += 1
            print("  [ok] 新增 ill-emergency（应急三步骤）")
        else:
            print("  [FAIL] 找不到插画区标记")
            return 1

    # ---- 2) 应急页接入 ----
    if "ill-emergency\"" in body and 'class="ill-figure ill-emergency"' in body:
        print("  [跳过] 应急页已接入")
    elif EMERGENCY_ANCHOR in body:
        body = body.replace(EMERGENCY_ANCHOR, EMERGENCY_FIGURE, 1)
        applied += 1
        print("  [ok] 应急页接入三步骤引导图")
    else:
        print("  [注意] 应急页锚点未匹配")

    # ---- 3) 首页接入 PPE ----
    if 'class="ill-figure ill-ppe"' in body:
        print("  [跳过] 首页已接入")
    elif HOME_ANCHOR in body:
        body = body.replace(HOME_ANCHOR, HOME_FIGURE, 1)
        applied += 1
        print("  [ok] 首页接入 PPE 六件套引导图")
    else:
        print("  [注意] 首页锚点未匹配")

    # ---- 4) 样式 ----
    if "§5-4 线稿插画" not in tiers:
        tiers = tiers.rstrip() + CSS
        applied += 1
        print("  [ok] 插画样式已加入")

    if body.count(chr(92)):
        print("[FAIL] body 含反斜杠")
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
