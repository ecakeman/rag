"""检索编排(DESIGN §7.3):多查询扩展 → 双腿召回 → RRF → 重排 → 父块展开。"""
from __future__ import annotations

from app.config import settings
from app.ingestion.embedder import embed_texts
from app.retrieval import bm25, fusion
from app.retrieval.store import Hit, fetch_parents, vector_search


def retrieve_fused(query: str, *, doc_ids: list[int] | None = None,
                   embed_fn=None) -> list[Hit]:
    """双腿召回 + RRF 融合(不含重排)——供 agent 图的 retrieve/rerank 分节点使用(§8.2)。"""
    queries = fusion.multi_query_expand(query, llm=_query_llm())
    vec_leg: list[Hit] = []
    if embed_fn is None and not settings.effective_embed_api_key:
        try:
            from app.observe.llm_log import write_llm_call
            write_llm_call(node="embed", model=settings.embed_model, latency_ms=0,
                           status="degraded", error_snippet="embed api key missing")
        except Exception:  # noqa: BLE001
            pass
        embeddings = []
    else:
        embeddings = (embed_fn or embed_texts)(queries)
    for vec in embeddings:
        vec_leg.extend(vector_search(vec, doc_ids=doc_ids))
    seen: set[int] = set()
    vec_leg = [h for h in vec_leg if not (h.chunk_id in seen or seen.add(h.chunk_id))]
    if settings.enable_hybrid:
        bm25_leg = bm25.search(query, doc_ids=doc_ids)
        return fusion.rrf_fuse([vec_leg, bm25_leg])
    return sorted(vec_leg, key=lambda h: h.score, reverse=True)[: settings.fusion_top_k]


def hybrid_search(query: str, *, doc_ids: list[int] | None = None,
                  top_k: int | None = None, embed_fn=None) -> list[Hit]:
    """返回重排后的 top 子块(含父块 id);供 /search 与 A0 直连路径共用。"""
    fused = retrieve_fused(query, doc_ids=doc_ids, embed_fn=embed_fn)
    ranked, _degraded = fusion.rerank(query, fused)
    return ranked


def _query_llm():
    if not settings.llm_api_key or not settings.enable_multiquery:
        return None

    def expand(query: str, n: int) -> list[str]:
        from app.agent.llm import fast_llm
        raw = fast_llm().call(
            [{"role": "user", "content": f"给出{n}个检索变体，每行一个，不要解释：{query}"}],
            node="multi_query", prompt_id="multi_query", json_mode=False)
        return [line.strip() for line in raw.splitlines() if line.strip()]

    return expand


def hits_with_parents(hits: list[Hit]) -> list[dict]:
    """检索输出 DTO(§5.1 SearchItem):子块命中→返回父块内容用于展示/生成。"""
    parents = fetch_parents([h.parent_id for h in hits if h.parent_id])
    items = []
    for h in hits:
        p = parents.get(h.parent_id) if h.parent_id else None
        items.append({
            "chunkId": h.chunk_id,
            "docId": h.doc_id,
            "docTitle": (h.section_path or "").split(" > ")[0] if h.section_path else "",
            "sectionPath": h.section_path or "",
            "page": h.page,
            "text": (p.content if p else h.content),
            "score": h.score,
        })
    return items
