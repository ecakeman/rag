"""全局配置(DESIGN §7.1):全部常量的单一事实来源。"""
from __future__ import annotations

import os
from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ---- 摄入 ----
    child_tokens: int = 256
    overlap_tokens: int = 40
    parent_fallback_tokens: int = 768
    embed_batch: int = 64

    # ---- 检索 ----
    multi_query_n: int = 3
    top_k_per_leg: int = 8
    fusion_top_k: int = 10
    rerank_top_n: int = 5
    rrf_k: int = 60
    bm25_init_on_startup: bool = True

    # ---- agent ----
    grade_threshold: int = 6
    max_hops: int = 3
    temperature_fast: float = 0.1
    temperature_synth: float = 0.3

    # ---- prompt 资产 ----
    prompt_dir: str = "app/agent/prompts"
    prompt_pack: str = "no-prompts"  # M2W3-1 起启动时计算指纹

    # ---- 上下文预算 ----
    history_max_tokens: int = 2000
    message_truncate_chars: int = 500
    ctx_budget_system: int = 500
    ctx_budget_chunks: int = 8
    ctx_budget_chunk_tokens: int = 900
    ctx_budget_question: int = 200
    ctx_budget_output: int = 2000
    fast_call_budget: int = 1500

    # ---- 超时/重试 ----
    llm_timeout_fast: int = 15
    llm_timeout_synth: int = 60
    llm_retry: int = 2
    rerank_timeout: int = 5
    embed_dim: int = 1024

    # ---- 消融开关 ----
    enable_hybrid: bool = True
    enable_multiquery: bool = True
    enable_rerank: bool = True
    enable_agent: bool = True

    # ---- 模型接入(全 OpenAI 兼容;换厂商零代码改动,只改 env) ----
    llm_base_url: str = "https://open.bigmodel.cn/api/paas/v4/"
    llm_api_key: str = ""
    llm_fast_model: str = "glm-4-flash"
    llm_synth_model: str = "glm-4.5"
    llm_judge_model: str = ""  # 空=用 synth
    embed_base_url: str = ""   # 空=用 llm_base_url
    embed_api_key: str = ""    # 空=用 llm_api_key
    embed_model: str = "embedding-3"
    rerank_base_url: str = "https://api.siliconflow.cn/v1"
    rerank_api_key: str = ""
    rerank_model: str = "BAAI/bge-reranker-v2-m3"

    # ---- 服务 ----
    internal_token: str = "dev-doc-qa-internal-token"
    database_url: str = "postgresql+psycopg://postgres:root123@db:5432/doc_qa"

    model_config = {"env_file": ".env", "extra": "ignore"}

    @property
    def effective_embed_base_url(self) -> str:
        return self.embed_base_url or self.llm_base_url

    @property
    def effective_embed_api_key(self) -> str:
        return self.embed_api_key or self.llm_api_key

    @property
    def effective_judge_model(self) -> str:
        return self.llm_judge_model or self.llm_synth_model


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
