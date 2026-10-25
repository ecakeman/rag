"""摄入管线(DESIGN §7.2):异步任务 + webhook 回调 + 幂等写库。"""
from __future__ import annotations

import logging
from pathlib import Path

import httpx
from sqlalchemy import text

from app.config import settings
from app.db import engine
from app.ingestion.chunker import Chunk, build_chunks
from app.ingestion.convert import to_markdown
from app.ingestion.embedder import embed_texts

log = logging.getLogger(__name__)

# 进程内摄入状态(对账兜底用;重启后以 DB 为准)
_INGEST_STATE: dict[int, dict] = {}


def _callback(callback_url: str, payload: dict) -> None:
    try:
        httpx.post(callback_url, json=payload, timeout=10.0,
                   headers={"X-Internal-Token": settings.internal_token})
    except Exception as e:  # noqa: BLE001
        log.warning("[ingest] 回调失败(Java 可通过对账补偿): %s", e)


def _write_chunks(doc_id: int, chunks: list[Chunk], vectors: list[list[float]]) -> int:
    """单事务:先删后插(幂等);父块先写拿 id,再写子块带 parent_id。返回子块数。"""
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM doc_chunk WHERE doc_id = :d"), {"d": doc_id})
        parent_ids: dict[int, int] = {}
        for idx, c in enumerate(chunks):
            if not c.is_parent:
                continue
            row = conn.execute(text("""
                INSERT INTO doc_chunk (doc_id, parent_id, is_parent, content, embedding,
                                       section_path, page, token_count)
                VALUES (:doc, NULL, true, :content, NULL, :sp, :page, :tc) RETURNING id
            """), {"doc": doc_id, "content": c.content, "sp": c.section_path,
                   "page": c.page, "tc": c.token_count}).fetchone()
            parent_ids[idx] = row[0]

        child_count = 0
        vec_iter = iter(vectors)
        for c in chunks:
            if c.is_parent:
                continue
            vec = next(vec_iter)
            vec_literal = "[" + ",".join(f"{x:.6f}" for x in vec) + "]"
            conn.execute(text("""
                INSERT INTO doc_chunk (doc_id, parent_id, is_parent, content, embedding,
                                       section_path, page, token_count)
                VALUES (:doc, :pid, false, :content, :vec, :sp, :page, :tc)
            """), {"doc": doc_id, "pid": parent_ids.get(c.parent_index),
                   "content": c.content, "vec": vec_literal,
                   "sp": c.section_path, "page": c.page, "tc": c.token_count})
            child_count += 1
    return child_count


def run_ingest(doc_id: int, file_path: str, file_name: str, title: str,
               callback_url: str, embed_fn=None) -> None:
    """后台任务主体(§7.2 步骤2)。"""
    try:
        _callback(callback_url, {"docId": doc_id, "status": "PROCESSING"})
        _INGEST_STATE[doc_id] = {"status": "PROCESSING"}

        pages = to_markdown(file_path)
        chunks = build_chunks(pages, title or Path(file_name).stem)
        children = [c for c in chunks if not c.is_parent]
        vectors = embed_texts([c.content for c in children], embed_fn=embed_fn)
        n = _write_chunks(doc_id, chunks, vectors)

        _INGEST_STATE[doc_id] = {"status": "READY", "chunkCount": n}
        _callback(callback_url, {"docId": doc_id, "status": "READY", "chunkCount": n})
    except Exception as e:  # noqa: BLE001
        log.error("[ingest] doc %s 失败", doc_id, exc_info=True)
        _INGEST_STATE[doc_id] = {"status": "FAILED", "errorMsg": str(e)}
        _callback(callback_url, {"docId": doc_id, "status": "FAILED",
                                 "errorMsg": str(e)[:500]})


def ingest_status(doc_id: int) -> dict:
    """对账查询:进程状态优先,DB 兜底(有子块=READY)。"""
    st = _INGEST_STATE.get(doc_id)
    if st:
        return {"docId": doc_id, **st}
    with engine.connect() as conn:
        n = conn.execute(text(
            "SELECT count(*) FROM doc_chunk WHERE doc_id=:d AND is_parent=false"),
            {"d": doc_id}).scalar()
    return {"docId": doc_id,
            "status": "READY" if n else "PROCESSING",
            "chunkCount": n or None}


def delete_doc_chunks(doc_id: int) -> None:
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM doc_chunk WHERE doc_id=:d"), {"d": doc_id})
    _INGEST_STATE.pop(doc_id, None)
