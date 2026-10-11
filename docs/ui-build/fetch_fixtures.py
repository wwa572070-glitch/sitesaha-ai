"""从本地运行中的服务抓取接口响应，作为 DOM 仿真的数据夹具。

用法：python fetch_fixtures.py [base_url]
"""

from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

BUILD = Path(__file__).resolve().parent
BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8503"

ENDPOINTS = {
    "training": "/api/training",
    "status": "/api/status",
    "cases": "/api/cases",
    "checklists": "/api/checklists",
    "standards": "/api/standards",
}


def main() -> int:
    for name, path in ENDPOINTS.items():
        try:
            with urllib.request.urlopen(BASE + path, timeout=20) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            print(f"[FAIL] {path}: {exc}")
            return 1
        target = BUILD / f"fixture_{name}.json"
        target.write_text(
            json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        size = target.stat().st_size
        summary = ""
        if isinstance(payload, dict):
            summary = ", ".join(
                f"{key}={len(value) if isinstance(value, (list, dict, str)) else value}"
                for key, value in list(payload.items())[:6]
            )
        print(f"[ok] {path} -> {target.name} ({size} bytes) {summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
