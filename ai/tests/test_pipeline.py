"""M1W2-2 验收:管线流程(回调时序/失败回调),DB 写入以 monkeypatch 隔离。"""
from app.ingestion import pipeline


def test_run_ingest_callbacks_processing_then_ready(monkeypatch, tmp_path):
    callbacks = []
    monkeypatch.setattr(pipeline, "_callback", lambda url, p: callbacks.append(p))
    monkeypatch.setattr(pipeline, "to_markdown",
                        lambda p: [(1, "# 手册\n## 假期\n年假 5 天。")])
    monkeypatch.setattr(pipeline, "_write_chunks", lambda d, c, v: 3)
    monkeypatch.setattr(pipeline, "embed_texts", lambda texts, embed_fn=None: [[0.0] * 8] * len(texts))

    f = tmp_path / "a.md"
    f.write_text("x", encoding="utf-8")
    pipeline.run_ingest(9, str(f), "a.md", "手册", "http://cb", embed_fn=lambda t: [[0.0]] * len(t))

    assert [c["status"] for c in callbacks] == ["PROCESSING", "READY"]
    assert callbacks[1]["chunkCount"] == 3
    assert pipeline._INGEST_STATE[9]["status"] == "READY"


def test_run_ingest_failure_sends_failed_callback(monkeypatch, tmp_path):
    callbacks = []
    monkeypatch.setattr(pipeline, "_callback", lambda url, p: callbacks.append(p))
    monkeypatch.setattr(pipeline, "to_markdown", lambda p: (_ for _ in ()).throw(RuntimeError("解析炸了")))

    f = tmp_path / "a.pdf"
    f.write_bytes(b"x")
    pipeline.run_ingest(10, str(f), "a.pdf", "t", "http://cb")

    assert callbacks[-1]["status"] == "FAILED"
    assert "解析炸了" in callbacks[-1]["errorMsg"]
    assert pipeline._INGEST_STATE[10]["status"] == "FAILED"


def test_write_chunks_sql_contains_idempotent_delete():
    import inspect
    src = inspect.getsource(pipeline._write_chunks)
    assert "DELETE FROM doc_chunk WHERE doc_id" in src
