import json
from pathlib import Path

from vejudge.experiments.prompt_repair_report import build_report_payload, write_html_report


def _write_jsonl(path: Path, rows):
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def test_report_contains_every_case_and_prompt_progression(tmp_path):
    run_dir = tmp_path / "experiment"
    run_dir.mkdir()
    source = tmp_path / "source image.png"
    edited = tmp_path / "edited image.png"
    source.write_bytes(b"source")
    edited.write_bytes(b"edited")
    seed = tmp_path / "seed.txt"
    seed.write_text("seed rubric", encoding="utf-8")
    (run_dir / "run_config.json").write_text(
        json.dumps({"model": "judge-model", "prompt_path": str(seed)}), encoding="utf-8"
    )
    baseline = {
        "item_id": "case-1", "task_uid": "task-1", "task": "editing",
        "model": "editor", "instruction": "Add <a hat>", "human_score": 1.0,
        "target_label": "partial", "source_image_path": str(source),
        "edited_image_path": str(edited),
        "initial": {"label": "no", "valid": True, "rationale": "not visible"},
        "repeats": [{"label": "no", "valid": True}],
        "robustness": {"n": 1, "target_hits": 0, "robust": False,
                       "label_distribution": {"no": 1, "partial": 0, "yes": 0, "invalid": 0}},
    }
    _write_jsonl(run_dir / "baseline_predictions.jsonl", [baseline])
    trace = {
        "item_id": "case-1", "method": "textgrad", "accepted": True,
        "stop_reason": "accepted_focal_robust", "rounds": [{
            "round": 1, "candidate_prompt": "improved rubric", "feedback": "move boundary",
            "lint": {"valid": True, "errors": []},
            "screen": {"label": "partial", "valid": True, "rationale": "some evidence"},
            "repeats": [{"label": "partial", "valid": True}],
            "robustness": {"n": 1, "target_hits": 1, "robust": True,
                           "label_distribution": {"no": 0, "partial": 1, "yes": 0, "invalid": 0}},
            "anchors": [], "accepted": True,
        }],
    }
    _write_jsonl(run_dir / "repair_traces.jsonl", [trace])
    (run_dir / "summary.json").write_text(
        json.dumps({"model": "judge-model", "baseline": {"accuracy": 0.0}}), encoding="utf-8"
    )

    payload = build_report_payload(run_dir)
    assert len(payload["cases"]) == 1
    assert payload["seed_prompt"] == "seed rubric"
    assert payload["cases"][0]["source_image_url"].startswith("file://")
    repair = payload["cases"][0]["repairs"][0]
    assert repair["rounds"][0]["candidate_prompt"] == "improved rubric"
    assert "seed rubric" in repair["rounds"][0]["prompt_diff"]
    assert repair["best_prompt"] == "improved rubric"

    output = write_html_report(run_dir)
    html = output.read_text(encoding="utf-8")
    assert "__PROMPT_REPAIR_REPORT_DATA__" not in html
    assert '"item_id":"case-1"' in html
    assert "Add \\u003ca hat\\u003e" in html
    assert "Load run folder" in html


def test_report_requires_baseline_predictions(tmp_path):
    missing = tmp_path / "missing"
    missing.mkdir()
    try:
        build_report_payload(missing)
    except FileNotFoundError as exc:
        assert "baseline_predictions.jsonl" in str(exc)
    else:
        raise AssertionError("missing baseline input should fail")
