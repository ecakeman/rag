"""向量腿(DESIGN §7.3):手写 pgvector SQL,支持元数据过滤。"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text

from app.config import settings
from app.db import engine


@dataclass
class Hit:
    chunk_id: int
    doc_id: int
    parent_id: int | None
    content: str
    section_path: str | None
    page: int | None
    score: float
    leg: str  # "vector" | "bm25"


def _vec_literal(vec: list[float]) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in vec) + "]"


def vector_search(query_vec: list[float], *, top_k: int | None = None,
                  doc_ids: list[int] | None = None,
                  knowledge_space_ids: list[str] | None = None) -> list[Hit]:
    if knowledge_space_ids is not None and not knowledge_space_ids:
        return []
    k = top_k or settings.top_k_per_leg
    docfilter = "AND c.doc_id = ANY(:docids)" if doc_ids else ""
    if knowledge_space_ids is None:
        sql = text(f"""
            SELECT c.id, c.doc_id, c.parent_id, c.content, c.section_path, c.page,
                   1 - (c.embedding <=> CAST(:qvec AS vector)) AS score
            FROM doc_chunk c
            WHERE c.embedding IS NOT NULL
            {docfilter}
            ORDER BY c.embedding <=> CAST(:qvec AS vector)
            LIMIT :k
        """)
        params: dict = {"qvec": _vec_literal(query_vec), "k": k}
    else:
        sql = text(f"""
            SELECT c.id, c.doc_id, c.parent_id, c.content, c.section_path, c.page,
                   1 - (c.embedding <=> CAST(:qvec AS vector)) AS score
            FROM doc_chunk c
            JOIN document d ON d.id = c.doc_id
            JOIN document_version dv ON dv.id = c.document_version_id
            WHERE c.embedding IS NOT NULL
              AND c.is_parent = false
              AND dv.status = 'READY'
              AND d.current_version_id = dv.id
              AND d.space_id = ANY(:spaces)
            {docfilter}
            ORDER BY c.embedding <=> CAST(:qvec AS vector)
            LIMIT :k
        """)
        params = {"qvec": _vec_literal(query_vec), "k": k, "spaces": knowledge_space_ids}
    if doc_ids:
        params["docids"] = doc_ids
    with engine.connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [Hit(r[0], r[1], r[2], r[3], r[4], r[5], round(float(r[6]), 4), "vector")
            for r in rows]


def fetch_parents(parent_ids: list[int]) -> dict[int, Hit]:
    """small-to-big:子块命中后取父块喂生成(§8.3)。"""
    if not parent_ids:
        return {}
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT id, doc_id, NULL, content, section_path, page
            FROM doc_chunk WHERE id = ANY(:ids)
        """), {"ids": parent_ids}).fetchall()
    # 列序: id, doc_id, NULL(占位), content, section_path, page
    return {r[0]: Hit(r[0], r[1], None, r[3], r[4], r[5], 0.0, "parent") for r in rows}
