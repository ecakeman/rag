"""M2W3-1 验收:重试矩阵/json_object 探测/解析降级/llm_call 观测(容器内连真实 PG)。"""
import pytest
from sqlalchemy import text

from app.agent.llm import LlmService
from app.agent.schemas import RouterOut
from app.config import settings
from app.db import engine


class FakeMsg:
    def __init__(self, content):
        self.content = content
        self.response_metadata = {"token_usage": {"prompt_tokens": 11, "completion_tokens": 7}}


class FakeClient:
    """按脚本回放:元素为 content 字符串或 Exception。"""

    def __init__(self, script):
        self.script = list(script)
        self.calls: list[dict] = []

    def invoke(self, messages, **kwargs):
        self.calls.append({"messages": messages, "kwargs": kwargs})
        item = self.script.pop(0) if self.script else "null"
        if isinstance(item, Exception):
            raise item
        return FakeMsg(item)


class TimeoutErr(Exception):
    pass


class BadRequestErr(Exception):
    status_code = 400


class ServerErr(Exception):
    status_code = 502


def svc(script) -> tuple[LlmService, FakeClient]:
    fake = FakeClient(script)
    s = LlmService(model="fake-model", temperature=0.1, timeout=5,
                   client_factory=lambda: fake)
    return s, fake


def _cleanup_llm_call():
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM llm_call WHERE model = 'fake-model'"))


def _last_llm_call():
    with engine.connect() as conn:
        return conn.execute(text(
            "SELECT node, model, prompt_pack, status FROM llm_call "
            "WHERE model='fake-model' ORDER BY id DESC LIMIT 1")).fetchone()


def test_retry_on_5xx_then_success(monkeypatch):
    monkeypatch.setattr("app.agent.llm.time.sleep", lambda s: None)
    s, fake = svc([ServerErr(), ServerErr(), '{"type":"SIMPLE","reason":"x"}'])
    out, degraded = s.complete_json("P2", {"question": "q"}, "router",
                                    fallback=lambda: RouterOut(type="SIMPLE", reason="fb"))
    assert degraded is False and out.type == "SIMPLE"
    assert len(fake.calls) == 3  # 2 次重试后成功
    row = _last_llm_call()
    assert row.model == "fake-model" and row.status == "ok" and row.prompt_pack == settings.prompt_pack
    _cleanup_llm_call()


def test_4xx_no_retry():
    s, fake = svc([BadRequestErr()])
    from app.agent.llm import _ApiError
    with pytest.raises(_ApiError):
        s.call([{"role": "user", "content": "x"}], node="router", json_mode=False)
    assert len(fake.calls) == 1
    row = _last_llm_call()
    assert row.status == "error"
    _cleanup_llm_call()


def test_json_mode_probe_400_then_without_format():
    s, fake = svc([BadRequestErr(), '{"type":"CHITCHAT","reason":"hi"}'])
    out, degraded = s.complete_json("P2", {"question": "你好"}, "router",
                                    fallback=lambda: RouterOut(type="SIMPLE", reason="fb"))
    assert degraded is False and out.type == "CHITCHAT"
    # 第1次带 response_format,探测 400 后第2次不带,且只算了2次调用(探测不耗重试)
    assert fake.calls[0]["kwargs"].get("response_format") == {"type": "json_object"}
    assert "response_format" not in fake.calls[1]["kwargs"]
    assert s.json_mode_supported is False
    _cleanup_llm_call()


def test_parse_fallback_after_bad_json():
    s, fake = svc(["不是json", "还是不是json"])
    out, degraded = s.complete_json("P2", {"question": "q"}, "router",
                                    fallback=lambda: RouterOut(type="SIMPLE", reason="fb"))
    assert degraded is True and out.reason == "fb"
    assert len(fake.calls) == 2  # 解析重试1次后降级
    _cleanup_llm_call()


def test_parse_strips_code_fence():
    s, fake = svc(["```json\n{\"type\":\"COMPLEX\",\"reason\":\"多跳\"}\n```"])
    out, degraded = s.complete_json("P2", {"question": "q"}, "router",
                                    fallback=lambda: RouterOut(type="SIMPLE", reason="fb"))
    assert degraded is False and out.type == "COMPLEX"
    _cleanup_llm_call()
