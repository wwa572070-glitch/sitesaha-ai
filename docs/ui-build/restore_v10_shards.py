"""从 git 历史恢复 V10 的四个界面分片（丰富版），替代被砍成极简的 V11。

用法：python restore_v10_shards.py [rev]
默认 rev = 2aacc7d^（V10 最后一次提交）
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

GIT = r"C:\Program Files\Git\cmd\git.exe"
BUILD = Path(__file__).resolve().parent
REPO = BUILD.parent.parent
REV = sys.argv[1] if len(sys.argv) > 1 else "2aacc7d^"

TARGETS = [
    "docs/ui-build/index_head.html",
    "docs/ui-build/index_body.html",
    "docs/ui-build/index_script_a.js",
    "docs/ui-build/index_script_b.js",
]


def main() -> int:
    failures: list[str] = []
    for rel in TARGETS:
        result = subprocess.run(
            [GIT, "show", f"{REV}:{rel}"],
            cwd=str(REPO),
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            failures.append(f"{rel}: git show 失败 {result.stderr.decode('utf-8', 'replace')[:120]}")
            continue
        raw = result.stdout
        if b"\x00" in raw:
            failures.append(f"{rel}: 含空字节，编码不对")
            continue
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            failures.append(f"{rel}: UTF-8 解码失败 {exc}")
            continue

        target = REPO / rel
        old_size = target.stat().st_size if target.is_file() else 0
        target.write_text(text, encoding="utf-8")
        print(f"[ok] {rel}")
        print(f"     {old_size} → {len(raw)} 字节")

    if failures:
        print("\n失败项：")
        for item in failures:
            print("  -", item)
        return 1
    print(f"\n[OK] 已从 {REV} 恢复 {len(TARGETS)} 个分片")
    return 0


if __name__ == "__main__":
    sys.exit(main())
