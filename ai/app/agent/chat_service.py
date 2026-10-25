"""问答流服务(DESIGN §8.2):
ENABLE_AGENT=True 走 LangGraph(M3W5 接入);False 走 A0 单轮直连:
  retrieve →(rerank)→ synthesize(流式) → 拒答兜底
事件协议见 §5.3:trace/token/citations/done/error(meta 由 Java 先发)。
"""
from __future__ import annotations

import logging
import re
import time
from collections.abc import AsyncIterator, Callable

from app.agent import prompts as prompt_assets
from app.agent.llm import synth_llm
from app.config import settings
from app.retrieval.service import hybrid_search
from app.retrieval.store import fetch_parents

log = logging.getLogger(__name__)

CITE = re.compile(r"\[(\d{1,2})\]")

REFUSE_TEXT = "根据现有知识库资料，无法回答该问题。建议：1) 更换问法 2) 上传相关文档后再试。"


def _emit_format(event: str, data: dict) -> str:
    import json
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def build_context(hits: list) -> tuple[str, list[dict]]:
    """子块命中→父块;截 CTX_BUDGET_CHUNKS 块/每块 ≤900;返回 (numbered_text, citations)。"""
    parents = fetch_parents([h.parent_id for h in hits if h.parent_id])
    blocks: list[str] = []
    citations: list[dict] = []
    for h in hits[: settings.ctx_budget_chunks]:
        parent = parents.get(h.parent_id) if h.parent_id else None
        text = parent.content if parent else h.content
        if len(text) > settings.ctx_budget_chunk_tokens:
            text = text[: settings.ctx_budget_chunk_tokens] + "…[截断]"
        no = len(blocks) + 1
        blocks.append(f"<doc src=\"{h.section_path or ''}\">[{no}] {text}</doc>")
        citations.append({
            "no": no, "chunkId": h.chunk_id, "docId": h.doc_id,
            "docTitle": (h.section_path or "").split(" > ")[0] or "",
            "sectionPath": h.section_path or "", "page": h.page,
            "text": text[:200],
        })
    return "\n".join(blocks), citations


def run_a0_chat(*, message: str, session_id: int | None, message_id: int | None,
                stream_fn=None) -> AsyncIterator[str]:
    """A0 直连路径(同步生成器,SSE 文本块)。stream_fn 可注入假流用于测试。"""
    t0 = time.monotonic()
    try:
        # ---- retrieve ----
        t1 = time.monotonic()
        hits = hybrid_search(message)
        yield _emit_format("trace", {"node": "retrieve", "status": "end",
                                     "detail": f"hits={len(hits)}",
                                     "tsMs": int((time.monotonic() - t1) * 1000)})
        if not hits:
            yield _emit_format("token", {"text": REFUSE_TEXT})
            yield _emit_format("citations", {"items": []})
            yield _emit_format("done", {"latencyMs": int((time.monotonic() - t0) * 1000)})
            return

        numbered, citations = build_context(hits)

        # ---- synthesize(流式) ----
        messages = prompt_assets.render("P6", numbered_chunks=numbered, question=message)
        t2 = time.monotonic()
        full: list[str] = []
        if stream_fn is not None:
            deltas = stream_fn(messages)
        else:
            deltas = synth_llm().stream(messages, node="synthesize", prompt_id="P6",
                                        session_id=session_id, message_id=message_id)
        for delta in deltas:
            full.append(delta)
            yield _emit_format("token", {"text": delta})
        yield _emit_format("trace", {"node": "synthesize", "status": "end",
                                     "detail": f"chars={sum(len(x) for x in full)}",
                                     "tsMs": int((time.monotonic() - t2) * 1000)})

        # 引用编号映射:文中出现过的编号保留,未定义编号丢弃(§8.3)
        used = {int(m) for m in CITE.findall("".join(full))}
        kept = [c for c in citations if c["no"] in used] if used else []
        yield _emit_format("citations", {"items": kept})
        yield _emit_format("done", {"latencyMs": int((time.monotonic() - t0) * 1000)})
    except Exception as e:  # noqa: BLE001
        log.error("[chat] 失败", exc_info=True)
        yield _emit_format("error", {"code": 5032, "message": f"AI 服务内部错误: {e}"[:200]})


async def stream_chat(payload: dict) -> AsyncIterator[str]:
    """FastAPI StreamingResponse 主体:按消融开关选择路径(§8.2)。"""
    if settings.enable_agent:
        # M3W5: LangGraph 路径接入后替换此处
        agen = run_a0_chat(message=payload["message"], session_id=payload.get("sessionId"),
                           message_id=payload.get("messageId"))
        for chunk in agen:
            yield chunk
        return
    for chunk in run_a0_chat(message=payload["message"], session_id=payload.get("sessionId"),
                             message_id=payload.get("messageId")):
        yield chunk
