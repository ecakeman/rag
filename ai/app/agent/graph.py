"""LangGraph 图(DESIGN §8.2):编译一次进程单例(§8.4)。

边定义:
START → rewrite → router
router ─ CHITCHAT → synthesize;SIMPLE → retrieve;COMPLEX → decompose → retrieve
retrieve → rerank → grade
grade ─(SIMPLE)→ synthesize;─(COMPLEX)→ sufficiency
sufficiency ─ NEED_MORE 且 hop<MAX_HOPS 且 new_hit_count>0 → retrieve
            ─ 否则 → synthesize
synthesize → verify
verify ─ PASS → END;FAIL 且未重试 → synthesize;FAIL 已重试 → END(节点内已加声明)
"""
from __future__ import annotations

from functools import partial

from langgraph.graph import END, StateGraph

from app.agent import nodes
from app.agent.state import AgentState
from app.config import settings


def _after_router(state: AgentState) -> str:
    q = state.get("qtype", "SIMPLE")
    if q == "CHITCHAT":
        return "chitchat"
    if q == "COMPLEX":
        return "complex"
    return "simple"


def _after_grade(state: AgentState) -> str:
    return "complex" if state.get("qtype") == "COMPLEX" else "simple"


def _after_sufficiency(state: AgentState) -> str:
    if (state.get("verdict") == "NEED_MORE"
            and state.get("hop", 0) < settings.max_hops
            and state.get("new_hit_count", 0) > 0):
        return "more"
    return "done"


def _after_verify(state: AgentState) -> str:
    if state.get("verified") == "FAIL" and not state.get("verify_retry"):
        return "retry"
    return "end"


def build_graph(emit=None):
    g = StateGraph(AgentState)
    g.add_node("rewrite", nodes.rewrite_node)
    g.add_node("router", nodes.router_node)
    g.add_node("decompose", nodes.decompose_node)
    g.add_node("retrieve", nodes.retrieve_node)
    g.add_node("rerank", nodes.rerank_node)
    g.add_node("grade", nodes.grade_node)
    g.add_node("sufficiency", nodes.sufficiency_node)
    g.add_node("synthesize", partial(nodes.synthesize_node, emit=emit))
    g.add_node("verify", nodes.verify_node)

    g.set_entry_point("rewrite")
    g.add_edge("rewrite", "router")
    g.add_conditional_edges("router", _after_router,
                            {"chitchat": "synthesize", "complex": "decompose", "simple": "retrieve"})
    g.add_edge("decompose", "retrieve")
    g.add_edge("retrieve", "rerank")
    g.add_edge("rerank", "grade")
    g.add_conditional_edges("grade", _after_grade,
                            {"complex": "sufficiency", "simple": "synthesize"})
    g.add_conditional_edges("sufficiency", _after_sufficiency,
                            {"more": "retrieve", "done": "synthesize"})
    g.add_edge("synthesize", "verify")
    g.add_conditional_edges("verify", _after_verify,
                            {"retry": "synthesize", "end": END})
    return g.compile()


def _router_without_model(state: AgentState) -> dict:
    return {"qtype": "SIMPLE", "hop": 0, "hits": [], "new_hit_count": 0,
            "standalone_query": state.get("standalone_query") or state.get("question"),
            "current_query": state.get("current_query") or state.get("question")}


def _grade_without_model(state: AgentState) -> dict:
    candidates = state.get("candidates") or []
    return {"hits": candidates, "new_hit_count": len(candidates), "verdict": "ENOUGH"}


def build_retrieval_graph():
    """只跑检索节点。没有模型密钥时不调用 LLM，也不生成回答。"""
    from app.config import settings
    g = StateGraph(AgentState)
    g.add_node("rewrite", nodes.rewrite_node)
    g.add_node("router", nodes.router_node if settings.llm_api_key else _router_without_model)
    g.add_node("decompose", nodes.decompose_node)
    g.add_node("retrieve", nodes.retrieve_node)
    g.add_node("rerank", nodes.rerank_node)
    g.add_node("grade", nodes.grade_node if settings.llm_api_key else _grade_without_model)
    g.add_node("sufficiency", nodes.sufficiency_node)
    g.add_node("collect", lambda state: state)
    g.set_entry_point("rewrite")
    g.add_edge("rewrite", "router")
    g.add_conditional_edges("router", _after_router,
                            {"chitchat": "collect", "complex": "decompose", "simple": "retrieve"})
    g.add_edge("decompose", "retrieve")
    g.add_edge("retrieve", "rerank")
    g.add_edge("rerank", "grade")
    g.add_conditional_edges("grade", _after_grade,
                            {"complex": "sufficiency", "simple": "collect"})
    g.add_conditional_edges("sufficiency", _after_sufficiency,
                            {"more": "retrieve", "done": "collect"})
    g.add_edge("collect", END)
    return g.compile()


_GRAPH_CACHE: dict = {}


def get_graph(emit=None):
    """单例;emit 不同实例各缓存(测试与请求流)。"""
    key = id(emit)
    if key not in _GRAPH_CACHE:
        _GRAPH_CACHE[key] = build_graph(emit=emit)
    return _GRAPH_CACHE[key]


def run_agent(payload: dict, emit) -> AgentState:
    """流式执行:每个节点完成即 emit trace(§5.3);token 由 synthesize 节点内 emit。"""
    import time
    t0 = time.monotonic()
    initial: AgentState = {
        "session_id": payload.get("sessionId"),
        "message_id": payload.get("messageId"),
        "question": payload["message"],
        "history": [h if isinstance(h, dict) else h.model_dump()
                    for h in (payload.get("history") or [])],
        "trace_nodes": [],
    }
    graph = get_graph(emit=emit)
    answer, citations, verified = "", [], ""
    hops = 0
    for update in graph.stream(initial, config={"recursion_limit": 40},
                               stream_mode="updates"):
        for node, delta in update.items():
            if not isinstance(delta, dict):
                continue
            if node == "retrieve":
                hops += 1
            detail = (f"hits={len(delta.get('hits', []))}" if node == "grade"
                      else f"type={delta.get('qtype')}" if node == "router"
                      else f"verdict={delta.get('verdict')}" if node == "sufficiency"
                      else f"verified={delta.get('verified')}" if node == "verify"
                      else "")
            emit("trace", {"node": node, "status": "end", "detail": detail, "tsMs": 0})
            if node == "synthesize":
                answer = delta.get("answer", answer)
                citations = delta.get("citations", citations)
            if node == "verify":
                answer = delta.get("answer", answer)
                verified = delta.get("verified", verified)
    emit("citations", {"items": citations})
    emit("done", {"latencyMs": int((time.monotonic() - t0) * 1000)})
    return {"answer": answer, "citations": citations, "verified": verified, "hops": hops}
