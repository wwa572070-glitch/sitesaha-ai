"""隔离测试主题判定逻辑：从 index_script_a.js 抽出 boot 块，在 Node 里跑各种输入。

用法：python test_theme_logic.py
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

BUILD = Path(__file__).resolve().parent
SCRIPT_A = BUILD / "index_script_a.js"
NODE = r"C:\Users\sht18\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\node\bin\node.exe"

BEGIN = "/* ===== THEME BOOT BEGIN ===== */"
END = "/* ===== THEME BOOT END ===== */"

HARNESS = """
// 假的最小 window/document，只够 boot 块跑起来
function makeEl() {
  const attrs = {};
  return {
    _attrs: attrs,
    textContent: "",
    setAttribute(n, v) { attrs[n] = String(v); },
    getAttribute(n) { return n in attrs ? attrs[n] : null; },
    removeAttribute(n) { delete attrs[n]; },
  };
}
const root = makeEl();
const button = makeEl();
const meta = makeEl();

global.window = {
  location: { search: process.env.QS || "" },
  localStorage: {
    _d: JSON.parse(process.env.LS || "{}"),
    getItem(k) { return k in this._d ? this._d[k] : null; },
    setItem(k, v) { this._d[k] = String(v); },
  },
  matchMedia(q) { return { matches: process.env.SYS === "dark", media: q }; },
};
global.document = {
  documentElement: root,
  getElementById(id) { return id === "themeToggle" ? button : null; },
  querySelector(sel) { return sel.indexOf("theme-color") >= 0 ? meta : null; },
  addEventListener() {},
};
global.localStorage = global.window.localStorage;

__BOOT__

console.log(JSON.stringify({
  theme: root.getAttribute("data-theme"),
  button: button.textContent,
  meta: meta.getAttribute("content"),
}));
"""

CASES = [
    {"label": "?theme=light（系统偏好 dark）", "qs": "?theme=light", "ls": {}, "sys": "dark"},
    {"label": "?theme=dark（系统偏好 light）", "qs": "?theme=dark", "ls": {}, "sys": "light"},
    {"label": "无参数 + 系统偏好 dark", "qs": "", "ls": {}, "sys": "dark"},
    {"label": "无参数 + 系统偏好 light", "qs": "", "ls": {}, "sys": "light"},
    {"label": "无参数 + 存了 light（系统 dark）", "qs": "", "ls": {"sitesaha-theme-v1": "light"}, "sys": "dark"},
    {"label": "无参数 + 存了 dark（系统 light）", "qs": "", "ls": {"sitesaha-theme-v1": "dark"}, "sys": "light"},
    {"label": "?theme=light 覆盖已存的 dark", "qs": "?theme=light", "ls": {"sitesaha-theme-v1": "dark"}, "sys": "dark"},
    {"label": "?foo=1&theme=dark 位置在后", "qs": "?foo=1&theme=dark", "ls": {}, "sys": "light"},
]


def main() -> int:
    script = SCRIPT_A.read_text(encoding="utf-8")
    start = script.find(BEGIN)
    end = script.find(END)
    if start < 0 or end < 0:
        print("[FAIL] index_script_a.js 里找不到 THEME BOOT 块")
        return 1
    boot = script[start + len(BEGIN):end]
    # 去掉 JS 注释里的中文说明不影响执行；保留原样即可
    harness = HARNESS.replace("__BOOT__", boot)

    path = Path(tempfile.gettempdir()) / "_theme_harness.js"
    path.write_text(harness, encoding="utf-8")

    print(f"{'场景':<34} {'data-theme':<12} {'按钮文案':<10} 判定")
    print("-" * 74)
    failures = 0
    # 亮色主题的表示方式是"没有 data-theme 属性"（removeAttribute），
    # 不是 data-theme="light"。断言必须按这个来，否则会误报失败。
    expectations = {
        "?theme=light（系统偏好 dark）": None,
        "?theme=dark（系统偏好 light）": "dark",
        "无参数 + 系统偏好 dark": "dark",
        "无参数 + 系统偏好 light": None,
        "无参数 + 存了 light（系统 dark）": None,
        "无参数 + 存了 dark（系统 light）": "dark",
        "?theme=light 覆盖已存的 dark": None,
        "?foo=1&theme=dark 位置在后": "dark",
    }
    for case in CASES:
        result = subprocess.run(
            [NODE, str(path)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            env={
                "QS": case["qs"],
                "LS": json.dumps(case["ls"]),
                "SYS": case["sys"],
                "PATH": "",
                "SystemRoot": r"C:\Windows",
            },
            timeout=60,
        )
        line = (result.stdout or "").strip().split("\n")[-1]
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            print(f"{case['label']:<34} 解析失败：{(result.stderr or '')[:60]}")
            failures += 1
            continue
        actual = data["theme"]
        want = expectations.get(case["label"], "未定义")
        if actual == want:
            mark = "OK"
        else:
            mark = f"期望 {want!r}"
            failures += 1
        shown = "(无属性=亮色)" if actual is None else actual
        print(f"{case['label']:<34} {shown:<12} {data['button']:<10} {mark}")

    print()
    if failures:
        print(f"[FAIL] {failures} 个场景不符合预期")
        return 1
    print("[OK] 主题判定逻辑全部符合预期")
    return 0


if __name__ == "__main__":
    sys.exit(main())
