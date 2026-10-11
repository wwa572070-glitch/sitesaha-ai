"""审计：结构里每个可交互控件是否真的绑定了处理函数。

这是 DOM 仿真的补充——仿真验证"init() 不报错"，本脚本验证"控件点了有反应"。
两者结合才能排除"按钮渲染出来但点了没反应"这类死按钮。

用法（在 docs/ui-build 下）：python audit_bindings.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
BODY = BUILD / "index_body.html"
FULL = BUILD / "index_full.html"

# 需要"有反应"的控件：按钮、链接、select、以及带 id 的文件输入框
INTERACTIVE_TAGS = ("button", "a", "select")

# 允许没有点击处理的例外（附理由），避免误报
ALLOWED_UNBOUND = {
    "call120": "纯 tel: 链接，由 href 处理",
    "sosFab": "有 click 绑定走 SPA 切换，href 作为 JS 未加载时的兜底",
    "call119": "纯 tel: 链接，由 href 处理",
    "sitePhoto": "文件输入框，由 change 事件处理",
    "sitePhotoCamera": "文件输入框，由 change 事件处理",
    "question": "文本框，由 keydown 处理",
    "photoQuestion": "文本框，无事件属正常",
    "docSearch": "搜索框，由 input 事件处理",
    "standardsSearch": "搜索框，由 input 事件处理",
    "caseSearch": "搜索框，由 keydown 处理",
    "quizNext": "运行时动态创建，在 answerQuiz 里绑定",
}


def collect_controls(html: str) -> list[tuple[str, str]]:
    """返回 (id, 标签名) 列表；只收带 id 的元素。"""
    found: list[tuple[str, str]] = []
    for tag in INTERACTIVE_TAGS:
        for match in re.finditer(rf"<{tag}\b([^>]*)>", html):
            attrs = match.group(1)
            id_match = re.search(r'\bid="([^"]+)"', attrs)
            if id_match:
                found.append((id_match.group(1), tag))
    # 带 id 的文件输入框也纳入（它们靠 change 事件）
    for match in re.finditer(r"<input\b([^>]*)>", html):
        attrs = match.group(1)
        id_match = re.search(r'\bid="([^"]+)"', attrs)
        if id_match and 'type="file"' in attrs:
            found.append((id_match.group(1), "input[file]"))
    return found


def main() -> int:
    if not FULL.is_file():
        print(f"未找到 {FULL}，请先运行 assemble.py")
        return 1

    body = BODY.read_text(encoding="utf-8")
    full = FULL.read_text(encoding="utf-8")
    script_match = re.search(r"<script>(.*?)</script>", full, re.S)
    if not script_match:
        print("[FAIL] 未找到 script 块")
        return 1
    script = script_match.group(1)

    controls = collect_controls(body)
    if not controls:
        print("[FAIL] 未在结构里发现任何带 id 的控件")
        return 1

    unbound: list[tuple[str, str]] = []
    for control_id, tag in controls:
        # 绑定方式：bindClick("id", ...) / var x = $("id") 后 addEventListener
        if f'bindClick("{control_id}"' in script:
            continue
        if re.search(rf'\$\("{re.escape(control_id)}"\)', script) and "addEventListener" in script:
            continue
        if control_id in ALLOWED_UNBOUND:
            continue
        unbound.append((control_id, tag))

    print(f"带 id 的控件：{len(controls)} 个")
    print(f"已绑定：{len(controls) - len(unbound)} 个")
    print(f"未绑定：{len(unbound)} 个（已排除 {len(ALLOWED_UNBOUND)} 个有理由的例外）")

    if unbound:
        print("\n[FAIL] 以下控件在结构里存在但没有处理函数（点了没反应）：")
        for control_id, tag in unbound:
            print(f"   - <{tag} id=\"{control_id}\">")
        return 1

    # 反向检查（"脚本引用了不存在的 id"）由 check_page.py 负责，
    # 那里比对的是完整的 id 集合；此处不重复，避免与容器类 id 混淆。
    print("\n[OK] 控件绑定审计通过：无死按钮")
    return 0


if __name__ == "__main__":
    sys.exit(main())
