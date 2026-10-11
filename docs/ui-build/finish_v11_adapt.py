"""V11 适配收尾：清理失效元素引用、更新检查项类名、补语音与朗读逻辑。

用法：python finish_v11_adapt.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
SCRIPT_A = BUILD / "index_script_a.js"
SCRIPT_B = BUILD / "index_script_b.js"


def drop_function(text: str, signature: str, label: str) -> tuple[str, str]:
    """删除一个顶层函数定义（含结尾的空行）。"""
    start = text.find(signature)
    if start < 0:
        return text, f"{label}：未找到定义"
    end = text.find("\n    }\n", start)
    if end < 0:
        return text, f"{label}：未找到结束位置"
    end += len("\n    }\n")
    return text[:start] + text[end:], ""


def main() -> int:
    problems: list[str] = []

    # ---------------- script_b ----------------
    b = SCRIPT_B.read_text(encoding="utf-8")

    # 1) 消息行类名
    b = b.replace('make("div", "msg-row from-user")', 'make("div", "msg me")')
    b = b.replace('make("div", "msg-row")', 'make("div", "msg")')

    # 2) 检查项类名（V11 用 .on 而不是 .checked）
    b = b.replace('make("label", "check-item" + (state[key] ? " checked" : ""))',
                  'make("label", state[key] ? "on" : "")')
    b = b.replace('document.querySelectorAll("#checklist .check-item").forEach(function (item) { item.classList.remove("checked"); });',
                  'document.querySelectorAll("#checklist label").forEach(function (item) { item.classList.remove("on"); });')

    # 3) 删除音色选择控件（V11 去掉这个下拉）
    b, err = drop_function(b, "    function buildVoiceControl() {", "buildVoiceControl")
    if err:
        problems.append(err)
    else:
        print("[ok] 删除 buildVoiceControl")

    # 删掉调用与回调
    b = re.sub(r"\n *var speakPauseButton = null;", "", b)
    b = re.sub(r"\n *var preferredVoiceName = \"\";", "\n    var preferredVoiceName = \"\";", b)
    b = re.sub(r"\n *if \(\"speechSynthesis\" in window\) \{\n(?:.*\n)*?    \}\n", "\n", b, count=1)
    b = b.replace("      if (typeof window.speechSynthesis.onvoiceschanged !== \"undefined\") {\n        window.speechSynthesis.onvoiceschanged = buildVoiceControl;\n      }\n", "")

    # 4) KPI 元素 → 新的知识库概览字段
    b = b.replace("var kpiDocs = $(\"kpiDocs\");", "var kpiDocs = $(\"chunkCount\");")
    b = b.replace("var kpiChunks = $(\"kpiChunks\");", "var kpiChunks = $(\"documentCount\");")
    b = re.sub(r'\n *var note = \$\("kpiChunksNote"\);\n *if \(note\) note\.textContent = [^\n]*\n', "\n", b)
    b = re.sub(r'\n *var docNote = \$\("kpiDocsNote"\);\n *if \(docNote && Object\.keys\(categories\)\.length\) \{\n[^\n]*\n *\}\n', "\n", b)
    b = b.replace("var kpiCases = $(\"kpiCases\");", "var kpiCases = $(\"caseCount\");")

    SCRIPT_B.write_text(b, encoding="utf-8")
    print(f"[ok] script_b 写入，{b.count(chr(10)) + 1} 行")

    # ---------------- script_a ----------------
    a = SCRIPT_A.read_text(encoding="utf-8")
    a = a.replace('make("div", "msg-row")', 'make("div", "msg")')
    SCRIPT_A.write_text(a, encoding="utf-8")

    # ---------------- 残留检查 ----------------
    stale = ["speakVoiceRow", "kpiQuiz", "kpiChunksNote", "kpiDocsNote", "assistantRoleChips",
             "trainPathPanel", "trainQuizPanel", "msg-row", "check-item", "chatClear"]
    leftovers: list[str] = []
    for path in (SCRIPT_A, SCRIPT_B):
        text = path.read_text(encoding="utf-8")
        for marker in stale:
            if marker in text and marker != "chatClear":  # chatClear 已在结构里补回
                leftovers.append(f"{path.name}: {marker}")

    if problems:
        print("\n问题：")
        for item in problems:
            print("  -", item)
    if leftovers:
        print("\n仍有残留：")
        for item in leftovers:
            print("  -", item)
        return 1
    print("\n[OK] 收尾清理完成")
    return 0


if __name__ == "__main__":
    sys.exit(main())
