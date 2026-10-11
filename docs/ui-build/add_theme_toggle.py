"""给顶栏加主题切换按钮，并接入 v12_dark.css 暗色主题。

做三件事：
  1) index_body.html：在版本号前插入 #themeToggle 按钮
  2) index_script_b.js：加 initTheme()，读取 localStorage 并绑定切换
  3) apply_v12_theme.py 会把 v12_dark.css 一起注入 index_head.html

用法：python add_theme_toggle.py
"""

from __future__ import annotations

import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
BODY = BUILD / "index_body.html"
SCRIPT_B = BUILD / "index_script_b.js"

BUTTON = '''        <button id="themeToggle" class="theme-toggle" type="button"
                aria-pressed="false" title="切换白天 / 夜间配色">🌙 夜间</button>

'''

ANCHOR = '        <div class="version-tag">'

THEME_JS = '''
    /* ==================================================================
       主题切换：默认白天（方案 C：纯白 + 单一蓝），可切夜间（方案 B：深蓝黑 + 明黄）
       选择存在 localStorage，刷新后保持；系统偏好只作首次默认值。
       ================================================================== */
    var THEME_KEY = "sitesaha-theme-v1";

    function currentTheme() {
      var saved = "";
      try { saved = window.localStorage.getItem(THEME_KEY) || ""; } catch (e) { saved = ""; }
      if (saved === "dark" || saved === "light") return saved;
      try {
        if (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches) {
          return "dark";
        }
      } catch (e) { /* 忽略：不支持 matchMedia 时按白天处理 */ }
      return "light";
    }

    function applyTheme(theme) {
      var root = document.documentElement;
      if (theme === "dark") {
        root.setAttribute("data-theme", "dark");
      } else {
        root.removeAttribute("data-theme");
      }
      var meta = document.querySelector('meta[name="theme-color"]');
      if (meta) meta.setAttribute("content", theme === "dark" ? "#0e1c28" : "#17385c");
      var button = $("themeToggle");
      if (button) {
        button.textContent = theme === "dark" ? "☀️ 白天" : "🌙 夜间";
        button.setAttribute("aria-pressed", theme === "dark" ? "true" : "false");
      }
    }

    function initTheme() {
      applyTheme(currentTheme());
      bindClick("themeToggle", function () {
        var next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
        applyTheme(next);
        try { window.localStorage.setItem(THEME_KEY, next); } catch (e) { /* 隐私模式下忽略 */ }
      });
    }
'''


def main() -> int:
    # 1) 按钮
    body = BODY.read_text(encoding="utf-8")
    if 'id="themeToggle"' not in body:
        if body.count(ANCHOR) != 1:
            print(f"[FAIL] 版本号锚点命中 {body.count(ANCHOR)} 次，应为 1")
            return 1
        body = body.replace(ANCHOR, BUTTON + ANCHOR)
        BODY.write_text(body, encoding="utf-8")
        print("[ok] 已在顶栏插入主题切换按钮")
    else:
        print("[跳过] 按钮已存在")

    # 2) 脚本
    js = SCRIPT_B.read_text(encoding="utf-8")
    if "function initTheme()" in js:
        print("[跳过] initTheme 已存在")
    else:
        # 插到文件末尾前的 IIFE 收尾之前，确保函数在作用域内
        marker = "\n  })();"
        if marker not in js:
            # 退回：在最后一个 })(); 前插入
            idx = js.rfind("})();")
            if idx < 0:
                print("[FAIL] 找不到 IIFE 收尾，无法插入 initTheme")
                return 1
            js = js[:idx] + THEME_JS + "\n" + js[idx:]
        else:
            js = js.replace(marker, THEME_JS + marker, 1)
        SCRIPT_B.write_text(js, encoding="utf-8")
        print("[ok] 已插入 initTheme / applyTheme")

    # 3) 确认初始化调用链里会调用 initTheme
    if "initTheme();" not in js:
        # 找到 boot/init 调用区，追加调用
        for cand in ("      initVoiceControls();", "      bindEvents();", "      boot();"):
            if cand in js:
                js = js.replace(cand, cand + "\n      initTheme();", 1)
                SCRIPT_B.write_text(js, encoding="utf-8")
                print(f"[ok] 已在 {cand.strip()} 之后调用 initTheme()")
                break
        else:
            print("[注意] 未找到初始化调用点，请手工在启动流程里加 initTheme();")
    return 0


if __name__ == "__main__":
    sys.exit(main())
