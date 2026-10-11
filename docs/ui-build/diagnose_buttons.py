"""逐个检查每个可点击控件的绑定与状态，找出"点不动"的原因。

对每个控件回答三个问题：
  1) 结构里存在吗？
  2) 脚本里绑定了处理函数吗？
  3) 初始是否 disabled 或 hidden（导致用户点了没反应）？

用法：python diagnose_buttons.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
BODY = BUILD / "index_body.html"
FULL = BUILD / "index_full.html"


def main() -> int:
    if not FULL.is_file():
        print("请先运行 assemble.py")
        return 1
    body = BODY.read_text(encoding="utf-8")
    full = FULL.read_text(encoding="utf-8")
    script = re.search(r"<script>(.*?)</script>", full, re.S).group(1)

    # 收集所有 button / a / input[file] / select
    controls: list[dict[str, str]] = []
    for tag in ("button", "a", "select"):
        for match in re.finditer(rf"<{tag}\b([^>]*)>", body):
            attrs = match.group(1)
            id_match = re.search(r'\bid="([^"]+)"', attrs)
            controls.append({
                "tag": tag,
                "id": id_match.group(1) if id_match else "",
                "attrs": attrs,
                "text": "",
            })

    print(f"带 id 的可交互控件：{sum(1 for c in controls if c['id'])} 个\n")
    print(f"{'控件 id':<24} {'标签':<8} {'绑定':<6} {'初始禁用':<9} {'初始隐藏'}")
    print("-" * 68)

    problems: list[str] = []
    for control in controls:
        cid = control["id"]
        if not cid:
            continue
        attrs = control["attrs"]

        bound = (
            f'bindClick("{cid}"' in script
            or (f'$("{cid}")' in script and "addEventListener" in script)
            or f"registerClick" in script
        )
        disabled = "disabled" in attrs
        hidden = "hidden" in attrs

        flag = ""
        if not bound:
            flag = "  ← 没绑定"
            problems.append(f"{cid}：没有绑定任何处理函数")
        elif disabled:
            flag = "  ← 初始禁用（需 JS 解除）"
        elif hidden:
            flag = "  ← 初始隐藏（需 JS 显示）"

        print(f"{cid:<24} {control['tag']:<8} "
              f"{'有' if bound else '无':<6} "
              f"{'是' if disabled else '否':<9} "
              f"{'是' if hidden else '否'}{flag}")

    print()
    if problems:
        print(f"[FAIL] {len(problems)} 个控件点不动：")
        for item in problems:
            print("  -", item)
        return 1
    print("[OK] 所有控件都有处理函数")

    # 额外：检查被 JS 解除禁用/隐藏的控件，其解除代码是否存在
    # 用正则而非字符串拼接，覆盖 变量.disabled / $(id).disabled / setAttribute / style.display 等写法
    print("\n--- 初始禁用/隐藏的控件，解除代码是否存在 ---")
    unresolved: list[str] = []
    for control in controls:
        cid = control["id"]
        if not cid:
            continue
        attrs = control["attrs"]
        if "disabled" not in attrs and "hidden" not in attrs:
            continue
        escaped = re.escape(cid)
        patterns = [
            rf'\$\("{escaped}"\)\.disabled\s*=\s*false',
            rf'\$\("{escaped}"\)\.hidden\s*=\s*false',
            rf'\$\("{escaped}"\)\.removeAttribute\("hidden"\)',
            rf'\$\("{escaped}"\)\.style\.display',
            rf'bindClick\("{escaped}"',
        ]
        # 变量式写法：var x = $("id"); x.disabled = false
        var_match = re.search(rf'var\s+(\w+)\s*=\s*\$\("{escaped}"\)', script)
        if var_match:
            var = var_match.group(1)
            patterns.append(rf'{re.escape(var)}\.disabled\s*=\s*false')
            patterns.append(rf'{re.escape(var)}\.hidden\s*=\s*false')
            patterns.append(rf'{re.escape(var)}\.removeAttribute\("hidden"\)')

        found = any(re.search(p, script) for p in patterns)
        mark = "有" if found else "没有 ← 需要人工确认"
        print(f"  {cid:<24} 解除代码：{mark}")
        if not found:
            unresolved.append(cid)

    if unresolved:
        print(f"\n[注意] {len(unresolved)} 个控件的解除代码没匹配到，可能是写法特殊或真的缺失：")
        for cid in unresolved:
            print("  -", cid)
        print("建议：在浏览器里点一次确认；点在需要的条件下才会显示（例如先打开摄像头）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
