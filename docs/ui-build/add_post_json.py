"""补 postJson 辅助函数（第 16 轮 §11 前端）。

项目里只有 getJson，没有 POST 版本的 JSON 请求辅助。
新增的 /api/checklists/generate 需要 POST，所以加一个同风格的 postJson，
复用已有的 apiFetch（它带访问码重试逻辑，不能绕过）。

用法：python add_post_json.py [--dry-run]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
SCRIPT_A = BUILD / "index_script_a.js"

ANCHOR = '''    async function getJson(url) {
      var response = await apiFetch(url, { method: "GET" });
      if (!response.ok) throw new Error("HTTP " + response.status);
      return response.json();
    }'''

NEW = '''    async function getJson(url) {
      var response = await apiFetch(url, { method: "GET" });
      if (!response.ok) throw new Error("HTTP " + response.status);
      return response.json();
    }

    /* POST JSON。走 apiFetch 而不是裸 fetch —— 它带访问码重试逻辑。 */
    async function postJson(url, body) {
      var response = await apiFetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body || {}),
      });
      if (!response.ok) throw new Error("HTTP " + response.status);
      return response.json();
    }'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    text = SCRIPT_A.read_text(encoding="utf-8")
    if "function postJson" in text:
        print("[跳过] postJson 已存在")
        return 0
    if ANCHOR not in text:
        print("[FAIL] 找不到 getJson 锚点")
        return 1

    text = text.replace(ANCHOR, NEW, 1)
    if text.count(chr(92)):
        print("[FAIL] 引入反斜杠")
        return 1
    print("[ok] postJson 已加入，且无反斜杠")

    if args.dry_run:
        print("（dry-run，未写入）")
        return 0
    SCRIPT_A.write_text(text, encoding="utf-8")
    print("[ok] 已写入")
    return 0


if __name__ == "__main__":
    sys.exit(main())
