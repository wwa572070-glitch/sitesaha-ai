"""最后一轮收尾（第 16 轮 §5）。

  1. .panel-head h2 残留的两处 13px → 15px（字号吸附脚本把它压下来了）
  2. 审计的阴影判断：只比 --shadow-1 与 --shadow-2 的**浅色**配方，
     并把 var() 别名解析掉，避免把别名和暗色值数成新配方
  3. 审计的令牌取值：跳过注释行，避免权威块的说明文字被当成值
  4. pre 视图补主行动按钮「生成当班清单」

用法：python patch_spec_final2.py [--dry-run]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
HEAD = BUILD / "index_head.html"
BODY = BUILD / "index_body.html"
AUDIT = BUILD / "audit_v16_spec.py"


def blank(text: str) -> str:
    return "\n\n".join(text.split("\n"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    # ---- 1) panel-head h2 ----
    head = HEAD.read_text(encoding="utf-8")
    count = 0
    out_lines = []
    for line in head.split("\n"):
        if ".panel-head h2" in line and "font-size:13px" in line:
            line = line.replace("font-size:13px", "font-size:15px")
            count += 1
        out_lines.append(line)
    head = "\n".join(out_lines)
    print(f"[ok] .panel-head h2 残留 13px 修正 {count} 处")

    # ---- 4) pre 主行动 ----
    body = BODY.read_text(encoding="utf-8")
    if 'id="preGenerate"' not in body:
        anchor = '<button id="checkReset" class="ghost-button" type="button">'
        addition = (
            '<button id="preGenerate" class="primary-button ico-button" type="button">'
            '<svg class="ico" aria-hidden="true"><use href="#i-clipboard"/></svg>生成当班清单</button>'
            + "\n\n          "
            + anchor
        )
        if anchor in body:
            body = body.replace(anchor, addition, 1)
            print("[ok] pre 视图已加主行动按钮 preGenerate")
        else:
            print("[FAIL] 未匹配 checkReset 锚点")
            return 1
    else:
        print("[跳过] preGenerate 已存在")

    # ---- 2) + 3) 审计脚本 ----
    audit = AUDIT.read_text(encoding="utf-8")

    old_shadow = '''    # 只比较三条主配方：--shadow-1/2/3。别名（--shadow/sm/lg）指向同值不算新配方。
    recipe = {}
    for key in ("--shadow-1", "--shadow-2", "--shadow-3"):
        found = re.findall(re.escape(key) + r":\\s*([^;]+);", css)
        if found:
            recipe[key] = found[-1].strip()
    distinct = set(recipe.values())'''
    new_shadow = '''    # 只比较两条主配方（--shadow-1 浅 / --shadow-2 深）的浅色值。
    # --shadow-3 与 --shadow/sm/lg 都是别名，指向这两条，不算新配方；
    # 暗色主题里的同名令牌是同一配方的深色版，也不该算第三条。
    light_css = css.split('[data-theme="dark"]')[0]

    def resolve(value: str) -> str:
        match = re.search(r"var\\((--[\\w-]+)\\)", value)
        if not match:
            return value.strip()
        found = re.findall(re.escape(match.group(1)) + r":\\s*([^;]+);", light_css)
        return found[-1].strip() if found else value.strip()

    distinct = set()
    for key in ("--shadow-1", "--shadow-2"):
        found = re.findall(re.escape(key) + r":\\s*([^;]+);", light_css)
        if found:
            distinct.add(resolve(found[-1]))'''
    if old_shadow in audit:
        audit = audit.replace(old_shadow, new_shadow, 1)
        print("[ok] 审计阴影判断已改为两条配方 + 解析别名")
    else:
        print("[跳过] 阴影判断已是新逻辑")

    # 令牌取值跳过注释
    old_canvas = 'canvas_vals = re.findall(r"--canvas:\\s*([^;]+);", css)'
    new_canvas = ('canvas_vals = [v for v in re.findall(r"--canvas:\\s*([^;]+);", css)\n'
                  '                   if "/" not in v and "*" not in v]')
    if old_canvas in audit:
        audit = audit.replace(old_canvas, new_canvas, 1)
        print("[ok] canvas 取值跳过注释行")

    old_line = 'line_vals = re.findall(r"--line:\\s*([^;]+);", css)'
    new_line = ('line_vals = [v for v in re.findall(r"--line:\\s*([^;]+);", css)\n'
                '                 if "/" not in v and "*" not in v]')
    if old_line in audit:
        audit = audit.replace(old_line, new_line, 1)
        print("[ok] line 取值跳过注释行")

    if any(chr(92) in t for t in (head, body)):
        print("[FAIL] 分片引入反斜杠")
        return 1

    if args.dry_run:
        print("（dry-run，未写入）")
        return 0

    HEAD.write_text(head, encoding="utf-8")
    BODY.write_text(body, encoding="utf-8")
    AUDIT.write_text(audit, encoding="utf-8")
    print("[ok] 已写入")
    return 0


if __name__ == "__main__":
    sys.exit(main())
