"""Embedding 客户端(DESIGN §7.2d):批量、重试、llm_call 观测。"""
from __future__ import annotations

import time
from collections.abc import Callable

from app.config import settings
from app.observe.llm_log import write_llm_call
from app.runtime_config import cfg

EmbedFn = Callable[[list[str]], list[list[float]]]


def _openai_embed_fn() -> EmbedFn:
    """OpenAI 兼容 embedding(llama-index 实现);失败按 llm_retry 重试。"""
    from llama_index.embeddings.openai import OpenAIEmbedding

    embed = OpenAIEmbedding(
        # model_name kwarg 绕过 llama-index 的 OpenAI 模型白名单校验;
        # 连接信息优先级: DB embed 覆盖 > DB llm 覆盖 > 环境变量(空=沿用 llm 配置)
        model_name=cfg("embed.model", settings.embed_model),
        api_key=cfg("embed.api_key") or cfg("llm.api_key") or settings.effective_embed_api_key,
        api_base=cfg("embed.base_url") or cfg("llm.base_url") or settings.effective_embed_base_url,
        dimensions=settings.embed_dim,
        embed_batch_size=settings.embed_batch,
    )

    def fn(texts: list[str]) -> list[list[float]]:
        last: Exception | None = None
        for attempt in range(settings.llm_retry + 1):
            try:
                return embed.get_text_embedding_batch(texts, show_progress=False)
            except Exception as e:  # noqa: BLE001
                last = e
                time.sleep(2 ** attempt)
        raise RuntimeError(f"embedding 失败: {last}") from last

    return fn


def embed_texts(texts: list[str], embed_fn: EmbedFn | None = None) -> list[list[float]]:
    """批量向量化:按 embed_batch 分批;每批写 llm_call(node=embed)。"""
    fn = embed_fn or _openai_embed_fn()
    out: list[list[float]] = []
    for i in range(0, len(texts), settings.embed_batch):
        batch = texts[i:i + settings.embed_batch]
        t0 = time.monotonic()
        try:
            vecs = fn(batch)
            write_llm_call(node="embed", model=settings.embed_model,
                           latency_ms=int((time.monotonic() - t0) * 1000),
                           status="ok", input_tokens=sum(len(t) for t in batch))
        except Exception as e:  # noqa: BLE001
            write_llm_call(node="embed", model=settings.embed_model,
                           latency_ms=int((time.monotonic() - t0) * 1000),
                           status="error", error_snippet=str(e))
            raise
        out.extend(vecs)
    return out
