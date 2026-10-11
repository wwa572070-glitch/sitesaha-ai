"""修补 webapp.py：自检 probe 参数 + 大图上传拦截（第 16 轮 §4）。

1) _handle_selftest 支持 GET ?probe=1，与 POST body {"probe": true} 两种触发方式。
2) 图片上传：在读体之前就判断大小，避免读入 9MB 后才拒绝；
   返回结构化错误码 image_too_large + 可操作提示。

用法：python patch_media_guards.py [--dry-run]
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

APP = Path(__file__).resolve().parent.parent.parent
WEBAPP = APP / "webapp.py"

OLD_PROBE = '''        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
            body = self.rfile.read(length) if length > 0 else b"{}"
            payload = _json.loads(body.decode("utf-8") or "{}")
            if not isinstance(payload, dict):
                payload = {}
        except (ValueError, _json.JSONDecodeError):
            payload = {}

        want_probe = bool(payload.get("probe"))'''

NEW_PROBE = '''        payload: dict = {}
        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
            if length > 0:
                body = self.rfile.read(length)
                parsed = _json.loads(body.decode("utf-8") or "{}")
                if isinstance(parsed, dict):
                    payload = parsed
        except (ValueError, _json.JSONDecodeError):
            payload = {}

        # 两种触发方式：POST body {"probe": true}，或 GET 的 ?probe=1
        query = urllib.parse.urlparse(self.path).query
        want_probe = bool(payload.get("probe")) or ("probe=1" in (query or ""))'''

OLD_GUARD = '''                if length <= 0 or length > self.services.config.max_image_bytes + 200_000:'''

NEW_GUARD = '''                if length <= 0:

                    self._write_json({"error": "图片为空"}, HTTPStatus.BAD_REQUEST)

                    return

                if length > self.services.config.max_image_bytes + 200_000:

                    limit_mb = self.services.config.max_image_bytes // (1024 * 1024)

                    self._write_json(

                        {

                            "error": f"图片不能超过 {limit_mb} MB",

                            "error_code": "image_too_large",

                            "hint": "请压缩后重试；手机拍照时可先用相册的裁剪功能改小再上传。",

                        },

                        HTTPStatus.REQUEST_ENTITY_TOO_LARGE,

                    )

                    return'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    text = WEBAPP.read_text(encoding="utf-8")
    changed = 0

    if "probe=1" not in text:
        if OLD_PROBE not in text:
            print("[FAIL] 找不到 probe 解析锚点")
            return 1
        text = text.replace(OLD_PROBE, NEW_PROBE, 1)
        changed += 1
        print("[ok] 自检支持 ?probe=1")
    else:
        print("[跳过] probe 参数已支持")

    if "image_too_large" not in text:
        if OLD_GUARD not in text:
            print("[FAIL] 找不到图片大小判断锚点")
            return 1
        text = text.replace(OLD_GUARD, NEW_GUARD, 1)
        changed += 1
        print("[ok] 大图在读体前拦截")
    else:
        print("[跳过] 大图拦截已存在")

    try:
        ast.parse(text)
    except SyntaxError as exc:
        print(f"[FAIL] 语法错误：{exc}")
        return 1
    print("[ok] 语法检查通过")

    if args.dry_run:
        print(f"（dry-run，未写入；{changed} 处）")
        return 0
    WEBAPP.write_text(text, encoding="utf-8")
    print(f"[ok] webapp.py 已更新（{changed} 处）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
