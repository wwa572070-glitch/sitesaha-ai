"""修两类回归（第 16 轮）。

问题 1：textContent 赋 SVG 字符串会显示成原始代码
  button.textContent = '<svg ...>' 会被当成**纯文本**转义，页面上直接看到标签。
  实测在顶栏主题按钮上看到了 "<svg class=\"ico\" ...> 夜间" 这样的字面量。
  修法：这 4 处改用 innerHTML。图标是我们自己写的常量字符串，不含用户输入，
  不引入 XSS 风险。

问题 2：.avatar / .step-order 的对比度修复被后续分片吸附覆盖
  V15 里原本写过正确颜色，但后面的字号/间距重写把它冲掉了，
  导致退回基础层的 var(--amber) on var(--i800)（3.21:1）。
  修法：在 v17_palette.css 末尾重新声明，位置在所有分片之后，确保生效。

用法：python fix_innerhtml_and_contrast.py [--dry-run]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
A = BUILD / "index_script_a.js"
B = BUILD / "index_script_b.js"
PALETTE = BUILD / "v17_palette.css"

CONTRAST_BLOCK = """

/* ==========================================================================
   头像与步骤序号的对比度（重新声明）
   --------------------------------------------------------------------------
   基础层里写着 var(--amber) on var(--i800)，对比度只有 3.21:1。
   之前修过一次，但被后续分片的字号/间距重写冲掉了，这里放在所有分片之后，
   确保它是最终生效值。
   ========================================================================== */
.avatar {
  background: var(--i800); color: #ffffff; font-weight: 800;
}
.msg-row.from-user .avatar {
  background: var(--accent); color: var(--brand-700);
}
.step-order {
  background: var(--brand); color: #ffffff; font-weight: 800;
}
.step-item.is-done .step-order {
  background: var(--risk-low-bg); color: var(--risk-low-text);
  border-color: var(--risk-low);
}
[data-theme="dark"] .avatar { background: #3a434e; color: #ffffff; }
[data-theme="dark"] .msg-row.from-user .avatar { background: var(--accent); color: #1a1206; }
[data-theme="dark"] .step-order { background: var(--brand); color: #10151a; }
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    fixed = 0
    for path in (A, B):
        text = path.read_text(encoding="utf-8")
        # 只改「赋值右侧是 SVG 字符串」的 textContent
        pattern = re.compile(r"(\.textContent\s*=\s*)((?:[^;\n]*?)?'<svg)")

        def repl(match: re.Match[str]) -> str:
            nonlocal fixed
            fixed += 1
            return match.group(1).replace(".textContent", ".innerHTML") + match.group(2)

        text, count = pattern.subn(repl, text)
        if count:
            print(f"  [ok] {path.name}: textContent → innerHTML {count} 处")
            path.write_text(text, encoding="utf-8")

    if fixed == 0:
        print("[跳过] 没有需要改的 textContent")

    palette = PALETTE.read_text(encoding="utf-8")
    if "头像与步骤序号的对比度（重新声明）" not in palette:
        palette = palette.rstrip() + CONTRAST_BLOCK
        if not args.dry_run:
            PALETTE.write_text(palette, encoding="utf-8")
        print("[ok] 已重新声明 .avatar / .step-order 对比度")
    else:
        print("[跳过] 对比度块已存在")

    if not args.dry_run:
        for path in (A, B):
            if path.read_text(encoding="utf-8").count(chr(92)):
                print(f"[FAIL] {path.name} 含反斜杠")
                return 1
    print("[ok] 无反斜杠")
    return 0


if __name__ == "__main__":
    sys.exit(main())
