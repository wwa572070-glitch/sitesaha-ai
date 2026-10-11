from __future__ import annotations

import argparse
import base64
import json
import urllib.parse
import urllib.request
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPOSITORY = "priscilla254/RAG-Construction-Assistant"
REF = "main"
API_ROOT = f"https://api.github.com/repos/{REPOSITORY}"
USER_AGENT = "SiteSaha-AI"

TARGET_FILES = [
    "LICENSE",
    "README.md",
    "app.py",
    "src/rag_assistant/config.py",
    "src/rag_assistant/retriever.py",
    "src/rag_assistant/keyword_search.py",
    "src/rag_assistant/vector_store.py",
    "src/rag_assistant/generator.py",
    "src/rag_assistant/pipeline.py",
]


def request_json(url: str) -> dict:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/vnd.github+json",
        },
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def fetch_file(path: str) -> bytes:
    quoted = urllib.parse.quote(path)
    url = f"{API_ROOT}/contents/{quoted}?ref={REF}"
    payload = request_json(url)
    if payload.get("encoding") != "base64":
        raise RuntimeError(f"Unsupported GitHub content encoding for {path}")
    return base64.b64decode(payload["content"].replace("\n", ""))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="下载许可证兼容的 GitHub 参考项目文件"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "third_party" / "github" / "RAG-Construction-Assistant",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output = args.output.resolve()
    metadata = request_json(API_ROOT)
    if (metadata.get("license") or {}).get("spdx_id") != "MIT":
        raise RuntimeError("Reference repository is not MIT licensed.")

    for path in TARGET_FILES:
        target = output / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(fetch_file(path))
        print(f"已下载 {path}")

    manifest = {
        "repository": metadata["html_url"],
        "description": metadata.get("description", ""),
        "default_branch": metadata.get("default_branch", REF),
        "license": metadata["license"]["spdx_id"],
        "selected_files": TARGET_FILES,
        "integration_reason": (
            "The project demonstrates grounded citations, hybrid BM25 plus "
            "vector retrieval, RRF fusion, per-source result caps, and an "
            "offline-friendly Streamlit workflow."
        ),
    }
    (output / "SOURCE.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"参考项目已写入：{output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
