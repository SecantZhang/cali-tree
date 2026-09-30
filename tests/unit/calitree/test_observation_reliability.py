from copy import deepcopy
import json

import pytest

from run.calitree_observation_reliability import freeze_manifest, label_from_statuses, run_pilot, summarize
from .test_casewise_fitting import plan, check, Engine
from .test_decision_sets import images


def inputs(tmp_path):
    evidence, hashes = images(tmp_path)
    return {"sample": {"instruction": "Close curtains", "optimized_prompt": "rubric",
                       "plan": plan(), "feedback_used": False, "criteria_origin": "test",
                       "human_label": "yes", "images": [
                           {"path": evidence[k], "sha256": h} for k, h in zip(evidence, hashes)]}}


def test_repeats_are_fresh_resume_is_not_and_labels_are_isolated(tmp_path):
    rows = inputs(tmp_path)
    out = tmp_path / "run"
    manifest = freeze_manifest(out, rows, model="offline", repeats=3, max_tokens=4096)
    engine = Engine([check("complete"), check("partial"), check("unknown")])
    result = run_pilot(out, manifest, engine)
    assert len(engine.calls) == 3
    for prompt, kwargs in engine.calls:
        payload = json.loads(prompt.split("INPUT_JSON: ")[1])
        assert set(payload) == {"instruction", "condition"}
        assert kwargs["strict_schema"]
    case = result["summary"]["cases"]["sample"]
    assert case["labels"] == ["yes", "partial", "unresolved"]
    assert case["conditions"][0]["known_draws"] == 2
    assert not case["all_conditions_stable_and_known"]
    replay = Engine([])
    assert run_pilot(out, manifest, replay) == result
    assert not replay.calls


def test_malformed_draw_is_recorded_without_repair_or_retry(tmp_path):
    rows = inputs(tmp_path)
    out = tmp_path / "run"
    manifest = freeze_manifest(out, rows, model="offline", repeats=2, max_tokens=4096)
    engine = Engine([{"bad": True}, check("complete")])
    result = run_pilot(out, manifest, engine)
    assert len(engine.calls) == 2
    assert result["summary"]["cases"]["sample"]["labels"] == ["unresolved", "yes"]
    assert not result["draws"]["0/sample"]["valid"]
    assert run_pilot(out, manifest, Engine([])) == result


def test_manifest_freezes_inputs_and_rejects_changed_images_and_review(tmp_path):
    rows = inputs(tmp_path)
    out = tmp_path / "run"
    frozen = freeze_manifest(out, rows)
    assert frozen["model"] == "gpt-6-luna"
    assert frozen["max_calls"] == 3
    assert frozen["completion_budget"] == 3072
    assert freeze_manifest(out, rows) == frozen
    changed = deepcopy(rows)
    changed["sample"]["plan"]["conditions"][0]["complete_when"] = "different"
    with pytest.raises(ValueError, match="Protocol changed"):
        freeze_manifest(out, changed)
    changed = deepcopy(rows)
    changed["sample"]["annotation_review"] = {"status": "uncertain"}
    with pytest.raises(ValueError, match="uncertain"):
        freeze_manifest(out, changed)
    from pathlib import Path
    Path(rows["sample"]["images"][0]["path"]).write_bytes(b"changed")
    with pytest.raises(ValueError, match="image bytes"):
        freeze_manifest(out, rows)


def test_unknown_consistency_is_not_reliability(tmp_path):
    rows = inputs(tmp_path)
    draws = {f"{i}/sample": {"label": "unresolved", "observations": {
        "checks": [{"condition_id": "c1", "status": "unknown"}]}} for i in range(3)}
    result = summarize(rows, draws, 3)
    assert result["stable_known_conditions"] == 0
    assert result["cases"]["sample"]["conditions"][0]["pairwise_status_agreement"] == 1
    assert label_from_statuses(["absent", "unknown"]) == "unresolved"


def test_provider_failure_stops_and_cannot_silently_retry_on_resume(tmp_path):
    class Broken(Engine):
        def generate(self, *args, **kwargs):
            raise RuntimeError("offline failure")
    rows = inputs(tmp_path)
    out = tmp_path / "run"
    manifest = freeze_manifest(out, rows, model="offline", repeats=2, max_tokens=4096)
    result = run_pilot(out, manifest, Broken([]))
    assert result["stop_reason"].startswith("blocked:")
    assert result["usage"]["calls"] == 1
    assert result["usage"]["completion_tokens_or_reserved"] == 4096
    with pytest.raises(ValueError, match="Previous provider"):
        run_pilot(out, manifest, Engine([]))


def test_dry_run_does_not_load_credentials_or_create_engine(tmp_path, monkeypatch):
    import run.calitree_observation_reliability as pilot
    rows = inputs(tmp_path)
    monkeypatch.setattr(pilot, "load_inputs", lambda *a, **k: rows)
    def forbidden(*args, **kwargs):
        raise AssertionError("Dry run must not access provider")
    monkeypatch.setattr(pilot, "load_creds", forbidden)
    monkeypatch.setattr(pilot, "get_engine", forbidden)
    monkeypatch.setattr("sys.argv", ["pilot", "--output-dir", str(tmp_path / "run")])
    pilot.main()
    assert (tmp_path / "run/manifest.json").exists()
    assert not (tmp_path / "run/budget.json").exists()


def test_engine_mismatch_rejected_before_calls(tmp_path):
    rows = inputs(tmp_path)
    out = tmp_path / "run"
    manifest = freeze_manifest(out, rows)
    engine = Engine([])
    with pytest.raises(ValueError, match="Engine differs"):
        run_pilot(out, manifest, engine)
    assert not engine.calls
