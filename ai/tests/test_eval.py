"""M2W4-2 验收:judge 输出解析/CSV 列/消融开关/promptPack 校验(mock 全链)。"""
import csv
from pathlib import Path

import pytest

from eval.run import ABLATIONS, CSV_FIELDS, apply_config, load_dataset, prompt_pack_check


def test_dataset_has_30_simple_questions():
    rows = load_dataset("simple")
    assert len(rows) == 30
    assert all(r["ref_answer"] and r["docs"] for r in rows)
    assert {r["type"] for r in rows} == {"simple"}


def test_ablation_matrix_matches_design():
    assert ABLATIONS["A0"] == dict(enable_hybrid=False, enable_multiquery=False,
                                   enable_rerank=False, enable_agent=False)
    assert ABLATIONS["A4"] == dict(enable_hybrid=True, enable_multiquery=True,
                                   enable_rerank=True, enable_agent=True)


def test_apply_config_sets_flags():
    from app.config import settings
    apply_config("A1")
    assert settings.enable_hybrid and not settings.enable_multiquery
    apply_config("A3")
    assert settings.enable_rerank and not settings.enable_agent
    apply_config("A4")  # 还原默认


def test_csv_fields_contract():
    for must in ["promptPack", "latencyMs", "hops", "degraded", "grade", "retrievalHit"]:
        assert must in CSV_FIELDS


def test_judge_parse_full_partial_wrong():
    from app.agent.schemas import JudgeOut
    j = JudgeOut.model_validate_json('{"grade":"full","reason":"一致"}')
    assert j.grade == "full"
    with pytest.raises(Exception):
        JudgeOut.model_validate_json('{"grade":"excellent"}')


def test_prompt_pack_check_warns_on_mismatch(tmp_path, capsys):
    (tmp_path / "A0_deadbeef.csv").write_text("x", encoding="utf-8")
    prompt_pack_check(tmp_path, "cafe1234")
    assert "deadbeef" in capsys.readouterr().out
