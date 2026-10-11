"""重构 #home 视图为五档重量结构。

目标（第 16 轮 §3.2）：
  L1 Hero 带      视图开场身份 + 一行结论 —— 不再承载统计
  L2 指标条        可量化的状态（≤4 个数字）
  L3 主行动卡      今天上工前的三件事（可勾选）+ 我的进度
  L4 内容卡        今日警示案例（1 张卡）
  L5 引用块        安全底线（6 条必须保留）
  + 设置入口       原「我是哪个工种」降级为 L1 下方的一个设置行

不动的 id（脚本依赖）：todoList / todoFill / todoLabel / todoReset /
  homeRoleChips / homeRoleHint / kpiChunks / kpiDocs / kpiCases / kpiQuiz

用法：python rebuild_home_v16.py [--dry-run]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
BODY = BUILD / "index_body.html"

NEW_HOME = '''<section id="home" class="view active" aria-label="首页">

      <!-- ============ L1 Hero 带：视图开场，一行结论 ============ -->
      <div class="tier-l1">
        <div class="l1-kicker">
          <svg class="ico" aria-hidden="true"><use href="#i-shield"/></svg>
          新工人入场安全助手
        </div>
        <h2>不懂就问。你告诉我<em>准备做什么、看到什么、哪里不确定</em>，我用现场能听懂的话说。</h2>
        <p class="l1-lead">回答优先给能立刻执行的动作，再附规范依据和来源。高后果决策仍由现场安全员、项目交底、作业许可和应急指挥确认。</p>
        <div class="l1-foot">
          <button class="secondary-button ico-button" data-jump="voice" type="button">
            <svg class="ico" aria-hidden="true"><use href="#i-mic"/></svg>说句话问安全
          </button>
          <button class="secondary-button ico-button" data-jump="photo" type="button">
            <svg class="ico" aria-hidden="true"><use href="#i-camera"/></svg>拍照识别风险
          </button>
          <button class="ghost-button ico-button is-emergency-link" data-jump="emergency" type="button">
            <svg class="ico" aria-hidden="true"><use href="#i-phone"/></svg>应急求助
          </button>
          <span class="hint">选工种：</span>
          <div id="homeRoleChips" class="role-chips is-inline" role="group" aria-label="选择工种"></div>
        </div>
        <div id="homeRoleHint" class="l1-rolehint">还没有选择工种 —— 未选择时按通用要点回答，选择后会自动带上本工种的主要风险与必守规矩。</div>
      </div>

      <!-- ============ L2 指标条：4 个数字 ============ -->
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
        </div>
        <div class="l2-cell">
          <div class="l2-num"><span id="kpiQuiz">0/20</span></div>
          <div class="l2-label">我的测验掌握度</div>
          <div class="l2-note" id="kpiQuizNote">本地保存，仅自己可见</div>
        </div>
      </div>

      <!-- ============ L3 主行动卡：这一屏要我干什么 ============ -->
      <div class="tier-l3">
        <div class="l3-head">
          <svg class="ico ico-lg" aria-hidden="true"><use href="#i-clipboard"/></svg>
          <h2>今天上工前的三件事</h2>
          <span class="l3-badge">每班必做</span>
        </div>
        <p class="l3-lead">逐条确认。勾选结果保存在本机，刷新后仍在；发现不满足条件时先停下来报告，不要硬上。</p>
        <div id="todoList" class="todo-list"></div>
        <div class="l3-action">
          <div class="l3-progress">
            <div class="tier-progress"><i id="todoFill" style="width:0%"></i></div>
            <span id="todoLabel" class="l3-count">0 / 5</span>
          </div>
          <button id="todoReset" class="ghost-button ico-button" type="button">
            <svg class="ico" aria-hidden="true"><use href="#i-refresh"/></svg>重置
          </button>
        </div>
      </div>

      <!-- ============ L4 内容卡：今日警示案例 ============ -->
      <div class="tier-l4">
        <div class="l4-head">
          <svg class="ico" aria-hidden="true"><use href="#i-alert"/></svg>
          <h2>今日警示案例</h2>
          <span class="l4-note">每天一条，看完再上工</span>
        </div>
        <div class="l4-body" id="homeDailyCase">
          <div class="tier-skeleton" style="height:74px"></div>
        </div>
      </div>

      <!-- ============ L5 引用块：安全底线（6 条必须保留） ============ -->
      <div class="tier-l4">
        <div class="l4-head">
          <svg class="ico" aria-hidden="true"><use href="#i-shield"/></svg>
          <h2>安全底线</h2>
        </div>
        <div class="l4-body">
          <div class="tier-l5 is-danger">
            <div class="l5-ref"><span class="l5-code">底线 1</span></div>
            <div class="l5-quote"><b>先停、先撤、先报。</b>发现异常先停工撤离并报告，不擅自拆改防护、维修设备或冒险施救。</div>
          </div>
          <div class="tier-l5 is-caution">
            <div class="l5-ref"><span class="l5-code">底线 2</span></div>
            <div class="l5-quote"><b>安全底线优先于进度和评分。</b>进度和评分不能让位于安全；<b>不接受未经训练人员冒险施救</b>，高后果决策由现场安全员、交底和作业许可确认。</div>
          </div>
          <div class="tier-l5">
            <div class="l5-ref"><span class="l5-code">底线 3</span></div>
            <div class="l5-quote">本页指引<b>不替代正式规范、项目制度、作业许可和现场判断</b>，也<b>不替代现场安全管理和专项方案</b>；测验结果<b>不作为上岗资格或考核合格判定依据</b>。</div>
            <div class="l5-source">
              <svg class="ico ico-sm" aria-hidden="true"><use href="#i-doc"/></svg>
              来源：安全生产法规与标准库（可在「学习与资料 → 标准库」查条款原文）
            </div>
          </div>
        </div>
      </div>

    </section>'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    body = BODY.read_text(encoding="utf-8")
    start = body.find('<section id="home"')
    end = body.find('<section id="', start + 10)
    if start < 0 or end < 0:
        print("[FAIL] 找不到 home 区块边界")
        return 1
    old = body[start:end]

    # 保住脚本依赖的 id
    needed = ["todoList", "todoFill", "todoLabel", "todoReset", "homeRoleChips",
              "homeRoleHint", "kpiChunks", "kpiDocs", "kpiCases", "kpiQuiz"]
    lost = [i for i in needed if f'id="{i}"' in old and f'id="{i}"' not in NEW_HOME]
    if lost:
        print(f"[FAIL] 新结构丢了脚本依赖的 id：{lost}")
        return 1

    # 保住 6 条强制文案
    must = [
        "安全底线优先于进度和评分", "不接受未经训练人员冒险施救",
        "不替代正式规范、项目制度、作业许可和现场判断",
        "先停、先撤、先报", "不作为上岗资格或考核合格判定依据",
        "不替代现场安全管理和专项方案",
    ]
    missing = [t for t in must if t not in NEW_HOME]
    if missing:
        print(f"[FAIL] 新结构缺少强制文案：{missing}")
        return 1

    body = body[:start] + NEW_HOME + body[end:]
    print(f"home 区块：{len(old)} → {len(NEW_HOME)} 字符")
    print(f"  保留 id {len(needed)} 个 ✓")
    print(f"  强制文案 6 条 ✓")

    if args.dry_run:
        print("（dry-run，未写入）")
        return 0
    BODY.write_text(body, encoding="utf-8")
    print("[ok] 已写入 index_body.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
