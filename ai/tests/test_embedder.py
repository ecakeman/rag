"""M1W2-2 验收:批量分批调用/失败传播(llm_call 写入在无 DB 时静默)。"""
import pytest

from app.config import settings
from app.ingestion.embedder import embed_texts


def test_batches_by_embed_batch_size():
    calls = []

    def fake_fn(texts):
        calls.append(len(texts))
        return [[0.1] * 4 for _ in texts]

    texts = ["块" * 10 for _ in range(130)]
    vecs = embed_texts(texts, embed_fn=fake_fn)
    assert len(vecs) == 130
    assert calls == [settings.embed_batch, settings.embed_batch, 130 - 2 * settings.embed_batch]


def test_error_propagates():
    def boom(texts):
        raise RuntimeError("embedding 服务不可用")

    with pytest.raises(RuntimeError, match="embedding 服务不可用"):
        embed_texts(["x"], embed_fn=boom)


def test_empty_input_no_calls():
    calls = []
    embed_texts([], embed_fn=lambda t: calls.append(t) or [])
    assert calls == []
