"""Agent 状态(DESIGN §8.1)。全部字段可序列化(checkpointer 安全)。"""
from __future__ import annotations

from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    session_id: int | None
    message_id: int | None
    question: str
    history: list[dict]        # [{role,content}](仅 rewrite 使用,§8.3)
    standalone_query: str
    current_query: str          # 本跳实际检索词(子问题或独立问题)
    qtype: str                  # SIMPLE | COMPLEX | CHITCHAT
    sub_questions: list[str]
    hop: int
    candidates: list[dict]      # 本跳检索候选(序列化 Hit)
    hits: list[dict]            # 累计相关块(按 chunkId 去重)
    new_hit_count: int
    verdict: str                # ENOUGH | NEED_MORE
    answer: str
    citations: list[dict]
    verified: str               # PASS | FAIL
    verify_retry: bool
    trace_nodes: list[str]      # 节点执行序(测试与 trace 依据)
    context: dict               # 调用方传入的故障上下文
    knowledge_space_ids: list[str]
    top_k: int
