from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
EXCLUDED_PARTS = {
    ".git",
    ".pytest_cache",
    ".venv",
    "__pycache__",
    "outputs",
    "work",
}
EXCLUDED_SUFFIXES = {
    ".pyc",
    ".pyo",
}
EXCLUDED_NAMES = {
    ".env",
    "RELEASE_MANIFEST.json",
    "sitesaha.db-shm",
    "sitesaha.db-wal",
    "sitesaha.db",
}


def should_include(path: Path) -> bool:
    relative = path.relative_to(PROJECT_ROOT)
    if any(part in EXCLUDED_PARTS for part in relative.parts):
        return False
    if path.suffix.lower() in EXCLUDED_SUFFIXES:
        return False
    if path.name in EXCLUDED_NAMES:
        return False
    if path.name.startswith("webapp.") and path.suffix == ".log":
        return False
    return path.is_file()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成 SiteSaha AI 发布 ZIP")
    parser.add_argument(
        "--output",
        type=Path,
        default=(
            PROJECT_ROOT.parent
            / "sitesaha-ai-online-v9-source.zip"
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        output.unlink()

    files = sorted(
        path
        for path in PROJECT_ROOT.rglob("*")
        if should_include(path)
    )
    manifest = {
        "name": "筑安智培 SiteSaha AI",
        "version": "9.1.0",
        "packaged_at": datetime.now(timezone.utc).isoformat(),
        "description": (
            "面向建筑一线新员工的AI安全培训智能体"
        ),
        "file_count": len(files),
        "files": [str(path.relative_to(PROJECT_ROOT)) for path in files],
        "notes": [
            "公开附件来自济南市住房和城乡建设局。",
            "OpenStd 标准仅包含公开元数据和官方入口，未绕过验证码。",
            "GitHub 参考项目为 MIT 许可，许可证已随包保留。",
        ],
    }

    with zipfile.ZipFile(
        output,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        for path in files:
            relative = path.relative_to(PROJECT_ROOT)
            archive.write(path, arcname=str(relative))
        archive.writestr(
            "RELEASE_MANIFEST.json",
            json.dumps(manifest, ensure_ascii=False, indent=2),
        )

    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    print(f"ZIP: {output}")
    print(f"FILES: {len(files)}")
    print(f"BYTES: {output.stat().st_size}")
    print(f"SHA256: {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
