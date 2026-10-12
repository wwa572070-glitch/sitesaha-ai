"""§5-1 KPI 指标条升级（第 21 轮）。

现状：4 个等权白色格子（知识片段 / 入库文档 / 真实案例 / 测验成绩），
      视觉上没有主次，看不出哪个和自己有关。

改法（严格按指令）：
  1. 建立层级：前 3 项是系统元数据，第 4 项「测验成绩」是**用户自己的**安全知识水平，
     给它视觉优先级（主格 + 环形进度）
  2. 环形图**只用真实比例**：测验成绩 bestCorrect/total 是真实分母，
     训练进度 done/steps 也是。其余三项没有有效分母，**不画环**，保持纯数字
  3. 环形图用 SVG，零依赖；带 role="img" 与 aria-label（不能只靠颜色表意）
  4. 尊重 prefers-reduced-motion

数据来源（已核对 /api/status 与 /api/cases）：
  stats.chunks / stats.documents / cases 数量 / quiz.bestCorrect

用法：python patch_kpi_strip.py [--dry-run]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
BODY = BUILD / "index_body.html"
SCRIPT_A = BUILD / "index_script_a.js"
TIERS = BUILD / "v16_tiers.css"

OLD_KPI = '''      <!-- ============ L2 指标条：4 个数字 ============ -->
      <div class="tier-l2" role="group" aria-label="知识库与学习状态">
        <div class="l2-cell">
          <div class="l2-num"><span id="kpiChunks">--</span><span class="unit">条</span></div>
          <div class="l2-label">知识片段</div>
          <div class="l2-note" id="kpiChunksNote">正在读取知识库</div>
        </div>
        <div class="l2-cell">
          <div class="l2-num"><span id="kpiDocs">--</span><span class="unit">份</span></div>
          <div class="l2-label">入库文档</div>
          <div class="l2-note" id="kpiDocsNote">安全法规 / 项目制度 / 培训资料</div>
        </div>
        <div class="l2-cell">
          <div class="l2-num"><span id="kpiCases">--</span><span class="unit">例</span></div>
          <div class="l2-label">真实案例</div>
          <div class="l2-note">事故与隐患通报整理</div>
        </div>'''

NEW_KPI = '''      <!-- ============ L2 指标条：主指标 + 支撑指标 ============ -->
      <div class="tier-l2" role="group" aria-label="知识库与学习状态">

        <!-- 主指标：用户自己的安全知识水平（唯一有真实分母的指标） -->
        <div class="l2-cell is-primary">
          <div class="l2-ring-wrap">
            <svg class="l2-ring" id="kpiRing" viewBox="0 0 48 48" role="img"
                 aria-labelledby="kpiRingLabel">
              <title id="kpiRingLabel">安全知识测验最佳成绩</title>
              <circle class="l2-ring-track" cx="24" cy="24" r="20"/>
              <circle class="l2-ring-fill" id="kpiRingFill" cx="24" cy="24" r="20"
                      stroke-dasharray="125.66" stroke-dashoffset="125.66"/>
            </svg>
            <div class="l2-ring-center">
              <span class="l2-ring-pct" id="kpiRingPct">--</span>
              <span class="l2-ring-unit">%</span>
            </div>
          </div>
          <div class="l2-primary-text">
            <div class="l2-label">我的安全知识</div>
            <div class="l2-num l2-num-sm"><span id="kpiQuiz">0/20</span></div>
            <div class="l2-note" id="kpiQuizNote">还没有测验记录</div>
          </div>
        </div>

        <!-- 支撑指标：系统知识库规模（无有效分母，不画环） -->
        <div class="l2-cell">
          <div class="l2-num"><span id="kpiChunks">--</span><span class="unit">条</span></div>
          <div class="l2-label">知识片段</div>
          <div class="l2-note" id="kpiChunksNote">正在读取知识库</div>
        </div>
        <div class="l2-cell">
          <div class="l2-num"><span id="kpiDocs">--</span><span class="unit">份</span></div>
          <div class="l2-label">入库文档</div>
          <div class="l2-note" id="kpiDocsNote">安全法规 / 项目制度 / 培训资料</div>
        </div>
        <div class="l2-cell">
          <div class="l2-num"><span id="kpiCases">--</span><span class="unit">例</span></div>
          <div class="l2-label">真实案例</div>
          <div class="l2-note">事故与隐患通报整理</div>
        </div>'''

# 原来的第 4 格（测验）要删掉，因为已移到主格
OLD_KPI4 = '''        <div class="l2-cell">
          <div class="l2-num"><span id="kpiQuiz">0/20</span></div>
          <div class="l2-label"'''

CSS = """

/* ==========================================================================
   §5-1 KPI 指标条（第 21 轮）
   --------------------------------------------------------------------------
   原来 4 个格子等权，看不出哪个和自己有关。
   现在：主格（我的安全知识，带环形图）+ 3 个支撑格。
   环形图只用真实分母，不编造百分比。
   ========================================================================== */
.tier-l2 { align-items: stretch; }
.l2-cell.is-primary {
  display: flex; align-items: center; gap: 14px;
  flex: 1 1 260px;
  background: linear-gradient(135deg, var(--brand-050), var(--surface) 62%);
  border-color: var(--brand-100);
}
.l2-ring-wrap { position: relative; width: 64px; height: 64px; flex: 0 0 auto; }
.l2-ring { width: 64px; height: 64px; display: block; transform: rotate(-90deg); }
.l2-ring-track {
  fill: none; stroke: var(--brand-100); stroke-width: 6;
}
.l2-ring-fill {
  fill: none; stroke: var(--accent); stroke-width: 6; stroke-linecap: round;
  transition: stroke-dashoffset .6s cubic-bezier(.22,.61,.36,1);
}
.l2-ring-center {
  position: absolute; inset: 0;
  display: flex; align-items: center; justify-content: center;
  font-variant-numeric: tabular-nums; pointer-events: none;
}
.l2-ring-pct { font-size: var(--fs-md); font-weight: 800; color: var(--brand); }
.l2-ring-unit { font-size: var(--fs-xs); color: var(--i500); margin-left: 1px; }
.l2-primary-text { min-width: 0; }
.l2-num-sm { font-size: var(--fs-xl); }

@media (max-width: 640px) {
  .l2-cell.is-primary { flex: 1 1 100%; }
  .l2-ring-wrap, .l2-ring { width: 56px; height: 56px; }
}

@media (prefers-reduced-motion: reduce) {
  .l2-ring-fill { transition: none; }
}
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    applied = 0
    body = BODY.read_text(encoding="utf-8")
    tiers = TIERS.read_text(encoding="utf-8")

    if 'id="kpiRing"' in body:
        print("  [跳过] KPI 指标条已改")
    elif OLD_KPI in body:
        body = body.replace(OLD_KPI, NEW_KPI, 1)
        applied += 1
        print("  [ok] KPI 主格 + 环形图已加入")
    else:
        print("  [FAIL] KPI 锚点未匹配")
        return 1

    # 删掉原来的第 4 格测验（已移到主格）—— 用正则定位整块
    if body.count('id="kpiQuiz"') > 1:
        import re
        pattern = re.compile(
            r'\n        <div class="l2-cell">\s*\n'
            r'\s*<div class="l2-num"><span id="kpiQuiz">.*?</div>\s*\n\s*</div>',
            re.S,
        )
        new_body, n = pattern.subn("", body, count=1)
        if n:
            body = new_body
            applied += 1
            print("  [ok] 删掉重复的第 4 格（测验已移到主格）")
        else:
            print("  [注意] 第 4 格未匹配，可能有重复 kpiQuiz")

    if "§5-1 KPI 指标条" not in tiers:
        tiers = tiers.rstrip() + CSS
        applied += 1
        print("  [ok] 样式已加入")

    if body.count(chr(92)):
        print("[FAIL] body 含反斜杠")
        return 1
    print("[ok] 无反斜杠")

    if args.dry_run:
        print(f"（dry-run，未写入；{applied} 处）")
        return 0
    BODY.write_text(body, encoding="utf-8")
    TIERS.write_text(tiers, encoding="utf-8")
    print(f"[ok] 已写入（{applied} 处）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
