"""§2 前端：等待计时 + 超时重试（第 20 轮 P0）。

三个改动（你 §2 的第 1、2 条）：
  1. 等待气泡加预期与计时：
       0~20 秒   「通常需要 10~20 秒 · 已等待 N 秒」
       >20 秒    「网络可能较慢，仍在生成… 已等待 N 秒」
  2. 客户端 45 秒超时：到点中止，显示「这次没等到结果」+ 重试按钮
  3. 重试复用原问题，不丢输入

实现约束：分片禁止反斜杠。

用法：python patch_ask_ux.py [--dry-run]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
SCRIPT_B = BUILD / "index_script_b.js"
TIERS = BUILD / "v16_tiers.css"

OLD_THINKING = '''    function appendThinking() {
      var stream = $("chatStream");
      if (!stream) return null;
      var row = make("div", "msg-row");
      row.id = "chatThinking";
      row.appendChild(make("div", "avatar", "筑"));
      var bubble = make("div", "bubble");
      bubble.appendChild(make("div", "bubble-title", "正在检索知识库并组织回答…"));
      var dots = make("div", "thinking");
      dots.appendChild(make("i"));
      dots.appendChild(make("i"));
      dots.appendChild(make("i"));
      bubble.appendChild(dots);
      row.appendChild(bubble);
      stream.appendChild(row);
      row.scrollIntoView({ behavior: "smooth", block: "center" });
      return row;
    }'''

NEW_THINKING = '''    /* 等待期间的计时器句柄（第 20 轮 §2：让用户知道要等多久） */
    var thinkingTimer = null;
    var thinkingStartedAt = 0;
    var ASK_TIMEOUT_MS = 45000;

    function updateThinkingHint() {
      var hint = $("chatThinkingHint");
      if (!hint) return;
      var seconds = Math.round((Date.now() - thinkingStartedAt) / 1000);
      if (seconds < 20) {
        hint.textContent = "通常需要 10~20 秒 · 已等待 " + seconds + " 秒";
      } else {
        hint.textContent = "网络可能较慢，仍在生成… 已等待 " + seconds + " 秒";
      }
      hint.classList.toggle("is-slow", seconds >= 20);
    }

    function appendThinking() {
      var stream = $("chatStream");
      if (!stream) return null;
      var row = make("div", "msg-row");
      row.id = "chatThinking";
      row.appendChild(make("div", "avatar", "筑"));
      var bubble = make("div", "bubble");
      bubble.appendChild(make("div", "bubble-title", "正在检索知识库并组织回答…"));
      var dots = make("div", "thinking");
      dots.appendChild(make("i"));
      dots.appendChild(make("i"));
      dots.appendChild(make("i"));
      bubble.appendChild(dots);
      /* 预期时长 + 实时计时，避免用户以为卡死 */
      var hint = make("div", "thinking-hint");
      hint.id = "chatThinkingHint";
      hint.textContent = "通常需要 10~20 秒 · 已等待 0 秒";
      bubble.appendChild(hint);
      row.appendChild(bubble);
      stream.appendChild(row);
      row.scrollIntoView({ behavior: "smooth", block: "center" });
      thinkingStartedAt = Date.now();
      if (thinkingTimer) clearInterval(thinkingTimer);
      thinkingTimer = setInterval(updateThinkingHint, 1000);
      return row;
    }'''

OLD_REMOVE = '''    function removeThinking() {
      var node = $("chatThinking");
      if (node && node.parentNode) node.parent'''

NEW_REMOVE = '''    function removeThinking() {
      if (thinkingTimer) { clearInterval(thinkingTimer); thinkingTimer = null; }
      var node = $("chatThinking");
      if (node && node.parentNode) node.parent'''

OLD_FETCH = '''        var response = await apiFetch("/api/ask", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Access-Code": accessCode(),
          },
          body: JSON.stringify(payload),
        });
        removeThinking();'''

NEW_FETCH = '''        /* 45 秒超时：到点主动中止，不让用户无限等 */
        var controller = new AbortController();
        var timeoutId = setTimeout(function () { controller.abort(); }, ASK_TIMEOUT_MS);
        var response;
        try {
          response = await apiFetch("/api/ask", {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "X-Access-Code": accessCode(),
            },
            body: JSON.stringify(payload),
            signal: controller.signal,
          });
        } finally {
          clearTimeout(timeoutId);
        }
        removeThinking();'''

OLD_CATCH = '''      } catch (error) {
        removeThinking();
        appendAnswer(question, {
          text: "查询失败，请稍后重试或联系管理员。已保留你的问题，可以再试一次。",'''

NEW_CATCH = '''      } catch (error) {
        removeThinking();
        var waited = Math.round((Date.now() - thinkingStartedAt) / 1000);
        var aborted = error && (error.name === "AbortError" || error.code === 20);
        var failText = aborted
          ? ("这次没等到结果（已等待 " + waited + " 秒）。可能是网络较慢或模型繁忙，"
             + "你的问题还在下面，点一下就能原样重试。")
          : "查询失败，请稍后重试或联系管理员。已保留你的问题，可以再试一次。";
        var failBox = appendAnswer(question, {
          text: failText,'''

OLD_TAIL = '''          text: "查询失败，请稍后重试或联系管理员。已保留你的问题，可以再试一次。",
          mode: "error",
        }, role);
        appendUserMessage'''

NEW_TAIL = '''          mode: "error",
        }, role);
        /* 重试按钮：复用原问题，不丢输入 */
        if (failBox) {
          var retry = make("button", "secondary-button ico-button", "重试这个问题");
          retry.type = "button";
          retry.addEventListener("click", function () {
            var box = $("question");
            if (box) box.value = question;
            askQuestion();
          });
          failBox.appendChild(retry);
        }
        appendUserMessage'''

CSS = """

/* ==========================================================================
   等待提示（第 20 轮 §2）
   ========================================================================== */
.thinking-hint {
  margin-top: 8px; font-size: var(--fs-xs); color: var(--i500);
  font-variant-numeric: tabular-nums;
}
.thinking-hint.is-slow { color: var(--risk-mid-text); font-weight: 700; }
"""


def blank(text: str) -> str:
    """分片里每行之间有空行，锚点必须按这个格式给出。"""
    return "\n\n".join(text.split("\n"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    applied = 0
    text = SCRIPT_B.read_text(encoding="utf-8")
    tiers = TIERS.read_text(encoding="utf-8")

    for note, old, new in [
        ("等待气泡加预期与计时", blank(OLD_THINKING), blank(NEW_THINKING)),
        ("removeThinking 清理计时器", blank(OLD_REMOVE), blank(NEW_REMOVE)),
        ("45 秒超时中止", blank(OLD_FETCH), blank(NEW_FETCH)),
        ("失败文案区分超时/其他", blank(OLD_CATCH), blank(NEW_CATCH)),
        ("重试按钮", blank(OLD_TAIL), blank(NEW_TAIL)),
    ]:
        if old in text:
            text = text.replace(old, new, 1)
            applied += 1
            print(f"  [ok] {note}")
        else:
            print(f"  [跳过] {note}（锚点未匹配）")

    if "等待提示（第 20 轮" not in tiers:
        tiers = tiers.rstrip() + CSS
        applied += 1
        print("  [ok] 等待提示样式")

    if text.count(chr(92)):
        print(f"[FAIL] 分片含 {text.count(chr(92))} 个反斜杠")
        return 1
    print("[ok] 无反斜杠")

    if args.dry_run:
        print(f"（dry-run，未写入；{applied} 处）")
        return 0
    SCRIPT_B.write_text(text, encoding="utf-8")
    TIERS.write_text(tiers, encoding="utf-8")
    print(f"[ok] 已写入（{applied} 处）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
