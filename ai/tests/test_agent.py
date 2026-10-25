"""M3W5-1 验收:图拓扑/终止条件/拒答/verify重试/闲聊(全部 stub LLM,零网络)。"""
import pytest
from langgraph.graph import END

from app.agent import nodes
from app.agent.graph import _after_router, _after_sufficiency, _after_verify, run_agent
from app.config import settings
from app.retrieval.store import Hit


class FakeFast:
    """complete_json 脚本回放:node -> [(schema_obj, degraded), ...]"""

    def __init__(self, script):
        self.script = {k: list(v) for k, v in script.items()}
        self.calls = []

    def complete_json(self, prompt_id, variables, node, fallback, **kw):
        self.calls.append(node)
        queue = self.script.get(node) or []
        if not queue:
            return fallback(), True
        obj, degraded = queue.pop(0)
        return obj, degraded


def hit(cid, content="条款内容"):
    return Hit(cid, 5, None, content, "手册 > 假期", 3, 0.9, "rrf")


@pytest.fixture(autouse=True)
def no_rerank(monkeypatch):
    # 单测中 rerank 直通(真实降级路径已由 test_retrieval 覆盖)
    monkeypatch.setattr("app.retrieval.fusion.rerank",
                        lambda q, hits, **kw: (hits, False))


def run(payload, fast_script, retrieval_results, synth_deltas=None, synth_forbidden=False):
    fast = FakeFast(fast_script)
    retrievals = list(retrieval_results)
    monkey_calls = {"synth": 0, "retrieve": 0}

    def fake_retrieve(q):
        monkey_calls["retrieve"] += 1
        return retrievals.pop(0) if retrievals else []

    if synth_forbidden:
        def fake_synth(msgs, emit):
            monkey_calls["synth"] += 1
            raise AssertionError("synth 不应被调用")
            yield  # pragma: no cover
    else:
        def fake_synth(msgs, emit):
            monkey_calls["synth"] += 1
            for d in (synth_deltas or ["答案", "[1]"]):
                yield d

    orig_fast, orig_ret, orig_synth = nodes.get_fast, nodes.get_retrieval, nodes.get_synth
    nodes.get_fast = lambda: fast
    nodes.get_retrieval = lambda: fake_retrieve
    nodes.get_synth = lambda: fake_synth
    try:
        events: list[tuple[str, dict]] = []

        def emit(event, data):
            events.append((event, data))

        result = run_agent(payload, emit)
        return result, events, monkey_calls
    finally:
        nodes.get_fast, nodes.get_retrieval, nodes.get_synth = orig_fast, orig_ret, orig_synth


from app.agent.schemas import (DecomposeOut, GradeItem, GradeOut, RouterOut,
                               SufficiencyOut, VerifyOut)


def trace_of(events):
    return [d["node"] for e, d in events if e == "trace"]


def test_simple_flow_full_sequence():
    result, events, calls = run(
        {"message": "年假几天"},
        {"router": [(RouterOut(type="SIMPLE", reason="单跳"), False)],
         "grade": [(GradeOut(items=[GradeItem(id=1, score=9), GradeItem(id=2, score=8)]), False)],
         "verify": [(VerifyOut(verdict="PASS", unsupported=""), False)]},
        [[hit(1), hit(2)]],
        synth_deltas=["年假为5天", "[1]"])
    assert trace_of(events) == ["rewrite", "router", "retrieve", "rerank",
                                "grade", "synthesize", "verify"]
    assert "年假为5天" in result["answer"]
    assert [c["no"] for c in result["citations"]] == [1]
    assert any(e == "token" for e, _ in events)
    assert events[-1][0] == "done"


def test_chitchat_skips_retrieval():
    result, events, calls = run(
        {"message": "你好"},
        {"router": [(RouterOut(type="CHITCHAT", reason="闲聊"), False)],
         "verify": [(VerifyOut(verdict="PASS", unsupported=""), False)]},
        [], synth_forbidden=True)
    assert trace_of(events) == ["rewrite", "router", "synthesize", "verify"]
    assert "知识库助手" in result["answer"]
    assert calls["retrieve"] == 0 and calls["synth"] == 0


def test_complex_two_hops_then_enough():
    result, events, calls = run(
        {"message": "对比年假和报销时限"},
        {"router": [(RouterOut(type="COMPLEX", reason="跨文档"), False)],
         "decompose": [(DecomposeOut(subQuestions=["年假几天", "报销时限"]), False)],
         "grade": [(GradeOut(items=[GradeItem(id=1, score=9)]), False),
                   (GradeOut(items=[GradeItem(id=1, score=9)]), False)],
         "sufficiency": [(SufficiencyOut(verdict="NEED_MORE", missing="报销"), False),
                         (SufficiencyOut(verdict="ENOUGH", missing=""), False)],
         "verify": [(VerifyOut(verdict="PASS", unsupported=""), False)]},
        [[hit(1, "年假条款")], [hit(2, "报销条款")]],
        synth_deltas=["综合结论", "[1]", " [2]"])
    tr = trace_of(events)
    assert tr.count("retrieve") == 2
    assert result["hops"] == 2
    assert len(result["citations"]) == 2


def test_max_hops_capped():
    result, events, _ = run(
        {"message": "无底洞问题"},
        {"router": [(RouterOut(type="COMPLEX", reason="难"), False)],
         "decompose": [(DecomposeOut(subQuestions=["q1", "q2", "q3", "q4"]), False)],
         "grade": [(GradeOut(items=[GradeItem(id=1, score=9)]), False)] * 6,
         "sufficiency": [(SufficiencyOut(verdict="NEED_MORE", missing="还缺"), False)] * 6,
         "verify": [(VerifyOut(verdict="PASS", unsupported=""), False)]},
        [[hit(i)] for i in range(1, 10)],
        synth_deltas=["结论", "[1]"])
    assert trace_of(events).count("retrieve") == settings.max_hops  # 封顶 3 跳


def test_zero_new_hits_terminates_loop():
    result, events, _ = run(
        {"message": "两跳后无新增"},
        {"router": [(RouterOut(type="COMPLEX", reason="多跳"), False)],
         "decompose": [(DecomposeOut(subQuestions=["a", "b"]), False)],
         "grade": [(GradeOut(items=[GradeItem(id=1, score=9)]), False),
                   (GradeOut(items=[GradeItem(id=1, score=9)]), False)],  # 第二跳同块,去重后零新增
         "sufficiency": [(SufficiencyOut(verdict="NEED_MORE", missing="x"), False)],
         "verify": [(VerifyOut(verdict="PASS", unsupported=""), False)]},
        [[hit(1)], [hit(1)]],
        synth_deltas=["答案", "[1]"])
    assert trace_of(events).count("retrieve") == 2  # 零新增即停,不进第三跳


def test_refuse_when_no_hits():
    result, events, calls = run(
        {"message": "不相干问题"},
        {"router": [(RouterOut(type="SIMPLE", reason="单跳"), False)]},
        [[]], synth_forbidden=True)
    assert "无法回答" in result["answer"]
    assert result["citations"] == []
    assert calls["synth"] == 0


def test_verify_fail_retries_synth_once():
    result, events, _ = run(
        {"message": "校验问题"},
        {"router": [(RouterOut(type="SIMPLE", reason="单跳"), False)],
         "grade": [(GradeOut(items=[GradeItem(id=1, score=9)]), False)],
         "verify": [(VerifyOut(verdict="FAIL", unsupported="句A"), False),
                    (VerifyOut(verdict="PASS", unsupported=""), False)]},
        [[hit(1)]],
        synth_deltas=["第一版", "[1]"])
    tr = trace_of(events)
    assert tr.count("synthesize") == 2 and tr.count("verify") == 2
    assert result["verified"] == "PASS"


def test_verify_fail_twice_appends_disclaimer():
    result, events, _ = run(
        {"message": "仍不通过"},
        {"router": [(RouterOut(type="SIMPLE", reason="单跳"), False)],
         "grade": [(GradeOut(items=[GradeItem(id=1, score=9)]), False)],
         "verify": [(VerifyOut(verdict="FAIL", unsupported="句A"), False),
                    (VerifyOut(verdict="FAIL", unsupported="句B"), False)]},
        [[hit(1)]],
        synth_deltas=["存疑答案", "[1]"])
    assert "请人工复核" in result["answer"]
    assert trace_of(events).count("synthesize") == 2


def test_router_resets_state_each_round():
    fast = FakeFast({"router": [(RouterOut(type="SIMPLE", reason="r"), False)]})
    orig = nodes.get_fast
    nodes.get_fast = lambda: fast
    try:
        delta = nodes.router_node({"question": "q", "standalone_query": "q",
                                   "hits": [{"chunkId": 1}]})
    finally:
        nodes.get_fast = orig
    assert delta["hits"] == [] and delta["hop"] == 0  # 每轮独立,无残留(§7.4)
