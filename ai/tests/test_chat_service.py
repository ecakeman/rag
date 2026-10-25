"""M2W4-1 验收(python 侧):A0 流事件序列/拒答/引用过滤/异常事件。"""
import json

from app.agent import chat_service as cs
from app.retrieval.store import Hit


def parse_events(chunks: list[str]) -> list[tuple[str, dict]]:
    events = []
    for c in chunks:
        for block in c.split("\n\n"):
            block = block.strip()
            if not block:
                continue
            ev, data = None, None
            for line in block.splitlines():
                if line.startswith("event: "):
                    ev = line[7:]
                elif line.startswith("data: "):
                    data = json.loads(line[6:])
            events.append((ev, data))
    return events


def hit(cid, doc=5):
    return Hit(cid, doc, cid + 100, "子块内容", "手册 > 假期 > 年假", 3, 0.9, "rrf")


def test_a0_event_sequence_with_citations(monkeypatch):
    monkeypatch.setattr(cs, "hybrid_search", lambda q, **k: [hit(1), hit(2)])
    monkeypatch.setattr(cs, "fetch_parents", lambda ids: {101: type("P", (), {"content": "父块内容长文本" * 20})()})
    deltas = iter(["年假为5天[1]", "，满10年为10天[2]"])
    chunks = list(cs.run_a0_chat(message="年假几天", session_id=1, message_id=10,
                                 stream_fn=lambda msgs: deltas))
    events = parse_events(chunks)
    names = [e for e, _ in events]
    assert names[0] == "trace" and events[0][1]["node"] == "retrieve"
    assert "token" in names and "citations" in names and names[-1] == "done"
    cit = next(d for e, d in events if e == "citations")
    assert [c["no"] for c in cit["items"]] == [1, 2]
    assert cit["items"][0]["docTitle"] == "手册"
    done = events[-1][1]
    assert "latencyMs" in done


def test_a0_refuse_when_no_hits(monkeypatch):
    monkeypatch.setattr(cs, "hybrid_search", lambda q, **k: [])
    chunks = list(cs.run_a0_chat(message="不相关", session_id=1, message_id=1,
                                 stream_fn=lambda m: iter([])))
    events = parse_events(chunks)
    assert any(e == "token" and "无法回答" in d["text"] for e, d in events)
    assert next(d for e, d in events if e == "citations")["items"] == []
    assert events[-1][0] == "done"


def test_a0_error_event_on_stream_failure(monkeypatch):
    monkeypatch.setattr(cs, "hybrid_search", lambda q, **k: [hit(1)])
    monkeypatch.setattr(cs, "fetch_parents", lambda ids: {})

    def boom(msgs):
        raise RuntimeError("llm down")
        yield  # pragma: no cover

    chunks = list(cs.run_a0_chat(message="q", session_id=None, message_id=None,
                                 stream_fn=boom))
    events = parse_events(chunks)
    err = next(d for e, d in events if e == "error")
    assert err["code"] == 5032


def test_a0_unused_citation_dropped(monkeypatch):
    monkeypatch.setattr(cs, "hybrid_search", lambda q, **k: [hit(1), hit(2), hit(3)])
    monkeypatch.setattr(cs, "fetch_parents", lambda ids: {})
    deltas = iter(["答案只引用了第二条[2]"])
    chunks = list(cs.run_a0_chat(message="q", session_id=None, message_id=None,
                                 stream_fn=lambda m: deltas))
    events = parse_events(chunks)
    cit = next(d for e, d in events if e == "citations")
    assert [c["no"] for c in cit["items"]] == [2]
