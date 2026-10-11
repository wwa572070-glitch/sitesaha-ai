"""接线 §11 的接口（第 16 轮）。

新增两个只读接口（不改动现有 /api/checklists 的返回结构，保持向后兼容）：
  GET  /api/checklists/conditions  → 可选条件清单（供前端渲染条件选择器）
  POST /api/checklists/generate    → 按当班条件生成检查清单

导入走前端 FileReader（csv/txt/md）+ 这个接口（xlsx），
所以再加：
  POST /api/checklists/import      → 上传 xlsx 或文本，返回解析结果（含逐行错误）

导入结果**不落库** —— 由前端存 localStorage。
理由：这是"项目自有文件"，属于本机资料；不落库也避免多用户互相污染。

用法：python patch_checklist_api.py [--dry-run]
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
APP = BUILD.parent.parent
WEBAPP = APP / "webapp.py"

IMPORT_OLD = "from sitesaha.structure import parse_inspection, strip_markdown"
IMPORT_NEW = ("from sitesaha.structure import parse_inspection, strip_markdown\n"
              "from sitesaha import checklists as checklists_mod\n"
              "from sitesaha.xlsx import XlsxError, to_text as xlsx_to_text")

# 插在 /api/checklists 分支之后
ANCHOR = '            if path == "/api/inspect-image":'

ROUTES = '''            if path == "/api/checklists/conditions":

                self._write_json(

                    {

                        "weather": checklists_mod.WEATHER_CONDITIONS,

                        "work": checklists_mod.WORK_CONDITIONS,

                    }

                )

                return

            if path == "/api/checklists/generate":

                payload = self._read_json()

                conditions = payload.get("conditions") or []

                if not isinstance(conditions, list):

                    self._write_json(

                        {

                            "error": "conditions 需要是数组。",

                            "error_code": "bad_request",

                            "hint": "例如 {\\"conditions\\": [\\"hotwork\\", \\"heat\\"]}",

                        },

                        HTTPStatus.BAD_REQUEST,

                    )

                    return

                self._write_json(checklists_mod.generate(conditions))

                return

            if path == "/api/checklists/import":

                content_type = self.headers.get("Content-Type", "")

                length = int(self.headers.get("Content-Length", "0"))

                if length <= 0:

                    self._write_json(

                        {"error": "没有收到文件内容。", "error_code": "empty_body"},

                        HTTPStatus.BAD_REQUEST,

                    )

                    return

                if length > 4 * 1024 * 1024:

                    self._write_json(

                        {

                            "error": "文件不能超过 4 MB。",

                            "error_code": "file_too_large",

                            "hint": "检查项清单通常很小；如果文件很大，先只保留需要的那部分。",

                        },

                        HTTPStatus.REQUEST_ENTITY_TOO_LARGE,

                    )

                    return

                raw = self._read_body(length)

                filename = ""

                match = re.search(r'filename="([^"]*)"', content_type) or None

                if match:

                    filename = match.group(1)

                is_xlsx = filename.lower().endswith(".xlsx") or raw[:2] == b"PK"

                try:

                    text = xlsx_to_text(raw) if is_xlsx else raw.decode("utf-8", "replace")

                except XlsxError as exc:

                    self._write_json(

                        {

                            "error": str(exc),

                            "error_code": "xlsx_unreadable",

                            "hint": "可以另存为 CSV 再导入，或者检查文件是否损坏。",

                        },

                        HTTPStatus.BAD_REQUEST,

                    )

                    return

                rows = checklists_mod.parse_delimited(text)

                result = checklists_mod.normalize_import(rows)

                result["filename"] = filename

                result["parsed"] = len(rows)

                self._write_json(result)

                return

'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    text = WEBAPP.read_text(encoding="utf-8")
    applied = 0

    if "checklists_mod" not in text:
        if IMPORT_OLD not in text:
            print("[FAIL] 找不到 structure 导入锚点")
            return 1
        text = text.replace(IMPORT_OLD, IMPORT_NEW, 1)
        applied += 1
        print("[ok] 导入 checklists_mod 与 xlsx_to_text")
    else:
        print("[跳过] 导入已存在")

    if "/api/checklists/conditions" not in text:
        if ANCHOR not in text:
            print("[FAIL] 找不到 inspect-image 锚点")
            return 1
        text = text.replace(ANCHOR, ROUTES + ANCHOR, 1)
        applied += 1
        print("[ok] 新增三个清单接口")
    else:
        print("[跳过] 接口已存在")

    # re 与 HTTPStatus 是否已导入
    if "import re" not in text.split("class SiteSahaHandler")[0]:
        print("[警告] 顶部可能没有 import re")
    if "HTTPStatus" not in text:
        print("[FAIL] 没有 HTTPStatus")

    try:
        ast.parse(text)
    except SyntaxError as exc:
        print(f"[FAIL] 语法错误：{exc}")
        return 1
    print("[ok] 语法通过")

    if args.dry_run:
        print(f"（dry-run，未写入；{applied} 处）")
        return 0
    WEBAPP.write_text(text, encoding="utf-8")
    print(f"[ok] 已写入（{applied} 处）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
