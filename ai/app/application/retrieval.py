"""一次检索的业务入口。内部可以走 LangGraph，对外只返回原文片段。"""
from __future__ import annotations

import asyncio

from app.agent.graph import build_retrieval_graph


def composed_query(query: str, context: dict | None) -> str:
    ctx = context or {}
    parts = [str(query or "").strip()]
    for key in ("serviceName", "episodeSummary"):
        value = str(ctx.get(key) or "").strip()
        if value and value not in parts[0]:
            parts.append(value)
    facts = ctx.get("knownFacts") or []
    if isinstance(facts, list):
        joined = "\n".join(parts)
        for fact in facts:
            value = str(fact).strip()
            if value and value not in joined:
                parts.append(value)
                joined = "\n".join(parts)
    return "\n".join(part for part in parts if part)


def _results(state: dict, invocation_id: str) -> dict:
    hits = state.get("hits") or state.get("candidates") or []
    results = []
    for hit in hits:
        document_id = hit.get("docId")
        version_id = hit.get("documentVersionId")
        chunk_id = hit.get("chunkId")
        title = hit.get("title")
        if document_id in (None, "") or version_id in (None, "") or chunk_id in (None, "") or not title:
            continue
        results.append({
            "rank": len(results) + 1,
            "documentId": str(document_id),
            "documentVersionId": str(version_id),
            "chunkId": str(chunk_id),
            "title": title,
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


async def retrieve(query: str, invocation_id: str, *, top_k: int = 8,
                   knowledge_space_ids: list[str] | None = None, context: dict | None = None) -> dict:
    spaces = [str(item).strip() for item in (knowledge_space_ids or []) if str(item).strip()]
    if not spaces:
        return {"schemaVersion": "knowledge-retrieval-result-v1", "invocationId": invocation_id, "results": []}
    question = composed_query(query, context)
    graph = build_retrieval_graph()
    state = await graph.ainvoke({
        "question": question,
        "standalone_query": question,
        "current_query": question,
        "hop": 0,
        "hits": [],
        "trace_nodes": [],
        "context": context or {},
        "knowledge_space_ids": spaces,
        "top_k": top_k,
    })
    result = _results(state, invocation_id)
    result["results"] = result["results"][:top_k]
    return result


def retrieve_documents(query: str, invocation_id: str) -> dict:
    return asyncio.run(retrieve(query, invocation_id))
