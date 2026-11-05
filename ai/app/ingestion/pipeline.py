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


class LostLease(RuntimeError):
    """续租失败后，旧 worker 不能再写这个版本。"""

# 进程内摄入状态(对账兜底用;重启后以 DB 为准)
_INGEST_STATE: dict[int, dict] = {}


def _callback(callback_url: str, payload: dict) -> None:
    try:
        httpx.post(callback_url, json=payload, timeout=10.0,
                   headers={"X-Internal-Token": settings.internal_token})
    except Exception as e:  # noqa: BLE001
        log.warning("[ingest] 回调失败(Java 可通过对账补偿): %s", e)


def _vectors(chunks: list[Chunk], embed_fn) -> list[list[float]]:
    children = [c for c in chunks if not c.is_parent]
    if embed_fn is None and not settings.effective_embed_api_key:
        return [[] for _ in children]
    return embed_texts([c.content for c in children], embed_fn=embed_fn)


def _write_legacy_chunks(doc_id: int, chunks: list[Chunk], vectors: list[list[float]]) -> int:
    """按整个文档替换块。旧 /ingest 没有版本号。"""
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
        children_meta: list[tuple] = []
        for c in chunks:
            if c.is_parent:
                continue
            vec = next(vec_iter)
            vec_literal = None if not vec else "[" + ",".join(f"{x:.6f}" for x in vec) + "]"
            row = conn.execute(text("""
                INSERT INTO doc_chunk (doc_id, parent_id, is_parent, content, embedding,
                                       section_path, page, token_count)
                VALUES (:doc, :pid, false, :content, CAST(:vec AS vector), :sp, :page, :tc)
                RETURNING id
            """), {"doc": doc_id, "pid": parent_ids.get(c.parent_index),
                   "content": c.content, "vec": vec_literal,
                   "sp": c.section_path, "page": c.page, "tc": c.token_count}).fetchone()
            children_meta.append((row[0], doc_id, parent_ids.get(c.parent_index),
                                  c.content, c.section_path, c.page))
            child_count += 1
    from app.retrieval import bm25
    bm25.remove_doc(doc_id)
    for item in children_meta:
        bm25.add_chunk(*item)
    return child_count


def _write_knowledge_chunks(doc_id: int, document_version_id: int, chunks: list[Chunk],
                            vectors: list[list[float]], *, job_id: int, lease_owner: str,
                            fencing_token: int) -> int:
    """单事务:确认仍持有任务后，只替换这个版本的块。"""
    with engine.begin() as conn:
        held = conn.execute(text("""
            SELECT lease_owner, fencing_token, lease_until > now()
            FROM ingestion_job WHERE id=:id FOR UPDATE
        """), {"id": job_id}).fetchone()
        if held is None or held[0] != lease_owner or int(held[1]) != fencing_token or not held[2]:
            raise LostLease(f"job {job_id} lease lost")
        conn.execute(text("DELETE FROM doc_chunk WHERE document_version_id = :v"), {"v": document_version_id})
        parent_ids: dict[int, int] = {}
        for idx, c in enumerate(chunks):
            if not c.is_parent:
                continue
            row = conn.execute(text("""
                INSERT INTO doc_chunk (doc_id, document_version_id, parent_id, is_parent, content, embedding,
                                       section_path, page, token_count)
                VALUES (:doc, :ver, NULL, true, :content, NULL, :sp, :page, :tc) RETURNING id
            """), {"doc": doc_id, "ver": document_version_id, "content": c.content, "sp": c.section_path,
                   "page": c.page, "tc": c.token_count}).fetchone()
            parent_ids[idx] = row[0]

        child_count = 0
        vec_iter = iter(vectors)
        for c in chunks:
            if c.is_parent:
                continue
            vec = next(vec_iter)
            vec_literal = None if not vec else "[" + ",".join(f"{x:.6f}" for x in vec) + "]"
            conn.execute(text("""
                INSERT INTO doc_chunk (doc_id, document_version_id, parent_id, is_parent, content, embedding,
                                       section_path, page, token_count)
                VALUES (:doc, :ver, :pid, false, :content, CAST(:vec AS vector), :sp, :page, :tc)
            """), {"doc": doc_id, "ver": document_version_id, "pid": parent_ids.get(c.parent_index),
                   "content": c.content, "vec": vec_literal,
                   "sp": c.section_path, "page": c.page, "tc": c.token_count})
            child_count += 1
    return child_count


def run_legacy_ingest(doc_id: int, file_path: str, file_name: str, title: str,
                      callback_url: str, embed_fn=None) -> None:
    """旧 Backend 的 /ingest。按 doc_id 替换块，不使用 document_version_id。"""
    try:
        _callback(callback_url, {"docId": doc_id, "status": "PROCESSING"})
        _INGEST_STATE[doc_id] = {"status": "PROCESSING"}
        pages = to_markdown(file_path)
        chunks = build_chunks(pages, title or Path(file_name).stem)
        n = _write_legacy_chunks(doc_id, chunks, _vectors(chunks, embed_fn))
        _INGEST_STATE[doc_id] = {"status": "READY", "chunkCount": n}
        _callback(callback_url, {"docId": doc_id, "status": "READY", "chunkCount": n})
    except Exception as e:  # noqa: BLE001
        log.error("[ingest] doc %s 失败", doc_id, exc_info=True)
        _INGEST_STATE[doc_id] = {"status": "FAILED", "errorMsg": str(e)}
        _callback(callback_url, {"docId": doc_id, "status": "FAILED", "errorMsg": str(e)[:500]})
        raise


def run_ingest(doc_id: int, file_path: str, file_name: str, title: str,
               callback_url: str, embed_fn=None) -> None:
    """兼容旧调用方的入口。"""
    run_legacy_ingest(doc_id, file_path, file_name, title, callback_url, embed_fn)


def run_knowledge_ingest(doc_id: int, file_path: str, file_name: str, title: str, *,
                         document_version_id: int, job_id: int, lease_owner: str,
                         fencing_token: int) -> None:
    """版本化摄取。只有持有租约的 job worker 可以写块。"""
    pages = to_markdown(file_path)
    chunks = build_chunks(pages, title or Path(file_name).stem)
    _write_knowledge_chunks(
        doc_id, document_version_id, chunks, _vectors(chunks, None),
        job_id=job_id, lease_owner=lease_owner, fencing_token=fencing_token,
    )


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
    from app.retrieval import bm25
    bm25.remove_doc(doc_id)
    _INGEST_STATE.pop(doc_id, None)
