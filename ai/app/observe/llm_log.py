"""LLM 调用观测(DESIGN §4.3 llm_call 表/§8.4):所有模型调用一行一记录。"""
from __future__ import annotations

from sqlalchemy import text

from app.db import engine


def write_llm_call(*, node: str, model: str, session_id: int | None = None,
                   message_id: int | None = None, prompt_id: str | None = None,
                   prompt_pack: str | None = None, input_tokens: int | None = None,
                   output_tokens: int | None = None, latency_ms: int | None = None,
                   status: str = "ok", error_snippet: str | None = None) -> None:
    """同步小写入;观测失败不阻塞业务(吞异常记日志)。"""
    try:
        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO llm_call (session_id, message_id, node, model, prompt_id,
                                      prompt_pack, input_tokens, output_tokens,
                                      latency_ms, status, error_snippet)
                VALUES (:sid, :mid, :node, :model, :pid, :pack, :in_tok, :out_tok,
                        :lat, :status, :err)
            """), {"sid": session_id, "mid": message_id, "node": node, "model": model,
                   "pid": prompt_id, "pack": prompt_pack, "in_tok": input_tokens,
                   "out_tok": output_tokens, "lat": latency_ms, "status": status,
                   "err": (error_snippet or "")[:500] or None})
    except Exception:  # noqa: BLE001 - 观测不阻塞主流程
        import logging
        logging.getLogger(__name__).warning("llm_call 写入失败", exc_info=True)
