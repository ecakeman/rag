"""BM25 腿(DESIGN §7.3):jieba 分词 + 进程内索引;启动全量重建,ingest 后增量。"""
from __future__ import annotations

import threading

import jieba
from rank_bm25 import BM25Okapi
from sqlalchemy import text

from app.db import engine
from app.retrieval.store import Hit

_LOCK = threading.Lock()
_CORPUS: list[tuple[int, tuple]] = []  # [(chunk_id, (doc_id,parent_id,content,section,page))]
_BM25: BM25Okapi | None = None


def _tokenize(s: str) -> list[str]:
    return [t for t in jieba.lcut(s) if t.strip()]


def rebuild() -> int:
    """全量重建(启动时)。返回子块数。"""
    global _CORPUS, _BM25
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT id, doc_id, parent_id, content, section_path, page
            FROM doc_chunk WHERE embedding IS NOT NULL
        """)).fetchall()
    corpus = [(r[0], (r[1], r[2], r[3], r[4], r[5])) for r in rows]
    with _LOCK:
        _CORPUS = corpus
        _BM25 = BM25Okapi([_tokenize(c[1][2]) for c in corpus]) if corpus else None
    return len(corpus)


def add_chunk(chunk_id: int, doc_id: int, parent_id: int | None,
              content: str, section_path: str | None, page: int | None) -> None:
    """ingest 后增量(粗粒度锁,§8.4)。"""
    global _BM25
    with _LOCK:
        _CORPUS.append((chunk_id, (doc_id, parent_id, content, section_path, page)))
        _BM25 = BM25Okapi([_tokenize(c[1][2]) for c in _CORPUS]) if _CORPUS else None


def remove_doc(doc_id: int) -> None:
    global _BM25
    with _LOCK:
        kept = [(cid, data) for cid, data in _CORPUS if data[0] != doc_id]
        _CORPUS.clear()
        _CORPUS.extend(kept)
        _BM25 = BM25Okapi([_tokenize(c[1][2]) for c in _CORPUS]) if _CORPUS else None


def search(query: str, *, top_k: int | None = None,
           doc_ids: list[int] | None = None) -> list[Hit]:
    from app.config import settings
    k = top_k or settings.top_k_per_leg
    with _LOCK:
        if not _BM25 or not _CORPUS:
            return []
        pairs = list(zip(_CORPUS, _BM25.get_scores(_tokenize(query))))
    scored = sorted(pairs, key=lambda p: p[1], reverse=True)
    out: list[Hit] = []
    for (cid, data), s in scored:
        if s == 0:
            continue  # rank_bm25 对命中全库的词可能给负 IDF 分,保留其相对排序
        if doc_ids and data[0] not in doc_ids:
            continue
        out.append(Hit(cid, data[0], data[1], data[2], data[3], data[4],
                       round(float(s), 4), "bm25"))
        if len(out) >= k:
            break
    return out
