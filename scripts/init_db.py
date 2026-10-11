from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sitesaha.config import AppConfig
from sitesaha.db import KnowledgeBase
from sitesaha.ingest import ingest_directory, seed_default_knowledge


def main() -> int:
    parser = argparse.ArgumentParser(description="初始化 SiteSaha AI 本地知识库")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="删除现有 SQLite 文件并重新导入默认知识库",
    )
    args = parser.parse_args()

    config = AppConfig.from_env()
    if args.reset and config.db_path.exists():
        config.db_path.unlink()

    kb = KnowledgeBase(config.db_path)
    results = seed_default_knowledge(
        kb,
        config.knowledge_dir,
        normalized_sources_dir=config.normalized_sources_dir,
        force=args.reset,
    )
    if not results and kb.stats()["documents"]:
        results = ingest_directory(
            kb,
            config.knowledge_dir,
            category="演示摘要",
            replace=True,
        )
        results.extend(
            ingest_directory(
                kb,
                config.normalized_sources_dir,
                category="公开标准",
                replace=True,
            )
        )

    stats = kb.stats()
    print(f"数据库：{config.db_path}")
    print(f"文档：{stats['documents']}，片段：{stats['chunks']}")
    for path, document_id, chunk_count in results:
        print(f"- {path.name}: document_id={document_id}, chunks={chunk_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
