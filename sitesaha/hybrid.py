from __future__ import annotations

from collections.abc import Sequence

from .db import KnowledgeBase
from .models import SearchResult


RRF_K = 60
SOURCE_MULTIPLIERS = {
    "公开标准": 1.12,
    "演示摘要": 0.88,
}

QUERY_EXPANSIONS = {
    ("第一次", "新工人", "新人", "入职", "入场", "新进场"): (
        "入场安全教育 实名制 安全帽 个人防护 班前交底 临边洞口 应急撤离"
    ),
    ("安全帽", "头部防护"): "进入施工现场 正确佩戴 安全帽",
    ("安全带", "坠落防护"): "高处作业 安全带 高挂低用 可靠挂点",
    ("脚手架", "架子"): "脚手架 连墙件 剪刀撑 防护栏杆 脚手板 验收",
    ("临电", "配电箱", "触电", "用电"): (
        "施工用电 配电箱 一机一闸一漏一箱 接地 漏电保护"
    ),
    ("塔吊", "塔机", "吊装"): (
        "塔式起重机 起重吊装 限位 制动 钢丝绳 警戒区"
    ),
    ("基坑", "坍塌"): "基坑支护 临边防护 监测 渗水 裂缝 撤离",
}

ROLE_EXPANSIONS = {
    "普工/杂工": "基础安全教育 PPE 临边洞口 机械 临时用电",
    "钢筋工": "钢筋加工机械 吊运 临边洞口 防护",
    "木工": "模板支撑 电锯 圆盘锯 高处 临边",
    "电工": "临时用电 配电箱 漏电保护 停送电 接地",
    "焊工": "动火 焊机 气瓶 防火 灭火器 防护",
    "架子工": "脚手架 连墙件 剪刀撑 验收 高处作业",
}

def role_expansion(worker_role: str) -> str:
    return ROLE_EXPANSIONS.get(worker_role, "")


def expand_query(question: str) -> str:
    additions: list[str] = []
    for triggers, expansion in QUERY_EXPANSIONS.items():
        if any(trigger in question for trigger in triggers):
            additions.append(expansion)
    return " ".join(dict.fromkeys(additions))


def reciprocal_rank_fusion(
    rankings: Sequence[Sequence[int]],
    *,
    weights: Sequence[float] | None = None,
    rrf_k: int = RRF_K,
) -> list[tuple[int, float]]:
    if weights is None:
        weights = [1.0] * len(rankings)
    if len(weights) != len(rankings):
        raise ValueError("weights and rankings must have the same length")

    scores: dict[int, float] = {}
    for ranking, weight in zip(rankings, weights, strict=True):
        for rank, chunk_id in enumerate(ranking, start=1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + weight / (rrf_k + rank)
    return sorted(scores.items(), key=lambda item: item[1], reverse=True)


def cap_per_source(
    results: Sequence[SearchResult],
    *,
    top_k: int,
    max_per_source: int,
) -> list[SearchResult]:
    if top_k < 1:
        return []
    if max_per_source < 1:
        return list(results[:top_k])

    selected: list[SearchResult] = []
    overflow: list[SearchResult] = []
    counts: dict[str, int] = {}
    for result in results:
        count = counts.get(result.source, 0)
        if result.source and count >= max_per_source:
            overflow.append(result)
            continue
        selected.append(result)
        if result.source:
            counts[result.source] = count + 1
        if len(selected) >= top_k:
            return selected

    if len(selected) < top_k:
        selected.extend(overflow[: top_k - len(selected)])
    return selected


class HybridRetriever:
    """Fuse SQLite FTS and local sparse-vector rankings with weighted RRF.

    The RRF and per-source cap design is adapted from
    priscilla254/RAG-Construction-Assistant (MIT), with the external Chroma
    dependency replaced by a deterministic local sparse-vector index.
    """

    def __init__(
        self,
        kb: KnowledgeBase,
        *,
        vector_weight: float = 0.65,
        keyword_weight: float = 0.35,
        max_per_source: int = 3,
    ):
        self.kb = kb
        self.vector_weight = vector_weight
        self.keyword_weight = keyword_weight
        self.max_per_source = max_per_source

    def search(self, question: str, *, top_k: int = 5, worker_role: str = "") -> list[SearchResult]:
        pool = max(20, top_k * 4)
        expansion = expand_query(question)
        role_hint = role_expansion(worker_role)
        retrieval_query = f"{question} {expansion} {role_hint}".strip()
        lexical = self.kb.search(retrieval_query, top_k=pool)
        vector = self.kb.vector_search(retrieval_query, top_k=pool)
        if not lexical:
            return cap_per_source(
                vector,
                top_k=top_k,
                max_per_source=self.max_per_source,
            )
        if not vector:
            return cap_per_source(
                lexical,
                top_k=top_k,
                max_per_source=self.max_per_source,
            )

        fused = reciprocal_rank_fusion(
            [
                [result.chunk_id for result in lexical],
                [result.chunk_id for result in vector],
            ],
            weights=[self.keyword_weight, self.vector_weight],
        )
        by_id = {result.chunk_id: result for result in lexical}
        by_id.update({result.chunk_id: result for result in vector})

        ranked: list[SearchResult] = []
        for chunk_id, rrf_score in fused:
            result = by_id.get(chunk_id)
            if result is None:
                continue
            weighted_score = rrf_score * SOURCE_MULTIPLIERS.get(
                result.category, 1.0
            )
            ranked.append(
                SearchResult(
                    chunk_id=result.chunk_id,
                    document_id=result.document_id,
                    title=result.title,
                    source=result.source,
                    version=result.version,
                    category=result.category,
                    heading=result.heading,
                    content=result.content,
                    score=round(weighted_score, 8),
                )
            )
        ranked.sort(key=lambda item: item.score, reverse=True)
        return cap_per_source(
            ranked,
            top_k=top_k,
            max_per_source=self.max_per_source,
        )
