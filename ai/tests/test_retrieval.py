"""M2W3-2 验收:RRF 公式/BM25 中文命中/重排降级/多查询开关/向量SQL过滤(容器内真库)。"""
import pytest
from sqlalchemy import text

from app.config import settings
from app.db import engine
from app.retrieval import bm25, fusion
from app.retrieval.store import Hit, vector_search

TEST_DOC_ID = 999901


def hit(cid, score, leg="vector", doc=1):
    return Hit(cid, doc, None, f"内容{cid}", "s", 1, score, leg)


# ---------- RRF ----------

def test_rrf_formula_matches_design():
    # score(d) = Σ 1/(60+rank);构造两腿,块1双腿第一 → 必居首
    leg_a = [hit(1, 0.9), hit(2, 0.8)]
    leg_b = [hit(3, 5.0), hit(1, 4.0)]
    out = fusion.rrf_fuse([leg_a, leg_b])
    assert out[0].chunk_id == 1
    expect = 1 / (60 + 1) + 1 / (60 + 2)
    assert abs(out[0].score - round(expect, 6)) < 1e-9
    assert out[0].leg == "rrf"


def test_rrf_fuse_top_k_limit():
    legs = [[hit(i, 1.0) for i in range(1, 30)]]
    out = fusion.rrf_fuse(legs, top_k=5)
    assert len(out) == 5


# ---------- BM25 ----------

def test_bm25_chinese_hit(monkeypatch):
    rows = [
        (1, TEST_DOC_ID, None, "年假为5天,工作满10年为10天", "a", 1),
        (2, TEST_DOC_ID, None, "报销需要在30天内提交发票", "b", 2),
        (3, TEST_DOC_ID, None, "办公室空调温度设定为26度", "c", 3),
    ]
    monkeypatch.setattr(bm25, "_CORPUS", [(r[0], (r[1], r[2], r[3], r[4], r[5])) for r in rows])
    from rank_bm25 import BM25Okapi
    monkeypatch.setattr(bm25, "_BM25", BM25Okapi([bm25._tokenize(r[3]) for r in rows]))
    hits = bm25.search("年假有几天")
    assert hits and hits[0].chunk_id == 1
    hits2 = bm25.search("报销 发票")
    assert hits2 and hits2[0].chunk_id == 2


def test_bm25_doc_filter(monkeypatch):
    rows = [
        (1, TEST_DOC_ID, None, "唯一关键词量子纠缠测试", "a", 1),
        (2, TEST_DOC_ID + 1, None, "唯一关键词量子纠缠测试", "b", 1),
    ]
    monkeypatch.setattr(bm25, "_CORPUS", [(r[0], (r[1], r[2], r[3], r[4], r[5])) for r in rows])
    from rank_bm25 import BM25Okapi
    monkeypatch.setattr(bm25, "_BM25", BM25Okapi([bm25._tokenize(r[3]) for r in rows]))
    hits = bm25.search("量子纠缠", doc_ids=[TEST_DOC_ID + 1])
    assert [h.chunk_id for h in hits] == [2]


# ---------- rerank ----------

def test_rerank_orders_by_score():
    hits = [hit(1, 0.1), hit(2, 0.2), hit(3, 0.3)]
    out, degraded = fusion.rerank("q", hits, http_post=lambda q, d: [(0, 0.9), (2, 0.5), (1, 0.1)])
    assert degraded is False
    assert [h.chunk_id for h in out] == [1, 3, 2]


def test_rerank_fallback_on_error():
    def boom(q, d):
        raise TimeoutError("rerank 挂了")
    hits = [hit(1, 0.1), hit(2, 0.2)]
    out, degraded = fusion.rerank("q", hits, http_post=boom)
    assert degraded is True
    assert [h.chunk_id for h in out] == [1, 2]  # 保持 RRF 序
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM llm_call WHERE node='rerank' AND status='degraded'"))


def test_multiquery_disabled_returns_original(monkeypatch):
    monkeypatch.setattr(settings, "enable_multiquery", False)
    assert fusion.multi_query_expand("q", llm=lambda q, n: ["a"]) == ["q"]


# ---------- 向量腿(真库) ----------

def test_vector_search_with_metadata_filter():
    vec = [0.1] * settings.embed_dim
    vec_lit = "[" + ",".join(f"{x:.6f}" for x in vec) + "]"
    try:
        with engine.begin() as conn:
            conn.execute(text(
                "DELETE FROM doc_chunk WHERE doc_id IN (:a, :b)"),
                {"a": TEST_DOC_ID, "b": TEST_DOC_ID + 1})
            for i, d in [(9101, TEST_DOC_ID), (9102, TEST_DOC_ID + 1)]:
                conn.execute(text("""
                    INSERT INTO doc_chunk (id, doc_id, parent_id, is_parent, content, embedding)
                    VALUES (:id, :doc, NULL, false, :content, CAST(:vec AS vector))
                """), {"id": i, "doc": d, "content": f"测试块{i}", "vec": vec_lit})
        hits = vector_search(vec, doc_ids=[TEST_DOC_ID + 1])
        assert [h.chunk_id for h in hits] == [9102]  # 过滤生效,不越界
        hits_all = vector_search(vec)
        ids = {h.chunk_id for h in hits_all}
        assert 9101 in ids and 9102 in ids
    finally:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM doc_chunk WHERE doc_id IN (:a, :b)"),
                         {"a": TEST_DOC_ID, "b": TEST_DOC_ID + 1})
