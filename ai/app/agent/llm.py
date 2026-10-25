"""LLM 统一封装(DESIGN §8.4/§11.3):
- tenacity 风格重试:仅超时/5xx 重试 LLM_RETRY 次(退避 1s/4s),4xx 不重试
- json_object 兼容性探测:厂商 400 时摘除 response_format 重发,进程内记忆
- 全部调用写 llm_call(含 prompt_pack 与 usage)
- complete_json:剥围栏→json.loads→pydantic;失败重试1次;再失败用 fallback 并标记 degraded
"""
from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import Callable
from typing import TypeVar

from pydantic import BaseModel

from app.agent import prompts as prompt_assets
from app.agent.schemas import NODE_SCHEMAS
from app.config import settings
from app.observe.llm_log import write_llm_call

log = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

_FENCE = re.compile(r"^```[a-zA-Z]*\s*|\s*```$", re.M)


class _ApiError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def _status_code_of(e: Exception) -> int | None:
    for attr in ("status_code", "code"):
        v = getattr(e, attr, None)
        if isinstance(v, int):
            return v
    return None


class LlmService:
    """单一模型的调用服务;fast/synth 各实例化一个。"""

    def __init__(self, *, model: str, temperature: float, timeout: int,
                 client_factory: Callable[[], object] | None = None):
        self.model = model
        self.temperature = temperature
        self.timeout = timeout
        self._client_factory = client_factory
        self._client: object | None = None
        # 进程级 json_object 支持探测结果(None=未探测)
        self.json_mode_supported: bool | None = None

    # ---- 客户端 ----
    def _get_client(self):
        if self._client is None:
            if self._client_factory is not None:
                self._client = self._client_factory()
            else:
                from langchain_openai import ChatOpenAI

                self._client = ChatOpenAI(
                    model=self.model,
                    api_key=settings.llm_api_key,
                    base_url=settings.llm_base_url,
                    temperature=self.temperature,
                    timeout=self.timeout,
                    max_retries=0,  # 重试由本类统一管理
                )
        return self._client

    def _invoke(self, messages: list[dict], json_mode: bool):
        kwargs = {}
        if json_mode and self.json_mode_supported is not False:
            kwargs["response_format"] = {"type": "json_object"}
        try:
            return self._get_client().invoke(messages, **kwargs)
        except Exception as e:  # noqa: BLE001
            raise _ApiError(str(e), _status_code_of(e)) from e

    # ---- 带重试的调用(§8.4) ----
    def call(self, messages: list[dict], *, node: str, prompt_id: str | None = None,
             session_id: int | None = None, message_id: int | None = None,
             json_mode: bool = False) -> str:
        last: _ApiError | None = None
        for attempt in range(settings.llm_retry + 1):
            t0 = time.monotonic()
            try:
                resp = self._invoke(messages, json_mode)
                content = resp.content if hasattr(resp, "content") else str(resp)
                usage = (getattr(resp, "response_metadata", {}) or {}).get("token_usage") or {}
                write_llm_call(node=node, model=self.model, session_id=session_id,
                               message_id=message_id, prompt_id=prompt_id,
                               prompt_pack=settings.prompt_pack,
                               input_tokens=usage.get("prompt_tokens"),
                               output_tokens=usage.get("completion_tokens"),
                               latency_ms=int((time.monotonic() - t0) * 1000),
                               status="ok")
                return content
            except _ApiError as e:
                status = "error"
                # json_object 兼容性探测:厂商 400 → 摘除参数立即重发(§11.3)
                if json_mode and e.status_code == 400 and self.json_mode_supported is None:
                    self.json_mode_supported = False
                    write_llm_call(node=node, model=self.model, prompt_id=prompt_id,
                                   prompt_pack=settings.prompt_pack, latency_ms=0,
                                   status="degraded", error_snippet="json-mode-unsupported")
                    continue  # 不消耗重试次数
                # 4xx:确定性错误,不重试
                if e.status_code is not None and 400 <= e.status_code < 500:
                    write_llm_call(node=node, model=self.model, session_id=session_id,
                                   message_id=message_id, prompt_id=prompt_id,
                                   prompt_pack=settings.prompt_pack,
                                   latency_ms=int((time.monotonic() - t0) * 1000),
                                   status="error", error_snippet=str(e)[:200])
                    raise e
                last = e
                write_llm_call(node=node, model=self.model, session_id=session_id,
                               message_id=message_id, prompt_id=prompt_id,
                               prompt_pack=settings.prompt_pack,
                               latency_ms=int((time.monotonic() - t0) * 1000),
                               status="error", error_snippet=str(e)[:200])
                if attempt < settings.llm_retry:
                    time.sleep(2 ** attempt)
        raise last  # type: ignore[misc]

    # ---- 流式调用(synthesize 用,§8.3) ----
    def stream(self, messages: list[dict], *, node: str, prompt_id: str | None = None,
               session_id: int | None = None, message_id: int | None = None):
        """yield 文本增量;整次调用结束写一行 llm_call。"""
        t0 = time.monotonic()
        parts: list[str] = []
        in_tokens = out_tokens = None
        try:
            client = self._get_client()
            stream = client.stream(messages) if hasattr(client, "stream") else None
            if stream is None:  # 客户端不支持流式 → 退化为整段
                content = self.call(messages, node=node, prompt_id=prompt_id,
                                    session_id=session_id, message_id=message_id)
                yield content
                return
            for chunk in stream:
                delta = chunk.content if hasattr(chunk, "content") else str(chunk)
                if delta:
                    parts.append(delta)
                    yield delta
                usage = (getattr(chunk, "response_metadata", {}) or {}).get("token_usage") or {}
                if usage.get("completion_tokens"):
                    in_tokens = usage.get("prompt_tokens")
                    out_tokens = usage.get("completion_tokens")
            write_llm_call(node=node, model=self.model, session_id=session_id,
                           message_id=message_id, prompt_id=prompt_id,
                           prompt_pack=settings.prompt_pack,
                           input_tokens=in_tokens, output_tokens=out_tokens,
                           latency_ms=int((time.monotonic() - t0) * 1000), status="ok")
        except Exception as e:  # noqa: BLE001
            write_llm_call(node=node, model=self.model, session_id=session_id,
                           message_id=message_id, prompt_id=prompt_id,
                           prompt_pack=settings.prompt_pack,
                           latency_ms=int((time.monotonic() - t0) * 1000),
                           status="error", error_snippet=str(e)[:200])
            raise

    # ---- 结构化输出(§11.3) ----
    def complete_json(self, prompt_id: str, variables: dict, node: str,
                      fallback: Callable[[], T], *,
                      session_id: int | None = None,
                      message_id: int | None = None) -> tuple[T, bool]:
        """返回 (模型实例, 是否降级)。解析失败重试1次,再失败用 fallback。"""
        schema: type[T] = NODE_SCHEMAS.get(node) or BaseModel  # type: ignore[assignment]
        messages = prompt_assets.render(prompt_id, **variables)
        raw = ""
        for _ in range(2):  # 首次 + 解析重试1次
            raw = self.call(messages, node=node, prompt_id=prompt_id,
                            session_id=session_id, message_id=message_id,
                            json_mode=True)
            try:
                text = _FENCE.sub("", raw.strip()).strip()
                if text.startswith("json"):
                    text = text[4:].strip()
                return schema.model_validate_json(text), False
            except Exception:  # noqa: BLE001
                continue
        log.warning("[llm] %s JSON 解析失败,使用降级默认值(raw=%.80s)", node, raw)
        return fallback(), True


# ---- 服务实例(进程单例,§8.4) ----
def fast_llm() -> LlmService:
    global _FAST
    if _FAST is None:
        _FAST = LlmService(model=settings.llm_fast_model,
                           temperature=settings.temperature_fast,
                           timeout=settings.llm_timeout_fast)
    return _FAST


def synth_llm() -> LlmService:
    global _SYNTH
    if _SYNTH is None:
        _SYNTH = LlmService(model=settings.llm_synth_model,
                            temperature=settings.temperature_synth,
                            timeout=settings.llm_timeout_synth)
    return _SYNTH


_FAST: LlmService | None = None
_SYNTH: LlmService | None = None
