"""修正顶栏两个胶囊的语义（第 16 轮 §5 第 5 条）。

问题（实测）：
  headerRole  = "工种未选择"（常驻）
  modelStatus = "离线检索模式"（常驻）

"离线检索模式"听起来像一个可选功能模式，实际上是**模型没连上的降级状态**。
把降级状态做成常驻功能标签会误导用户。

修法：
  · modelStatus：模型可用时**退场**（不占位）；不可用时说清是降级 +
    影响（检索摘要仍可用）+ 下一步（管理员配置）
  · headerRole：未选工种时**隐藏**，不要用"工种未选择"占位

用法：python patch_header_pills.py [--dry-run]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
SCRIPT_A = BUILD / "index_script_a.js"
SCRIPT_B = BUILD / "index_script_b.js"

# ---- modelStatus（在 b）----
PILL_OLD = '''var pill = $("modelStatus"); if (pill) { pill.textContent = model.available ? ("在线模型已连接：" + (model.model || "已配置")) : "离线检索模式"; pill.classList.toggle("offline", !model.available); pill.title = model.detail || ""; }'''

PILL_NEW = '''var pill = $("modelStatus"); if (pill) { if (model.available) { pill.hidden = true; pill.textContent = ""; pill.classList.remove("offline"); } else { pill.hidden = false; pill.textContent = "未连接模型 · 当前为检索摘要"; pill.classList.add("offline"); pill.title = (model.detail || "未配置模型服务地址") + "；检索摘要仍可用，成段解释需管理员配置 SITESHAHA_LLM_*"; } }'''

# ---- headerRole（在 a）----
ROLE_OLD = '''head.textContent = role ? "当前工种：" + role : "工种未选择";
        head.classList.toggle("offline", !role);'''

ROLE_NEW = '''/* 未选工种时不显示"工种未选择"——空状态不该做成常驻标签（§5 第 5 条） */
        head.hidden = !role;
        head.textContent = role ? "当前工种：" + role : "";
        head.classList.toggle("offline", !role);'''

ROLE_STYLE_OLD = '''head.setAttribute("style", role
          ? "background:#123f2a;color:#7ee0a8;border-color:#1f5c3c"
          : "background:#123a61;color:#a9c1d8;border-color:#1d4d7a");'''

ROLE_STYLE_NEW = '''head.setAttribute("style", role
          ? "background:var(--brand);color:#fff;border-color:var(--brand)"
          : "");'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    applied = 0
    text_b = SCRIPT_B.read_text(encoding="utf-8")
    text_a = SCRIPT_A.read_text(encoding="utf-8")

    if "未连接模型 · 当前为检索摘要" not in text_b:
        if PILL_OLD in text_b:
            text_b = text_b.replace(PILL_OLD, PILL_NEW, 1)
            applied += 1
            print("[ok] modelStatus：模型可用时退场，不可用时说明降级与下一步")
        else:
            print("[跳过] modelStatus 锚点未匹配")
    else:
        print("[跳过] modelStatus 已修正")

    if "head.hidden = !role;" not in text_a:
        if ROLE_OLD in text_a:
            text_a = text_a.replace(ROLE_OLD, ROLE_NEW, 1)
            applied += 1
            print("[ok] headerRole：未选工种时隐藏")
        else:
            print("[跳过] headerRole 锚点未匹配")
    else:
        print("[跳过] headerRole 已修正")

    if ROLE_STYLE_OLD in text_a:
        text_a = text_a.replace(ROLE_STYLE_OLD, ROLE_STYLE_NEW, 1)
        applied += 1
        print("[ok] headerRole 内联色改为品牌色令牌（原来硬编码深绿/深蓝）")

    for name, text in (("a", text_a), ("b", text_b)):
        if text.count(chr(92)):
            print(f"[FAIL] {name} 含反斜杠")
            return 1
    print("[ok] 无反斜杠")

    if args.dry_run:
        print(f"（dry-run，未写入；{applied} 处）")
        return 0
    SCRIPT_A.write_text(text_a, encoding="utf-8")
    SCRIPT_B.write_text(text_b, encoding="utf-8")
    print(f"[ok] 已写入（{applied} 处）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
