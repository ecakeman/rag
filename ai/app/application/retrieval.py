"""一次检索的业务入口。内部可以走 LangGraph，对外只返回原文片段。"""
from __future__ import annotations

import asyncio

from app.agent.graph import build_retrieval_graph


def _results(state: dict, invocation_id: str) -> dict:
    hits = state.get("hits") or state.get("candidates") or []
    results = []
    for rank, hit in enumerate(hits, start=1):
        results.append({
            "rank": rank,
            "documentId": str(hit.get("docId") or ""),
            "documentVersionId": str(hit.get("documentVersionId") or "1"),
            "chunkId": str(hit.get("chunkId") or ""),
            "title": (hit.get("sectionPath") or "").split(" > ")[0],
            "sectionPath": hit.get("sectionPath") or "",
            "page": hit.get("page"),
            "content": hit.get("content") or "",
            "relevanceScore": hit.get("score") or 0,
        })
    return {
        "schemaVersion": "knowledge-retrieval-result-v1",
        "invocationId": invocation_id,
        "results": results,
        "hops": state.get("hop") or 1,
    }


async def retrieve(query: str, invocation_id: str, *, space_ids: list[str] | None = None, top_k: int = 8) -> dict:
    graph = build_retrieval_graph()
    state = await graph.ainvoke({
        "question": query,
        "standalone_query": query,
        "current_query": query,
        "hop": 0,
        "hits": [],
        "trace_nodes": [],
        "knowledge_space_ids": space_ids or [],
        "top_k": top_k,
    })
    result = _results(state, invocation_id)
    result["results"] = result["results"][:top_k]
    return result


def retrieve_documents(query: str, invocation_id: str) -> dict:
    return asyncio.run(retrieve(query, invocation_id))
