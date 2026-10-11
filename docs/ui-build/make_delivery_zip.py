"""打包 16.0.0 交付包（第 16 轮 §14）。

排除规则（依据 RELEASE_MANIFEST.json 的 excluded 与项目 .gitignore）：
  · .env            —— 含真实 API key，绝不外发
  · data/sitesaha.db —— 启动时自动从 data/knowledge 重建，不必带
  · __pycache__ / *.pyc / *.pyo
  · 临时截图目录与临时脚本产物
  · .venv 之类虚拟环境

保留：
  · 全部源码、测试、部署配置、知识库播种源
  · 前端分片源码（docs/ui-build 的核心文件），方便后续重建
  · 验收截图各留一张桌面 + 一张手机
  · .git 目录（可选，便于同事直接推仓库）

用法：python make_delivery_zip.py [--with-git] [--no-evidence]
"""

from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

BUILD = Path(__file__).resolve().parent
APP = BUILD.parent.parent

# 目录名黑名单：任何路径段命中就跳过
SKIP_DIRS = {
    "__pycache__",
    ".venv",
    "venv",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "_shot",
    ".scratch",
}

# 文件名/后缀黑名单
SKIP_SUFFIX = {".pyc", ".pyo", ".pyd", ".db", ".db-journal", ".db-wal", ".db-shm",
               ".log", ".bak", ".bak-v91", ".tmp"}

# 明确排除的文件（相对路径）
# 注意：.env **包含在内** —— 用户要求「同事拿到就能直接部署」，
# 所以把已实测可用的三个 key 一起打包。默认排除，用 --with-env 才带。
SKIP_FILES = {
    "docs/ui-build/index_script_check.js",
    "docs/ui-build/index_full.html",
}

# 保留的截图（其余 evidence 图不打包）
KEEP_SHOTS = {
    "desktop-home.png", "desktop-ask.png", "desktop-pre.png",
    "desktop-sos.png", "desktop-learn.png",
    "mobile-home.png", "mobile-ask.png", "mobile-pre.png",
    "mobile-sos.png", "mobile-learn.png",
}


def should_skip(rel: Path, *, with_git: bool, with_evidence: bool,
                with_env: bool) -> str:
    parts = rel.parts
    if not with_git and parts and parts[0] == ".git":
        return "版本库（--with-git 可包含）"
    if rel.name == ".env" and not with_env:
        return ".env（含密钥，需 --with-env）"
    for part in parts[:-1]:
        if part in SKIP_DIRS:
            return f"目录 {part}"
    if rel.name in SKIP_FILES:
        return "明确排除"
    if rel.suffix.lower() in SKIP_SUFFIX:
        return f"后缀 {rel.suffix}"
    if rel.name.startswith("_check_") or rel.name.startswith("_crop"):
        return "临时截图"
    if "evidence" in parts and not with_evidence:
        if rel.name not in KEEP_SHOTS:
            return "非代表性截图"
    if rel.name == "webapp.py.bak-v91":
        return "备份文件"
    return ""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--with-git", action="store_true",
                        help="包含 .git 目录（便于同事直接推送仓库）")
    parser.add_argument("--no-evidence", action="store_true",
                        help="完全不包含截图")
    parser.add_argument("--with-env", action="store_true",
                        help="包含 .env（内含真实 API key，仅在私密转交时使用）")
    args = parser.parse_args()
    with_evidence = not args.no_evidence

    stamp = "16.0.0"
    out = APP.parent / f"sitesaha-ai-{stamp}-delivery.zip"
    if out.exists():
        out.unlink()

    included: list[tuple[Path, int]] = []
    skipped: dict[str, int] = {}

    for path in APP.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(APP)
        reason = should_skip(rel, with_git=args.with_git,
                             with_evidence=with_evidence, with_env=args.with_env)
        if reason:
            skipped[reason] = skipped.get(reason, 0) + 1
            continue
        try:
            size = path.stat().st_size
        except OSError:
            continue
        included.append((rel, size))

    print(f"=== 打包 {len(included)} 个文件 ===")
    total = sum(size for _rel, size in included)
    print(f"    原始大小 {total / (1024 * 1024):.1f} MB")
    print()
    print("=== 已排除 ===")
    for reason, count in sorted(skipped.items(), key=lambda kv: -kv[1]):
        print(f"    {count:>5} 个  {reason}")

    # 关键文件必须在
    must_have = [
        "webapp.py", "Dockerfile", "render.yaml", "requirements.txt",
        "Procfile", "RELEASE_MANIFEST.json", "README.md", "DEPLOY.md",
        "V16_RELEASE_NOTES.md", "DEPLOYMENT_STATUS.md", "部署交接单.md",
        "sitesaha/checklists.py", "sitesaha/xlsx.py", "sitesaha/structure.py",
        "tests/test_checklists.py", "tests/test_xlsx.py", "tests/test_structure.py",
        "docs/ui-build/index_head.html", "docs/ui-build/index_body.html",
        "docs/ui-build/index_script_a.js", "docs/ui-build/index_script_b.js",
        "docs/ui-build/assemble.py", "docs/ui-build/apply_v13_theme.py",
        "data/knowledge/01_jgj59_2011_demo.md",
    ]
    present = {str(rel).replace("\\", "/") for rel, _ in included}
    missing = [name for name in must_have if name not in present]
    print()
    if missing:
        print("[FAIL] 缺少关键文件：")
        for name in missing:
            print(f"    {name}")
        return 1
    print("[ok] 关键文件齐全")

    # .env 的处理：默认排除；--with-env 时包含，但要显式提醒
    env_included = any(rel.name == ".env" for rel, _ in included)
    for rel, _ in included:
        if rel.name.startswith(".env.") and rel.name != ".env.example":
            print(f"[FAIL] {rel} 可能是额外的密钥文件，中止")
            return 1

    if env_included:
        print()
        print("  " + "!" * 66)
        print("  警告：本包含 .env，里面有真实 API key。")
        print("  · 只做私密转交，不要上传到任何公开仓库或网盘分享链接")
        print("  · 同事部署后应立刻在平台上改成环境变量，并从压缩包删掉 .env")
        print("  · .gitignore 已排除 .env，所以它不会随 git 提交")
        print("  " + "!" * 66)
    else:
        print("[ok] 未包含 .env（密钥不外发）")

    print()
    print(f"=== 写入 {out.name} ===")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for rel, _size in sorted(included, key=lambda item: str(item[0])):
            zf.write(APP / rel, arcname=str(APP.name) + "/" + str(rel).replace("\\", "/"))

    print(f"[ok] 完成：{out}")
    print(f"    压缩包 {out.stat().st_size / (1024 * 1024):.1f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
