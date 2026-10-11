"""用无头 Edge dump DOM，读出 <html> 上的 data-theme，确认主题参数是否生效。

用法：python check_theme_attr.py [base]
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"


def dump(url: str, name: str, fresh_profile: bool = True) -> str:
    """每次用全新（或彻底清空）的 profile，避免上一轮写入的 localStorage 串味。"""
    profile = Path(tempfile.gettempdir()) / f"_attrprof_{name}"
    if profile.exists():
        shutil.rmtree(profile, ignore_errors=True)
    if not fresh_profile:
        profile.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [
            EDGE, "--headless=new", "--disable-gpu", "--no-sandbox",
            "--disable-extensions", f"--user-data-dir={profile}",
            "--virtual-time-budget=6000", "--dump-dom", url,
        ],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180,
    )
    return result.stdout or ""


def main() -> int:
    base = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8504/"
    print(f"{'入口':<26} {'<html ...>':<46} {'渲染主题'}")
    print("-" * 84)

    cases = [
        ("?theme=light", "?theme=light", "explicit-light"),
        ("?theme=dark", "?theme=dark", "explicit-dark"),
    ]
    results: dict[str, str] = {}
    tags: dict[str, str] = {}
    for label, suffix, slug in cases:
        dom = dump(base + suffix, slug)
        match = re.search(r"<html[^>]*>", dom)
        tag = match.group(0) if match else "(未找到 <html>)"
        has_dark = 'data-theme="dark"' in tag
        results[label] = "dark" if has_dark else "light"
        tags[label] = tag
        print(f"{label:<26} {tag[:44]:<46} {results[label]}")

    print()
    ok = results.get("?theme=light") == "light" and results.get("?theme=dark") == "dark"
    if ok:
        print("[OK] 主题参数生效：?theme=light → 亮色，?theme=dark → 暗色")
        print("     无参数时按 localStorage / 系统偏好决定（这是设计行为，不在此断言）")
        return 0
    print("[FAIL] 主题参数未按预期生效")
    for label, tag in tags.items():
        print(f"     {label}: {tag}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
