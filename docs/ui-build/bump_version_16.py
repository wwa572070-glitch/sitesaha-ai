"""§14 版本升级到 16.0.0（第 16 轮）。

需要同步的位置（都在仓库里，缺一个就会自相矛盾）：
  · webapp.py 的 APP_VERSION
  · docs/ui-build/index_head.html 的 <meta name="sitesaha-version">
  · docs/ui-build/index_body.html 的页脚与顶栏版本标记
  · RELEASE_MANIFEST.json 的 version
  · README.md 里出现的版本号
  · DELIVERY_VERIFY.ps1 的期望版本

用法：python bump_version_16.py [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
APP = BUILD.parent.parent

OLD = "15.0.0"
NEW = "16.0.0"

TARGETS = [
    (APP / "webapp.py", "APP_VERSION"),
    (APP / "docs" / "ui-build" / "index_head.html", "meta 版本标记"),
    (APP / "docs" / "ui-build" / "index_body.html", "页面版本标记"),
    (APP / "README.md", "README"),
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    total = 0

    # ---- 逐个文件替换 ----
    for path, note in TARGETS:
        if not path.is_file():
            print(f"  [跳过] {note}：文件不存在")
            continue
        text = path.read_text(encoding="utf-8")
        count = text.count(OLD)
        if not count:
            print(f"  [跳过] {note}：没有 {OLD}")
            continue
        text = text.replace(OLD, NEW)
        if not args.dry_run:
            path.write_text(text, encoding="utf-8")
        total += count
        print(f"  [ok] {note}：替换 {count} 处")

    # ---- RELEASE_MANIFEST.json（走 JSON，避免误改别的数字）----
    manifest_path = APP / "RELEASE_MANIFEST.json"
    if manifest_path.is_file():
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        if data.get("version") == OLD:
            data["version"] = NEW
            if not args.dry_run:
                manifest_path.write_text(
                    json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
            total += 1
            print("  [ok] RELEASE_MANIFEST.json：version → 16.0.0")

    # ---- DELIVERY_VERIFY.ps1 ----
    for name in ("DELIVERY_VERIFY.ps1", "VERIFY_ONLINE.ps1"):
        path = APP / name
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        count = text.count(OLD)
        if count:
            text = text.replace(OLD, NEW)
            if not args.dry_run:
                path.write_text(text, encoding="utf-8")
            total += count
            print(f"  [ok] {name}：替换 {count} 处")

    # ---- 复核 ----
    print()
    print("=== 复核 ===")
    for path, note in TARGETS + [(APP / "RELEASE_MANIFEST.json", "manifest")]:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        status = "旧版本残留" if OLD in text else "ok"
        found = NEW in text
        print(f"  [{status}] {note}  含 16.0.0: {found}")

    # APP_VERSION 单独确认
    webapp_text = (APP / "webapp.py").read_text(encoding="utf-8")
    match = re.search(r'APP_VERSION\s*=\s*["\']([^"\']+)', webapp_text)
    print(f"\nAPP_VERSION = {match.group(1) if match else '未找到'}")

    if args.dry_run:
        print(f"（dry-run，共 {total} 处）")
        return 0
    print(f"[ok] 已写入，共 {total} 处")
    return 0


if __name__ == "__main__":
    sys.exit(main())
