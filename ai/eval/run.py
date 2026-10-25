"""评测执行器(DESIGN §12):
用法: python -m eval.run --config A0..A4 --dataset simple|multi_hop|all --out results/
每题输出 CSV 行(含 promptPack/跳数/降级计数),summary.md 汇总均值。
无 LLM_API_KEY 时 judge 列记 no-key,答案列记 error(LLM 调用不可用),检索指标仍产出。
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from pathlib import Path

from app.agent import prompts as prompt_assets
from app.agent.llm import LlmService
from app.agent.schemas import JudgeOut
from app.config import settings
from app.retrieval.service import hybrid_search

DATASET_DIR = Path(__file__).parent / "datasets"

# 消融开关矩阵(§12.1)
ABLATIONS: dict[str, dict] = {
    "A0": dict(enable_hybrid=False, enable_multiquery=False, enable_rerank=False, enable_agent=False),
    "A1": dict(enable_hybrid=True, enable_multiquery=False, enable_rerank=False, enable_agent=False),
    "A2": dict(enable_hybrid=True, enable_multiquery=True, enable_rerank=False, enable_agent=False),
    "A3": dict(enable_hybrid=True, enable_multiquery=True, enable_rerank=True, enable_agent=False),
    "A4": dict(enable_hybrid=True, enable_multiquery=True, enable_rerank=True, enable_agent=True),
}

CSV_FIELDS = ["id", "type", "question", "answer", "grade", "reason",
              "retrievalHit", "latencyMs", "hops", "degraded", "error", "promptPack"]


def load_dataset(name: str) -> list[dict]:
    rows: list[dict] = []
    for f in sorted(DATASET_DIR.glob(f"{name}*.csv")):
        with open(f, encoding="utf-8") as fh:
            rows.extend(csv.DictReader(fh))
    return rows


def apply_config(tag: str) -> None:
    for k, v in ABLATIONS[tag].items():
        setattr(settings, k, v)


def run_one(row: dict, judge: LlmService | None, synth=None) -> dict:
    """synth 可注入(测试);无 key 时答案留空、grade=no-key,检索指标照常产出。"""
    t0 = time.monotonic()
    out = {k: "" for k in CSV_FIELDS}
    out.update(id=row["id"], type=row.get("type", "simple"), question=row["question"],
               promptPack=settings.prompt_pack,
               hops=1 if not settings.enable_agent else "")
    try:
        hits = hybrid_search(row["question"])
        expect_docs = [d.strip() for d in row["docs"].split("|")]
        hit_titles = {(h.section_path or "").split(" > ")[0] for h in hits}
        out["retrievalHit"] = int(bool(hits) and any(
            e in t or t in e for e in expect_docs for t in hit_titles))

        from app.agent import chat_service as cs
        if not hits:
            out["answer"] = cs.REFUSE_TEXT
        elif synth is not None:
            out["answer"] = synth(row["question"], hits)
        elif settings.llm_api_key:
            from app.agent.chat_service import build_context
            from app.agent.llm import synth_llm
            from app.agent.prompts import render as render_prompt
            numbered, _cits = build_context(hits)
            msgs = render_prompt("P6", numbered_chunks=numbered, question=row["question"])
            out["answer"] = synth_llm().call(msgs, node="synthesize", prompt_id="P6",
                                             json_mode=False)

        if judge is not None and out["answer"]:
            msgs = prompt_assets.render("P9", ref_answer=row["ref_answer"],
                                        system_answer=out["answer"])
            raw = judge.call(msgs, node="judge", prompt_id="P9", json_mode=True)
            text = re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", raw.strip()).strip()
            parsed = JudgeOut.model_validate_json(text if text.startswith("{") else "{}")
            out["grade"], out["reason"] = parsed.grade, parsed.reason
        elif out["grade"] == "":
            out["grade"] = "no-key" if not settings.llm_api_key else ""
    except Exception as e:  # noqa: BLE001
        out["error"] = str(e)[:200]
    out["latencyMs"] = int((time.monotonic() - t0) * 1000)
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, choices=list(ABLATIONS))
    parser.add_argument("--dataset", default="simple", choices=["simple", "multi_hop", "all"])
    parser.add_argument("--out", default="results")
    args = parser.parse_args()

    names = ["simple", "multi_hop"] if args.dataset == "all" else [args.dataset]
    rows: list[dict] = []
    for n in names:
        rows.extend(load_dataset(n))
    if not rows:
        print(f"数据集为空: {names}")
        return 1

    apply_config(args.config)
    judge = LlmService(model=settings.effective_judge_model, temperature=0.0,
                       timeout=settings.llm_timeout_fast) if settings.llm_api_key else None

    out_dir = Path(args.out)
    out_dir.mkdir(exist_ok=True)
    csv_path = out_dir / f"{args.config}_{settings.prompt_pack}.csv"
    prompt_pack_check(out_dir, settings.prompt_pack)

    results = []
    for row in rows:
        r = run_one(row, judge)
        results.append(r)
        print(f"[{args.config}] q{row['id']} hit={r['retrievalHit']} grade={r['grade']} "
              f"{r['latencyMs']}ms err={r['error'][:40]}")

    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(results)

    # summary
    total = len(results)
    hits = sum(int(r["retrievalHit"]) for r in results if r["retrievalHit"] != "")
    errors = sum(1 for r in results if r["error"])
    graded = [r for r in results if r["grade"] in ("full", "partial", "wrong")]
    full = sum(1 for r in graded if r["grade"] == "full")
    avg_lat = sum(int(r["latencyMs"]) for r in results) / max(total, 1)
    summary = out_dir / "summary.md"
    with open(summary, "a", encoding="utf-8") as fh:
        fh.write(f"| {args.config} | {settings.prompt_pack} | {total} | "
                 f"{hits / total:.0%} | {full}/{len(graded)} | {errors} | {avg_lat:.0f}ms |\n")
    print(f"done -> {csv_path}")
    return 0


def prompt_pack_check(out_dir: Path, current_pack: str) -> None:
    """历史结果 promptPack 不一致时提示重跑(§11.2.2)。"""
    for old in out_dir.glob("A*.csv"):
        old_pack = old.stem.split("_")[-1]
        if len(old_pack) == 8 and old_pack != current_pack:
            print(f"[warn] 历史 {old.name} 为 pack {old_pack},当前 {current_pack};"
                  f"prompt 已变更,建议重跑(--force 跳过本检查)")
            return


if __name__ == "__main__":
    sys.exit(main())
