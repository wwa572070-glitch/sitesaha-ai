"""重写 /api/checklists/import，正确解析 multipart（第 16 轮 §11）。

问题：我最初写这条路由时直接拿 body 当文件内容，没走 multipart 解析，
      而且 filename 在 body 里、不在 Content-Type 头里 —— 于是 500。

项目里已有 _parse_multipart / _find_part 辅助函数（inspect-image 在用），
这里改成复用它们。

用法：python fix_import_route.py [--dry-run]
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
APP = BUILD.parent.parent
WEBAPP = APP / "webapp.py"

# 原始（有问题的）片段
OLD = '''                raw = self._read_body(length)

                filename = ""

                match = re.search(r'filename="([^"]*)"', content_type) or None

                if match:

                    filename = match.group(1)

                is_xlsx = filename.lower().endswith(".xlsx") or raw[:2] == b"PK"'''

NEW = '''                raw = self._read_body(length)

                # 复用项目里的 multipart 解析（inspect-image 用的同一套），
                # 不能直接拿 body 当文件内容 —— filename 也在 body 里，不在头上。
                filename = ""

                payload = raw

                if "multipart/form-data" in content_type:

                    try:

                        parts = self._parse_multipart(content_type, raw)

                        part = self._find_part(parts, ("file", "upload", "data"))

                        if part is not None:

                            filename = str(self._part_param(part, "filename") or "")

                            payload = part.get_payload(decode=True) or b""

                    except Exception:  # noqa: BLE001

                        self._write_json(

                            {

                                "error": "文件内容解析失败，可能上传不完整。",

                                "error_code": "multipart_unreadable",

                                "hint": "重新选一次文件；如果仍然失败，改成 CSV 再试。",

                            },

                            HTTPStatus.BAD_REQUEST,

                        )

                        return

                is_xlsx = filename.lower().endswith(".xlsx") or payload[:2] == b"PK"'''

OLD2 = '''                try:

                    text = xlsx_to_text(raw) if is_xlsx else raw.decode("utf-8", "replace")'''

NEW2 = '''                try:

                    text = xlsx_to_text(payload) if is_xlsx else payload.decode("utf-8", "replace")'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    text = WEBAPP.read_text(encoding="utf-8")
    changed = 0

    if OLD in text:
        text = text.replace(OLD, NEW, 1)
        changed += 1
        print("[ok] import 路由改用 _parse_multipart")
    else:
        print("[跳过] 主片段锚点未匹配")

    if OLD2 in text:
        text = text.replace(OLD2, NEW2, 1)
        changed += 1
        print("[ok] xlsx 判断改用解析后的 payload")
    else:
        print("[跳过] xlsx 片段锚点未匹配")

    # 确认辅助函数的签名能这么用
    import re as _re
    sig = _re.search(r"def _find_part\([^)]*\)", text, _re.S)
    print(f"[信息] {sig.group(0) if sig else '_find_part 未找到'}")

    try:
        ast.parse(text)
    except SyntaxError as exc:
        print(f"[FAIL] 语法错误：{exc}")
        return 1
    print("[ok] 语法通过")

    if args.dry_run:
        print(f"（dry-run，未写入；{changed} 处）")
        return 0
    WEBAPP.write_text(text, encoding="utf-8")
    print(f"[ok] 已写入（{changed} 处）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
