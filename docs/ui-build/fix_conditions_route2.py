"""把 /api/checklists/conditions 加到 do_GET（缩进按 do_GET 实际层级）。

上一版用了 12 空格缩进（do_POST 的层级），所以在 do_GET 里找不到锚点、
匹配也失败。do_GET 的路由是 8 空格缩进。

用法：python fix_conditions_route2.py [--dry-run]
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
APP = BUILD.parent.parent
WEBAPP = APP / "webapp.py"

GET_BLOCK = '''        if path == "/api/checklists/conditions":

            self._write_json(

                {

                    "weather": checklists_mod.WEATHER_CONDITIONS,

                    "work": checklists_mod.WORK_CONDITIONS,

                }

            )

            return

'''

# do_POST 里的重复（12 空格缩进）
POST_BLOCK = '''            if path == "/api/checklists/conditions":

                self._write_json(

                    {

                        "weather": checklists_mod.WEATHER_CONDITIONS,

                        "work": checklists_mod.WORK_CONDITIONS,

                    }

                )

                return

'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    text = WEBAPP.read_text(encoding="utf-8")

    get_start = text.find("def do_GET")
    post_start = text.find("def do_POST")
    if get_start < 0 or post_start < 0:
        print("[FAIL] 找不到 do_GET / do_POST")
        return 1

    if '"/api/checklists/conditions"' in text[get_start:post_start]:
        print("[跳过] do_GET 里已有该路由")
    else:
        anchor = '        if path == "/api/training":'
        index = text.find(anchor, get_start, post_start)
        if index < 0:
            print("[FAIL] 找不到 /api/training 锚点")
            return 1
        text = text[:index] + GET_BLOCK + "\n" + text[index:]
        print("[ok] 已按 8 空格缩进加入 do_GET")

    if POST_BLOCK in text[post_start:]:
        text = text.replace(POST_BLOCK, "", 1)
        print("[ok] 已移除 do_POST 里的重复路由")
    else:
        print("[跳过] do_POST 里没有重复")

    try:
        ast.parse(text)
    except SyntaxError as exc:
        print(f"[FAIL] 语法错误：{exc}")
        return 1
    print("[ok] 语法通过")

    if args.dry_run:
        print("（dry-run，未写入）")
        return 0
    WEBAPP.write_text(text, encoding="utf-8")
    print("[ok] 已写入")
    return 0


if __name__ == "__main__":
    sys.exit(main())
