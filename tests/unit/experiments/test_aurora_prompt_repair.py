import argparse
import json
from pathlib import Path

import pytest

from run.aurora_prompt_repair import DEFAULT_PROMPT_PATH, Experiment, LiveJudge
from vejudge.checkpoint import CheckpointStore
from vejudge.lm_engine import openai_compat
from vejudge.logging.llm_history import LLMHistoryWriter
from vejudge.experiments.aurora_prompt_repair import (
    LABELS,
    baseline_summary,
    build_balanced_sample,
    candidate_rank,
    classification_metrics,
    lint_candidate,
    repair_reason,
    robustness_stats,
    select_anchors,
)


def _dataset():
    samples = {}
    labels = {}
    models = [f"model-{index}" for index in range(5)]
    tasks = ["ag", "clevr", "emu", "epic", "kubric", "magicbrush", "something", "whatsup"]
    for task_index in range(400):
        task_uid = f"task-{task_index:03d}"
        for model_index, model in enumerate(models):
            item_id = f"{task_uid}::{model}"
            ordinal = (task_index + model_index) % 3
            label = LABELS[ordinal]
            samples[item_id] = {
                "item_id": item_id,
                "task_uid": task_uid,
                "task": tasks[task_index % len(tasks)],
                "model": model,
                "split": "test",
                "input": {
                    "instruction": f"Edit request {task_index}",
                    "source_image_path": f"/source/{task_index}.png",
                },
                "output": {"edited_image_path": f"/edited/{item_id}.png"},
            }
            labels[item_id] = {
                "human_score": float(ordinal),
                "target_score": ordinal,
                "target_label": label,
            }
    return samples, labels


def _prediction(label, valid=True):
    return {"label": label if valid else "", "rationale": "evidence", "valid": valid}


def test_balanced_sample_is_deterministic_unique_and_task_disjoint():
    samples, labels = _dataset()
    first = build_balanced_sample(samples, labels, size=100, seed=44)
    second = build_balanced_sample(
        dict(reversed(list(samples.items()))),
        dict(reversed(list(labels.items()))),
        size=100,
        seed=44,
    )
    assert [row["item_id"] for row in first["cases"]] == [
        row["item_id"] for row in second["cases"]
    ]
    assert first["quotas"] == {"no": 34, "partial": 33, "yes": 33}
    assert len({row["task_uid"] for row in first["cases"]}) == 100
    assert first["counts"]["clean_holdout"]["total"] == 1500
    assert first["counts"]["clean_holdout"]["tasks"] == 300
    assert set(first["selected_task_uids"]).isdisjoint(
        row["task_uid"] for row in first["clean_holdout"]
    )
    model_counts = first["counts"]["sample"]["models"].values()
    assert max(model_counts) - min(model_counts) <= 1


def test_robustness_counts_invalid_as_a_miss_and_reports_wilson_interval():
    rows = [_prediction("partial") for _ in range(7)]
    rows += [_prediction("no"), _prediction("yes"), _prediction("", valid=False)]
    stats = robustness_stats(rows, "partial", required=7)
    assert stats["robust"] is True
    assert stats["target_hits"] == 7
    assert stats["label_distribution"] == {
        "no": 1,
        "partial": 7,
        "yes": 1,
        "invalid": 1,
    }
    assert stats["wilson_95"][0] == pytest.approx(0.396778, rel=1e-4)


def test_metrics_cover_confusion_ordinal_kappa_and_repair_union():
    rows = [
        {
            "target_label": "no",
            "initial": _prediction("no"),
            "robustness": {"robust": True},
        },
        {
            "target_label": "partial",
            "initial": _prediction("yes"),
            "robustness": {"robust": False},
        },
        {
            "target_label": "yes",
            "initial": _prediction("yes"),
            "robustness": {"robust": False},
        },
    ]
    metrics = classification_metrics(rows)
    assert metrics["accuracy"] == pytest.approx(2 / 3)
    assert metrics["ordinal_mae_0_2"] == pytest.approx(1 / 3)
    assert metrics["quadratic_weighted_kappa"] is not None
    assert repair_reason(rows[0]) is None
    assert repair_reason(rows[1]) == "initial_error_and_unstable"
    assert repair_reason(rows[2]) == "unstable_only"
    summary = baseline_summary(rows)
    assert summary["repair_pool_size"] == 2
    assert summary["robust_count"] == 1


def test_anchor_selection_requires_two_robust_correct_cases_per_label():
    rows = []
    for label_index, label in enumerate(LABELS):
        for index in range(3):
            rows.append({
                "item_id": f"{label}-{index}",
                "task_uid": f"task-{label}-{index}",
                "target_label": label,
                "human_score": label_index + (0.1 * index),
                "initial": _prediction(label),
                "robustness": {"robust": True, "target_hits": 10 - index, "modal_share": 1.0},
            })
    anchors = select_anchors(rows, seed=44)
    assert len(anchors) == 6
    assert {label: sum(row["target_label"] == label for row in anchors) for label in LABELS} == {
        "no": 2,
        "partial": 2,
        "yes": 2,
    }
    with pytest.raises(ValueError, match="anchor preflight failed"):
        select_anchors([row for row in rows if row["item_id"] != "yes-1" and row["item_id"] != "yes-2"])


def test_anchor_selection_can_use_disclosed_best_available_fallback_and_exclusion():
    rows = []
    for label_index, label in enumerate(LABELS):
        for index, hits in enumerate((10, 6, 4)):
            rows.append({
                "item_id": f"{label}-{index}",
                "task_uid": f"task-{label}-{index}",
                "target_label": label,
                "human_score": float(label_index),
                "initial": _prediction(label),
                "robustness": {
                    "robust": hits >= 7,
                    "target_hits": hits,
                    "modal_share": hits / 10,
                },
            })
    anchors = select_anchors(rows, allow_fallback=True)
    partial = [row for row in anchors if row["target_label"] == "partial"]
    assert [row["anchor_selection"]["tier"] for row in partial] == [
        "robust", "best_available_nonrobust"
    ]
    assert [row["anchor_selection"]["baseline_target_hits"] for row in partial] == [10, 6]

    substituted = select_anchors(
        rows,
        allow_fallback=True,
        exclude_item_ids={partial[1]["item_id"]},
    )
    assert partial[1]["item_id"] not in {row["item_id"] for row in substituted}
    replacement = [row for row in substituted if row["target_label"] == "partial"][1]
    assert replacement["anchor_selection"]["baseline_target_hits"] == 4


def test_prompt_lint_blocks_contract_breakage_and_target_leakage():
    focal = {
        "item_id": "task-1::model-x",
        "task_uid": "task-1",
        "model": "model-x",
        "instruction": "Make the car bright purple",
        "target_label": "partial",
    }
    valid = (
        "Judge semantic consistency. Labels: no, partial, yes. "
        'Return {"label":"no|partial|yes","rationale":"evidence"}.'
    )
    assert lint_candidate(valid, focal)["valid"] is True
    leaked = valid + " Make the car bright purple. This case should be labeled partial."
    result = lint_candidate(leaked, focal)
    assert result["valid"] is False
    assert "copies_focal_instruction" in result["errors"]
    assert "direct_target_answer" in result["errors"]


def test_candidate_rank_prefers_hits_then_anchors_then_screen_then_brevity():
    assert candidate_rank(target_hits=8, anchor_correct=0, screen_correct=False, prompt="x" * 100) > candidate_rank(
        target_hits=7, anchor_correct=6, screen_correct=True, prompt="x"
    )


def test_live_judge_repeat_ids_are_fresh_but_same_id_resumes(monkeypatch, tmp_path):
    calls = []

    class _Creds:
        endpoints = ["https://example.invalid"]
        token = "secret"

    def fake_completion(**kwargs):
        calls.append(kwargs)
        return openai_compat.ChatResult(
            content='{"label":"yes","rationale":"visible"}',
            prompt_tokens=10,
            completion_tokens=3,
            total_tokens=13,
            endpoint_host="example.invalid",
            latency_s=0.2,
            model="gpt-5.4-mini-2026-03-17",
        )

    monkeypatch.setattr("run.aurora_prompt_repair.load_creds", lambda: _Creds())
    monkeypatch.setattr(openai_compat, "chat_completion", fake_completion)
    source = tmp_path / "source.png"
    edited = tmp_path / "edited.png"
    source.write_bytes(b"source")
    edited.write_bytes(b"edited")
    case = {
        "item_id": "item",
        "instruction": "Add a hat",
        "source_image_path": str(source),
        "edited_image_path": str(edited),
    }
    judge = LiveJudge(
        model="gpt-5.4-mini",
        checkpoint=CheckpointStore(tmp_path / "checkpoint.jsonl"),
        history=LLMHistoryWriter(tmp_path / "history.jsonl"),
        max_tokens=100,
        timeout=10,
    )
    first = judge.judge(case, "rubric", temperature=0.3, call_id="repeat:00")
    second = judge.judge(case, "rubric", temperature=0.3, call_id="repeat:01")
    resumed = judge.judge(case, "rubric", temperature=0.3, call_id="repeat:00")
    assert len(calls) == 2
    assert first["model"] == "gpt-5.4-mini-2026-03-17"
    assert second["checkpoint_hit"] is False
    assert resumed["checkpoint_hit"] is True
    assert candidate_rank(target_hits=8, anchor_correct=6, screen_correct=True, prompt="short") > candidate_rank(
        target_hits=8, anchor_correct=6, screen_correct=True, prompt="a much longer prompt"
    )


class _Proposer:
    def __init__(self):
        self.calls = 0

    def propose(self, **kwargs):
        self.calls += 1
        return kwargs["prompt"] + "\nUse visible evidence consistently.", {"usage": [], "feedback": kwargs["feedback"]}


class _Judge:
    def __init__(self, *, regress_anchor=False, always_wrong=False, fail_if_called=False):
        self.regress_anchor = regress_anchor
        self.always_wrong = always_wrong
        self.fail_if_called = fail_if_called
        self.calls = []

    def judge(self, case, prompt, *, temperature, call_id):
        if self.fail_if_called:
            raise AssertionError("resume made a duplicate call")
        self.calls.append(call_id)
        target = case["target_label"]
        if self.always_wrong:
            return _prediction("no" if target != "no" else "yes")
        if ":anchor:" in call_id and self.regress_anchor and call_id.endswith("yes-anchor"):
            return _prediction("no")
        return _prediction(target)


def _args(tmp_path, max_rounds=2):
    return argparse.Namespace(
        prompt_path=DEFAULT_PROMPT_PATH,
        model="gpt-5.4-mini",
        max_tokens=1024,
        optimizer_max_tokens=4096,
        timeout=120,
        methods=["textgrad"],
        gepa_python=Path("unused"),
        repeats=10,
        repeat_temperature=0.3,
        robust_min_correct=7,
        max_rounds=max_rounds,
        seed=44,
        concurrency=1,
        input_cost_per_million=0.75,
        output_cost_per_million=4.5,
        focal_only=False,
    )


def _case_and_baseline():
    case = {
        "item_id": "focal-item",
        "task_uid": "focal-task",
        "task": "magicbrush",
        "model": "editor-x",
        "instruction": "Turn the cup blue",
        "human_score": 1.0,
        "target_label": "partial",
        "source_image_path": "/source.png",
        "edited_image_path": "/edited.png",
    }
    baseline = {
        **case,
        "initial": _prediction("no"),
        "robustness": {
            "robust": False,
            "target_hits": 0,
            "n": 10,
            "label_distribution": {"no": 10, "partial": 0, "yes": 0, "invalid": 0},
        },
    }
    anchors = []
    for label in LABELS:
        for index in range(2):
            anchors.append({
                **case,
                "item_id": f"{label}-anchor-{index}",
                "task_uid": f"{label}-anchor-task-{index}",
                "target_label": label,
            })
    # Makes the regression fake easy to target while retaining six anchors.
    anchors[-1]["item_id"] = "yes-anchor"
    return case, baseline, anchors


def test_repair_accepts_after_screen_repeats_and_all_anchors(tmp_path):
    experiment = Experiment(_args(tmp_path), tmp_path / "run")
    try:
        experiment.judge = _Judge()
        experiment.textgrad = _Proposer()
        case, baseline, anchors = _case_and_baseline()
        trace = experiment._repair_track(case, baseline, anchors, "textgrad")
        assert trace["accepted"] is True
        assert trace["stop_reason"] == "accepted_robust_with_anchors"
        assert len(trace["rounds"]) == 1
        assert trace["rounds"][0]["robustness"]["target_hits"] == 10
        assert sum(row["correct"] for row in trace["rounds"][0]["anchors"]) == 6
        (experiment.run_dir / "baseline_predictions.jsonl").write_text(
            json.dumps(baseline) + "\n", encoding="utf-8"
        )
        (experiment.run_dir / "repair_traces.jsonl").write_text(
            json.dumps(trace) + "\n", encoding="utf-8"
        )
        summary = experiment.report()
        assert summary["repair"]["textgrad"]["accepted"] == 1
        assert (experiment.run_dir / "summary.json").is_file()
        assert (experiment.run_dir / "summary.csv").is_file()
        assert list((experiment.run_dir / "case_reports").glob("*.md"))
    finally:
        experiment.close()


def test_repair_exhausts_rounds_on_wrong_screen(tmp_path):
    experiment = Experiment(_args(tmp_path, max_rounds=2), tmp_path / "run")
    try:
        experiment.judge = _Judge(always_wrong=True)
        experiment.textgrad = _Proposer()
        case, baseline, anchors = _case_and_baseline()
        trace = experiment._repair_track(case, baseline, anchors, "textgrad")
        assert trace["accepted"] is False
        assert trace["stop_reason"] == "max_rounds_exhausted"
        assert len(trace["rounds"]) == 2
        assert all(not row["repeats"] for row in trace["rounds"])
    finally:
        experiment.close()


def test_focal_only_accepts_majority_without_calling_anchors(tmp_path):
    args = _args(tmp_path, max_rounds=2)
    args.focal_only = True
    args.robust_min_correct = 6
    experiment = Experiment(args, tmp_path / "run")
    try:
        experiment.judge = _Judge(regress_anchor=True)
        experiment.textgrad = _Proposer()
        case, baseline, anchors = _case_and_baseline()
        trace = experiment._repair_track(case, baseline, anchors, "textgrad")
        assert trace["accepted"] is True
        assert trace["acceptance_mode"] == "focal_only"
        assert trace["stop_reason"] == "accepted_focal_robust"
        assert len(trace["rounds"]) == 1
        assert trace["rounds"][0]["anchors"] == []
        assert all(":anchor:" not in call for call in experiment.judge.calls)
        assert "Anchor regressions" not in trace["rounds"][0]["feedback"]
    finally:
        experiment.close()


def test_repair_rejects_anchor_regression_and_resumes_without_calls(tmp_path):
    args = _args(tmp_path, max_rounds=2)
    case, baseline, anchors = _case_and_baseline()
    run_dir = tmp_path / "run"
    first = Experiment(args, run_dir)
    try:
        first.judge = _Judge(regress_anchor=True)
        first.textgrad = _Proposer()
        trace = first._repair_track(case, baseline, anchors, "textgrad")
        assert trace["accepted"] is False
        assert len(trace["rounds"]) == 2
        assert all(sum(anchor["correct"] for anchor in row["anchors"]) == 5 for row in trace["rounds"])
    finally:
        first.close()

    resumed = Experiment(args, run_dir)
    try:
        resumed.judge = _Judge(fail_if_called=True)
        resumed.textgrad = _Proposer()
        restored = resumed._repair_track(case, baseline, anchors, "textgrad")
        assert restored["accepted"] is False
        assert len(restored["rounds"]) == 2
        assert resumed.textgrad.calls == 0
    finally:
        resumed.close()
