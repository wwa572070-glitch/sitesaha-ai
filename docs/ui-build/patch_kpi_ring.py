"""§5-1b 环形图接真实数据 + 微交互（第 21 轮）。

环形图必须用真实比例：
  测验成绩 bestCorrect / (total || 20)
  没有测验记录时显示 "--"，不画环，不编造百分比。

微交互（指令 §5-2）：
  · 首次展示平滑过渡到真实进度（stroke-dashoffset 过渡）
  · 数值变化时同步更新环与文字
  · 防止重复渲染闪烁：百分比没变就不重设属性
  · 尊重 prefers-reduced-motion（在 CSS 里已处理，JS 里也不做额外动画）

用法：python patch_kpi_ring.py [--dry-run]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
SCRIPT_A = BUILD / "index_script_a.js"

# 在更新 kpiQuiz 的地方后面接上环形图更新
OLD = '''      var kpiQuiz = $("kpiQuiz");
      if (kpiQuiz) {
        var quiz = readStore(QUIZ_KEY, EMPTY_QUIZ);
        kpiQuiz.textContent = quiz.bestCorrect + "/" + (quiz.total || 20);
        var note = $("kpiQuizNote");
        if (note) note.textContent = quiz.attempts ? ("已测 " + quiz.attempts + " 次 · 历史最佳") : "本地保存，仅自己可见";
      }'''

NEW = '''      var kpiQuiz = $("kpiQuiz");
      if (kpiQuiz) {
        var quiz = readStore(QUIZ_KEY, EMPTY_QUIZ);
        var quizTotal = quiz.total || 20;
        var quizBest = quiz.bestCorrect || 0;
        kpiQuiz.textContent = quizBest + "/" + quizTotal;
        var note = $("kpiQuizNote");
        if (note) {
          note.textContent = quiz.attempts
            ? ("已测 " + quiz.attempts + " 次 · 历史最佳")
            : "还没有测验记录";
        }
        updateKpiRing(quiz.attempts ? quizBest : null, quizTotal);
      }'''

# 环形图更新函数：插入到 updateKpi 所在函数之前
RING_FUNC = '''    /* ==================================================================
       §5-1 KPI 环形进度（第 21 轮）
       ------------------------------------------------------------------
       只用真实比例。没有测验记录时（best 为 null）显示 "--" 且不画环，
       不编造百分比。

       周长 = 2 * PI * 20 = 125.66，与 markup 里的 stroke-dasharray 一致。
       ================================================================== */
    var KPI_RING_LENGTH = 125.66;
    var kpiRingShown = -1;

    function updateKpiRing(best, total) {
      var ring = $("kpiRing");
      var fill = $("kpiRingFill");
      var pctLabel = $("kpiRingPct");
      if (!ring || !fill || !pctLabel) return;

      if (best === null || best === undefined || !total) {
        /* 没有有效分母 —— 不画环 */
        if (kpiRingShown !== -1) {
          fill.style.strokeDashoffset = String(KPI_RING_LENGTH);
          pctLabel.textContent = "--";
          ring.setAttribute("aria-label", "安全知识测验还没有记录");
          kpiRingShown = -1;
        }
        return;
      }

      var percent = Math.max(0, Math.min(100, Math.round((best / total) * 100)));
      /* 值没变就不重设，避免重复渲染闪烁 */
      if (percent === kpiRingShown) return;
      kpiRingShown = percent;

      fill.style.strokeDashoffset = String(KPI_RING_LENGTH * (1 - percent / 100));
      pctLabel.textContent = String(percent);
      ring.setAttribute("aria-label",
        "安全知识测验最佳成绩 " + best + " / " + total + "，正确率 " + percent + "%");
    }

'''

ANCHOR = "    var kpiQuiz = $(\"kpiQuiz\");"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    text = SCRIPT_A.read_text(encoding="utf-8")
    applied = 0

    if "updateKpiRing" in text:
        print("  [跳过] 环形图逻辑已接入")
    else:
        # 先插函数定义（找到外层函数起点之前的合适位置）
        marker = "    function updateKpi("
        if marker not in text:
            # 退而求其次：插在 kpiQuiz 使用处所在的函数之前
            position = text.find(ANCHOR)
            start = text.rfind("    function ", 0, position)
            if start < 0:
                print("  [FAIL] 找不到插入点")
                return 1
            text = text[:start] + RING_FUNC + text[start:]
        else:
            text = text.replace(marker, RING_FUNC + marker, 1)
        applied += 1
        print("  [ok] updateKpiRing 函数已定义")

        old = "\n\n".join(OLD.split("\n"))
        new = "\n\n".join(NEW.split("\n"))
        if old in text:
            text = text.replace(old, new, 1)
            applied += 1
            print("  [ok] 测验数据已接到环形图")
        elif OLD in text:
            text = text.replace(OLD, NEW, 1)
            applied += 1
            print("  [ok] 测验数据已接到环形图（无空行格式）")
        else:
            print("  [注意] kpiQuiz 更新块锚点未匹配，环形图不会更新")
            # 回滚函数定义，避免留下死代码
            text = text.replace(RING_FUNC, "", 1)
            print("  [已回滚] 避免留下未使用的函数")
            return 1

    if text.count(chr(92)):
        print("[FAIL] 含反斜杠")
        return 1
    print("  [ok] 无反斜杠")

    if args.dry_run:
        print(f"（dry-run，未写入；{applied} 处）")
        return 0
    SCRIPT_A.write_text(text, encoding="utf-8")
    print(f"[ok] 已写入（{applied} 处）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
