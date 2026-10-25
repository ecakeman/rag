"""Agent 节点实现(DESIGN §8.3)。

依赖注入缝(测试 monkeypatch 这三个工厂):
- get_fast()      -> LlmService(结构化)
- get_retrieval() -> callable(query) -> list[Hit]
- get_synth()     -> callable(messages, emit) -> iterable[str] 流式增量
"""
from __future__ import annotations

import logging
from typing import Callable, Iterable

from app.agent.llm import LlmService, fast_llm, synth_llm
from app.agent.schemas import (DecomposeOut, RewriteOut, RouterOut, SufficiencyOut, VerifyOut)
from app.agent.state import AgentState
from app.agent.chat_service import REFUSE_TEXT, build_context, CITE
from app.agent import prompts as prompt_assets
from app.config import settings

log = logging.getLogger(__name__)

# ---- 注入缝(默认生产实现) ----


def get_fast() -> LlmService:
    return fast_llm()


def get_retrieval() -> Callable:
    from app.retrieval.service import retrieve_fused
    return retrieve_fused


def get_synth() -> Callable[[list[dict], Callable | None], Iterable[str]]:
    def _synth(messages, emit):
        return synth_llm().stream(messages, node="synthesize", prompt_id="P6")
    return _synth


def _mark(state: AgentState, node: str) -> None:
    state.setdefault("trace_nodes", []).append(node)


# ---- 节点 ----

def rewrite_node(state: AgentState) -> dict:
    _mark(state, "rewrite")
    question = state["question"]
    history = state.get("history") or []
    if not history:
        return {"standalone_query": question, "current_query": question}
    hist_text = "\n".join(f"{m['role']}: {m['content'][:settings.message_truncate_chars]}"
                          for m in history[-6:])
    out, degraded = get_fast().complete_json(
        "P1", {"history": hist_text, "question": question}, "rewrite",
        fallback=lambda: RewriteOut(query=question))
    return {"standalone_query": out.query or question, "current_query": out.query or question}


def router_node(state: AgentState) -> dict:
    _mark(state, "router")
    from app.agent.schemas import RouterOut
    out, degraded = get_fast().complete_json(
        "P2", {"question": state["standalone_query"]}, "router",
        fallback=lambda: RouterOut(type="SIMPLE", reason="parse-fallback"))
    qtype = out.type if out.type in ("SIMPLE", "COMPLEX", "CHITCHAT") else "SIMPLE"
    return {"qtype": qtype, "hop": 0,
            "hits": [], "new_hit_count": 0, "verify_retry": False}


def decompose_node(state: AgentState) -> dict:
    _mark(state, "decompose")
    out, _ = get_fast().complete_json(
        "P3", {"question": state["standalone_query"]}, "decompose",
        fallback=lambda: DecomposeOut(subQuestions=[state["standalone_query"]]))
    subs = [s for s in out.subQuestions if s and s.strip()][:3] or [state["standalone_query"]]
    return {"sub_questions": subs, "current_query": subs[0], "hop": 0}


def retrieve_node(state: AgentState) -> dict:
    _mark(state, "retrieve")
    query = state.get("current_query") or state["standalone_query"]
    hits = get_retrieval()(query)
    return {"candidates": [
        {"chunkId": h.chunk_id, "docId": h.doc_id, "parentId": h.parent_id,
         "content": h.content, "sectionPath": h.section_path, "page": h.page,
         "score": h.score} for h in hits]}


def rerank_node(state: AgentState) -> dict:
    _mark(state, "rerank")
    from app.retrieval.store import Hit
    from app.retrieval.fusion import rerank as do_rerank
    hits = [Hit(c["chunkId"], c["docId"], c["parentId"], c["content"],
                c["sectionPath"], c["page"], c["score"], "rrf")
            for c in state.get("candidates", [])]
    ranked, degraded = do_rerank(state.get("current_query", ""), hits)
    return {"candidates": [
        {"chunkId": h.chunk_id, "docId": h.doc_id, "parentId": h.parent_id,
         "content": h.content, "sectionPath": h.section_path, "page": h.page,
         "score": h.score} for h in ranked]}


def grade_node(state: AgentState) -> dict:
    _mark(state, "grade")
    from app.agent.schemas import GradeItem, GradeOut
    candidates = state.get("candidates", [])[:10]
    if not candidates:
        return {"new_hit_count": 0}
    chunks_block = "\n".join(
        f'<chunk id="{i}">{c["content"][:400]}</chunk>'
        for i, c in enumerate(candidates, start=1))
    fallback = lambda: GradeOut(items=[GradeItem(id=i, score=5)  # noqa: E731
                                       for i in range(1, len(candidates) + 1)])
    out, _ = get_fast().complete_json(
        "P4", {"question": state["standalone_query"], "chunks_block": chunks_block},
        "grade", fallback=fallback)
    scores = {item.id: item.score for item in out.items}
    merged = list(state.get("hits", []))
    existing = {h["chunkId"] for h in merged}
    new_count = 0
    for i, c in enumerate(candidates, start=1):
        if scores.get(i, 0) >= settings.grade_threshold and c["chunkId"] not in existing:
            merged.append(c)
            existing.add(c["chunkId"])
            new_count += 1
    return {"hits": merged, "new_hit_count": new_count}


def sufficiency_node(state: AgentState) -> dict:
    _mark(state, "sufficiency")
    summary = "\n".join(f"- {h['content'][:120]}" for h in state.get("hits", [])[:8]) or "(暂无)"
    fallback = lambda: SufficiencyOut(verdict="ENOUGH", missing="")  # noqa: E731
    out, _ = get_fast().complete_json(
        "P5", {"question": state["standalone_query"], "hits_summary": summary},
        "sufficiency", fallback=fallback)
    update: dict = {"verdict": out.verdict}
    if out.verdict == "NEED_MORE":
        subs = state.get("sub_questions", [])
        hop = state.get("hop", 0) + 1
        update["hop"] = hop
        # 下一跳查询:优先取剩余子问题,否则用 missing 描述(§8.3)
        if hop < len(subs):
            update["current_query"] = subs[hop]
        else:
            update["current_query"] = (out.missing or state["standalone_query"])[:120]
    return update


def synthesize_node(state: AgentState, emit=None) -> dict:
    _mark(state, "synthesize")
    update: dict = {}
    if state.get("verified") == "FAIL" and not state.get("verify_retry"):
        update["verify_retry"] = True  # verify 失败后的重试轮(§8.2)

    if state.get("qtype") == "CHITCHAT" and not state.get("hits"):
        answer = "你好！我是企业知识库助手，可以回答公司制度、文档相关的问题。"
        if emit:
            emit("token", {"text": answer})
        return {**update, "answer": answer, "citations": []}

    hits = state.get("hits", [])
    if not hits:
        if emit:
            emit("token", {"text": REFUSE_TEXT})
        return {**update, "answer": REFUSE_TEXT, "citations": []}

    from app.retrieval.store import Hit
    hit_objs = [Hit(h["chunkId"], h["docId"], h["parentId"], h["content"],
                    h["sectionPath"], h["page"], h.get("score", 0), "rrf") for h in hits]
    numbered, citations = build_context(hit_objs)
    messages = prompt_assets.render("P6", numbered_chunks=numbered,
                                    question=state["standalone_query"])
    parts: list[str] = []
    for delta in get_synth()(messages, emit):
        parts.append(delta)
        if emit:
            emit("token", {"text": delta})
    answer = "".join(parts)
    used = {int(m) for m in CITE.findall(answer)}
    kept = [c for c in citations if c["no"] in used] if used else []
    return {**update, "answer": answer, "citations": kept}


def verify_node(state: AgentState) -> dict:
    _mark(state, "verify")
    hits = state.get("hits", [])
    if not hits or not state.get("answer"):
        return {"verified": "PASS"}
    from app.retrieval.store import Hit
    hit_objs = [Hit(h["chunkId"], h["docId"], h["parentId"], h["content"],
                    h["sectionPath"], h["page"], 0, "rrf") for h in hits]
    numbered, _cits = build_context(hit_objs)
    fallback = lambda: VerifyOut(verdict="PASS", unsupported="")  # noqa: E731
    out, _ = get_fast().complete_json(
        "P7", {"answer": state["answer"], "numbered_chunks": numbered},
        "verify", fallback=fallback)
    if out.verdict == "FAIL":
        if state.get("verify_retry"):
            # 重试后仍 FAIL:附加声明后结束(§8.2)
            return {"verified": "FAIL",
                    "answer": state["answer"] + "\n\n(注:以上回答部分内容未能被资料完全支撑,请人工复核。)"}
        return {"verified": "FAIL"}
    return {"verified": "PASS"}
