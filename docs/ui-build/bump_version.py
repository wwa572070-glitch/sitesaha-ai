"""把版本号统一提升到 10.0.0，并修正线上验证脚本的失效断言。

用法（在项目根运行）：python docs/ui-build/bump_version.py
只做精确替换，每处都必须命中，否则整体放弃写入。
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
APP = BUILD.parent.parent          # 项目根 sitesaha_v3
DELIVERY = APP.parent              # 交付根

OLD = "9.1.0"
NEW = "10.0.0"

# (相对项目根的路径, 原文, 新文, 说明)
EDITS: list[tuple[str, str, str, str]] = [
    ("webapp.py", f'APP_VERSION = "{OLD}"', f'APP_VERSION = "{NEW}"', "应用版本常量"),
    ("webapp.py", f'<div class="version-tag">V{OLD}</div>',
     f'<div class="version-tag">V{NEW}</div>', "顶栏版本标记"),
    ("webapp.py", f"<div><dt>版本</dt><dd>V{OLD}</dd></div>",
     f"<div><dt>版本</dt><dd>V{NEW}</dd></div>", "侧栏版本行"),
    ("webapp.py", f"<span>筑安智培 · 新工人安全培训问答智能体 · V{OLD}</span>",
     f"<span>筑安智培 · 新工人安全培训问答智能体 · V{NEW}</span>", "页脚版本"),
    ("webapp.py", f'["学习平台", "筑安智培（SiteSaha AI）V{OLD}"]',
     f'["学习平台", "筑安智培（SiteSaha AI）V{NEW}"]', "培训记录单版本"),
    ("sitesaha/__init__.py", f'__version__ = "{OLD}"', f'__version__ = "{NEW}"', "包版本"),
    ("pyproject.toml", f'version = "{OLD}"', f'version = "{NEW}"', "pyproject 版本"),
    ("docs/ui-build/index_body.html", f'<div class="version-tag">V{OLD}</div>',
     f'<div class="version-tag">V{NEW}</div>', "分片：顶栏版本"),
    ("docs/ui-build/index_body.html", f"<div><dt>版本</dt><dd>V{OLD}</dd></div>",
     f"<div><dt>版本</dt><dd>V{NEW}</dd></div>", "分片：侧栏版本行"),
    ("docs/ui-build/index_body.html", f"<span>筑安智培 · 新工人安全培训问答智能体 · V{OLD}</span>",
     f"<span>筑安智培 · 新工人安全培训问答智能体 · V{NEW}</span>", "分片：页脚版本"),
    ("docs/ui-build/index_head.html",
     '<meta name="theme-color" content="#0c2b4a">',
     f'<meta name="theme-color" content="#0c2b4a">\n  <meta name="sitesaha-version" content="{NEW}">',
     "分片：可机读版本标记"),
    ("docs/ui-build/index_script_b.js",
     '["学习平台", "筑安智培（SiteSaha AI）V9.1.0"]',
     f'["学习平台", "筑安智培（SiteSaha AI）V{NEW}"]',
     "分片：培训记录单版本"),
]

# 线上验证脚本：旧断言 "按住说话" 在 V10 首页已不存在，必须换成仍在的文案
VERIFY_EDITS: list[tuple[str, str, str, str]] = [
    ("VERIFY_ONLINE.ps1", f'[string]$ExpectedVersion = "{OLD}"',
     f'[string]$ExpectedVersion = "{NEW}"', "默认期望版本"),
    ("VERIFY_ONLINE.ps1", '$homePage.Content -match "按住说话"',
     '$homePage.Content -match "录音提问"', "语音入口断言（旧文案已不存在）"),
    ("VERIFY_ONLINE.ps1", '$homePage.Content -match "紧急求助"',
     '$homePage.Content -match "应急求助"', "应急入口断言"),
    ("VERIFY_ONLINE.ps1", '$homePage.Content -match "真实案例"',
     '$homePage.Content -match "真实案例"', "案例模块断言（保持）"),
    ("PUSH_AND_DEPLOY.ps1", f'if ($health.version -eq "{OLD}") {{',
     f'if ($health.version -eq "{NEW}") {{', "部署完成判定"),
    ("PUSH_AND_DEPLOY.ps1", f'throw "等待 $DeploymentTimeoutSeconds 秒后，线上仍未返回 {OLD}。请检查 Render 部署日志。"',
     f'throw "等待 $DeploymentTimeoutSeconds 秒后，线上仍未返回 {NEW}。请检查 Render 部署日志。"',
     "超时报错文案"),
]


def apply(path: Path, edits: list[tuple[str, str, str, str]], problems: list[str]) -> int:
    if not path.is_file():
        problems.append(f"文件不存在：{path}")
        return 0
    text = path.read_text(encoding="utf-8")
    changed = 0
    for name, old, new, note in edits:
        count = text.count(old)
        if count != 1:
            problems.append(f"{path.name} · {note}：命中 {count} 次（应为 1）")
            continue
        if old != new:
            text = text.replace(old, new)
            changed += 1
        print(f"  [ok] {path.name} · {note}")
    if changed:
        path.write_text(text, encoding="utf-8")
    return changed


def main() -> int:
    problems: list[str] = []
    total = 0

    print("== 项目根 ==")
    grouped: dict[str, list[tuple[str, str, str, str]]] = {}
    for rel, old, new, note in EDITS:
        grouped.setdefault(rel, []).append((rel, old, new, note))
    for rel, edits in grouped.items():
        total += apply(APP / rel, edits, problems)

    print("== 交付根脚本 ==")
    grouped2: dict[str, list[tuple[str, str, str, str]]] = {}
    for rel, old, new, note in VERIFY_EDITS:
        grouped2.setdefault(rel, []).append((rel, old, new, note))
    for rel, edits in grouped2.items():
        total += apply(DELIVERY / rel, edits, problems)

    # RELEASE_MANIFEST.json 用 JSON 写，避免手改坏格式
    manifest = APP / "RELEASE_MANIFEST.json"
    if manifest.is_file():
        data = json.loads(manifest.read_text(encoding="utf-8"))
        if data.get("version") != NEW:
            data["version"] = NEW
            manifest.write_text(
                json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            total += 1
            print("  [ok] RELEASE_MANIFEST.json · version -> " + NEW)

    if problems:
        print("\n以下替换未命中，整体仍需人工确认：")
        for item in problems:
            print("  [FAIL]", item)
        return 1

    print(f"\n共改写 {total} 处")
    # 残留检查
    leftovers: list[str] = []
    for rel in list(grouped) + ["RELEASE_MANIFEST.json"]:
        p = APP / rel
        if p.is_file() and OLD in p.read_text(encoding="utf-8") and "RELEASE_NOTES" not in rel:
            leftovers.append(f"{rel} 仍含 {OLD}")
    for rel in grouped2:
        p = DELIVERY / rel
        if p.is_file() and OLD in p.read_text(encoding="utf-8"):
            leftovers.append(f"{rel} 仍含 {OLD}")
    if leftovers:
        print("残留：")
        for item in leftovers:
            print("  -", item)
    else:
        print(f"残留检查：除历史发布说明外，已无 {OLD} 字样")
    return 0


if __name__ == "__main__":
    sys.exit(main())
