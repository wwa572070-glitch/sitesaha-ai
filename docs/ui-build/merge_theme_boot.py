"""把主题上色逻辑并进 index_script_a.js 的最前面（"use strict" 之后）。

为什么不用单独 <script> 块：check_js.py 只读取第一个 script 块，
多一个块会让关键实现标记全部检查不到，等于门禁失效。
另一个办法是在 head 里用 <style> 代替，但主题需要读 localStorage，
必须用脚本。所以放在同一个块的最前面最稳妥——
"use strict" 之后、任何 DOM 依赖之前执行，README 里的首屏闪白问题依然解决。

用法：python merge_theme_boot.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
SCRIPT_A = BUILD / "index_script_a.js"
BOOT = BUILD / "theme_boot.js"

BEGIN = "    /* ===== THEME BOOT BEGIN ===== */"
END = "    /* ===== THEME BOOT END ===== */"


def indent(source: str, spaces: int = 4) -> str:
    pad = " " * spaces
    return "\n".join((pad + line) if line.strip() else "" for line in source.split("\n"))


def main() -> int:
    if not SCRIPT_A.is_file() or not BOOT.is_file():
        print("[FAIL] 缺少 index_script_a.js 或 theme_boot.js")
        return 1

    script = SCRIPT_A.read_text(encoding="utf-8")
    boot = BOOT.read_text(encoding="utf-8").strip()
    block = f"{BEGIN}\n{indent(boot)}\n{END}\n"

    if BEGIN in script:
        pattern = re.compile(re.escape(BEGIN) + r".*?" + re.escape(END) + r"\n", re.S)
        script_new, n = pattern.subn(block, script)
        if n != 1:
            print(f"[FAIL] 替换主题块失败（命中 {n} 次）")
            return 1
        print("[ok] 已更新主题上色块")
    else:
        anchor = '    "use strict";\n'
        if script.count(anchor) != 1:
            print(f'[FAIL] "use strict"; 命中 {script.count(anchor)} 次，应为 1')
            return 1
        script_new = script.replace(anchor, anchor + "\n" + block, 1)
        print("[ok] 已在脚本最前面插入主题上色块")

    SCRIPT_A.write_text(script_new, encoding="utf-8")
    print(f"index_script_a.js：{len(script)} → {len(script_new)} 字符")

    # 重名检查：boot 里的 __sitesahaTheme 只能出现一次定义
    if script_new.count("window.__sitesahaTheme =") != 1:
        print("[FAIL] __sitesahaTheme 定义次数异常")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
