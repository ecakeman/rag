"""RRF 融合 + 多查询扩展 + 重排(DESIGN §7.3)。"""
from __future__ import annotations

import logging
import time

import httpx

from app.config import settings
from app.observe.llm_log import write_llm_call
from app.retrieval.store import Hit

log = logging.getLogger(__name__)


def rrf_fuse(legs: list[list[Hit]], *, top_k: int | None = None) -> list[Hit]:
    """score(d) = Σ_leg 1/(RRF_K + rank_leg(d)) (§7.3)。"""
    k = settings.rrf_k
    scores: dict[int, float] = {}
    best: dict[int, Hit] = {}
    for leg in legs:
        for rank, hit in enumerate(leg, start=1):
            scores[hit.chunk_id] = scores.get(hit.chunk_id, 0.0) + 1.0 / (k + rank)
            best.setdefault(hit.chunk_id, hit)
    limit = top_k or settings.fusion_top_k
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:limit]
    out = []
    for cid, s in ranked:
        h = best[cid]
        out.append(Hit(h.chunk_id, h.doc_id, h.parent_id, h.content,
                       h.section_path, h.page, round(s, 6), "rrf"))
    return out


def multi_query_expand(query: str, *, llm=None) -> list[str]:
    """生成 MULTI_QUERY_N 个变体(§7.3);llm 可注入以便测试。ENABLE_MULTIQUERY 关闭时返回原查询。"""
    if not settings.enable_multiquery:
        return [query]
    if llm is None:
        return [query]
    try:
        variants = llm(query, settings.multi_query_n)
        return [query] + list(variants)[: settings.multi_query_n]
    except Exception:  # noqa: BLE001
        return [query]


def rerank(query: str, hits: list[Hit], *, top_n: int | None = None,
           http_post=None) -> tuple[list[Hit], bool]:
    """SiliconFlow 风格 /rerank;失败/超时降级为输入序(§7.3)。返回 (结果, 是否降级)。"""
    n = top_n or settings.rerank_top_n
    if not settings.enable_rerank or not hits:
        return hits[:n], False
    post = http_post or _default_post
    t0 = time.monotonic()
    try:
        resp = post(query, [h.content for h in hits])
        order = resp  # [(index, score)] 已按分排序
        seen: dict[int, float] = {}
        for idx, score in order:
            seen[idx] = score
        reranked = [Hit(hits[i].chunk_id, hits[i].doc_id, hits[i].parent_id,
                        hits[i].content, hits[i].section_path, hits[i].page,
                        round(float(s), 4), "rerank")
                    for i, s in sorted(seen.items(), key=lambda kv: kv[1], reverse=True)]
        write_llm_call(node="rerank", model=settings.rerank_model,
                       prompt_pack=settings.prompt_pack,
                       latency_ms=int((time.monotonic() - t0) * 1000), status="ok")
        return reranked[:n], False
    except Exception as e:  # noqa: BLE001
        log.warning("[rerank] 降级为 RRF 序: %s", e)
        write_llm_call(node="rerank", model=settings.rerank_model,
                       prompt_pack=settings.prompt_pack,
                       latency_ms=int((time.monotonic() - t0) * 1000),
                       status="degraded", error_snippet=str(e)[:200])
        return hits[:n], True


def _default_post(query: str, docs: list[str]) -> list[tuple[int, float]]:
    payload = {"model": settings.rerank_model, "query": query, "documents": docs}
    headers = {"Authorization": f"Bearer {settings.rerank_api_key}"}
    with httpx.Client(timeout=settings.rerank_timeout) as client:
        resp = client.post(f"{settings.rerank_base_url}/rerank", json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
    return [(r["index"], r["relevance_score"]) for r in data["results"]]
