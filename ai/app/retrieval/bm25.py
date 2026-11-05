"""BM25 腿(DESIGN §7.3):jieba 分词 + 进程内索引;启动全量重建,ingest 后增量。"""
from __future__ import annotations

import threading
from dataclasses import dataclass

import jieba
from rank_bm25 import BM25Okapi
from sqlalchemy import text

from app.db import engine
from app.retrieval.store import Hit

_LOCK = threading.Lock()


@dataclass
class _Entry:
    chunk_id: int
    doc_id: int
    parent_id: int | None
    content: str
    section_path: str | None
    page: int | None
    document_version_id: int | None = None
    knowledge_space_id: str | None = None
    title: str | None = None


_CORPUS: list[_Entry] = []
_BM25: BM25Okapi | None = None

_CURRENT_SQL = """
    SELECT c.id, c.doc_id, c.parent_id, c.content, c.section_path, c.page,
           c.document_version_id, d.space_id, d.title
    FROM doc_chunk c
    JOIN document d ON d.id = c.doc_id
    JOIN document_version dv ON dv.id = c.document_version_id
    WHERE c.is_parent = false
      AND dv.status = 'READY'
      AND d.current_version_id = dv.id
"""


def _tokenize(s: str) -> list[str]:
    return [t for t in jieba.lcut(s) if t.strip()]


def _replace(corpus: list[_Entry]) -> None:
    global _CORPUS, _BM25
    _CORPUS = corpus
    _BM25 = BM25Okapi([_tokenize(item.content) for item in corpus]) if corpus else None


def rebuild() -> int:
    """Knowledge 模式：只装载当前 READY 版本。返回子块数。"""
    with engine.connect() as conn:
        rows = conn.execute(text(_CURRENT_SQL)).fetchall()
    corpus = [_Entry(r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8]) for r in rows]
    with _LOCK:
        _replace(corpus)
    return len(corpus)


def rebuild_legacy() -> int:
    """Legacy 模式：只读 doc_chunk，不连接 document 或 document_version。"""
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT id, doc_id, parent_id, content, section_path, page
            FROM doc_chunk WHERE is_parent = false
        """)).fetchall()
    corpus = [_Entry(r[0], r[1], r[2], r[3], r[4], r[5]) for r in rows]
    with _LOCK:
        _replace(corpus)
    return len(corpus)


def add_chunk(chunk_id: int, doc_id: int, parent_id: int | None,
              content: str, section_path: str | None, page: int | None,
              document_version_id: int | None = None,
              knowledge_space_id: str | None = None) -> None:
    """ingest 后增量(粗粒度锁,§8.4)。"""
    with _LOCK:
        _CORPUS.append(_Entry(chunk_id, doc_id, parent_id, content, section_path, page,
                              document_version_id, knowledge_space_id))
        _replace(list(_CORPUS))


def remove_doc(doc_id: int) -> None:
    with _LOCK:
        _replace([item for item in _CORPUS if item.doc_id != doc_id])


def remove_version(document_version_id: int) -> None:
    with _LOCK:
        _replace([item for item in _CORPUS if item.document_version_id != document_version_id])


def search(query: str, *, top_k: int | None = None,
           doc_ids: list[int] | None = None,
           knowledge_space_ids: list[str] | None = None) -> list[Hit]:
    from app.config import settings
    if knowledge_space_ids is not None and not knowledge_space_ids:
        return []
    allowed = set(knowledge_space_ids) if knowledge_space_ids is not None else None
    k = top_k or settings.top_k_per_leg
    with _LOCK:
        if not _BM25 or not _CORPUS:
            return []
        pairs = list(zip(list(_CORPUS), _BM25.get_scores(_tokenize(query))))
    scored = sorted(pairs, key=lambda p: p[1], reverse=True)
    out: list[Hit] = []
    for entry, score in scored:
        if score == 0:
            continue
        if doc_ids and entry.doc_id not in doc_ids:
            continue
        if allowed is not None and entry.knowledge_space_id not in allowed:
            continue
        out.append(Hit(entry.chunk_id, entry.doc_id, entry.parent_id, entry.content,
                       entry.section_path, entry.page, round(float(score), 4), "bm25",
                       entry.document_version_id, entry.title, entry.knowledge_space_id))
        if len(out) >= k:
            break
    return out
