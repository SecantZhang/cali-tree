from run.aurora_atomic_robustness import lint_spec, select_pilot_candidates


SPEC = {
    "objective": "judge semantic satisfaction",
    "evidence_rules": ["use visible evidence"],
    "decision_steps": [{"order": 1, "decision": "check instruction", "outcomes": "route"}],
    "label_boundaries": {"no": ["absent"], "partial": ["incomplete"], "yes": ["complete"]},
    "tie_breaks": ["absence is no"],
    "output_contract": {"format": "json", "labels": ["no", "partial", "yes"]},
}


def _candidate(item_id, method, label, round_index=1):
    return {
        "item_id": item_id,
        "method": method,
        "target_label": label,
        "round": round_index,
    }


def _structured(candidates, robust_ids=()):
    return {
        (row["item_id"], row["method"], row["round"]): {
            "comparison": {"robustness_preserved": row["item_id"] in robust_ids}
        }
        for row in candidates
    }


def test_small_failure_pilot_is_deterministic_and_method_balanced():
    candidates = [
        *[_candidate(f"tg-{index}", "textgrad", "partial") for index in range(5)],
        *[_candidate(f"gepa-no-{index}", "gepa", "no") for index in range(4)],
        *[_candidate(f"gepa-partial-{index}", "gepa", "partial") for index in range(4)],
        _candidate("already-robust", "textgrad", "yes"),
    ]
    structured = _structured(candidates, robust_ids={"already-robust"})

    first = select_pilot_candidates(
        candidates, structured, selection="structured-failures", limit=6, seed=44
    )
    second = select_pilot_candidates(
        candidates, structured, selection="structured-failures", limit=6, seed=44
    )

    assert first == second
    assert len(first) == 6
    assert {row["item_id"] for row in first}.isdisjoint({"already-robust"})
    assert sum(row["method"] == "textgrad" for row in first) == 3
    assert sum(row["method"] == "gepa" for row in first) == 3
    assert {row["target_label"] for row in first if row["method"] == "gepa"} == {
        "no",
        "partial",
    }


def test_unlimited_selection_returns_every_eligible_candidate():
    candidates = [
        _candidate("failed", "gepa", "no"),
        _candidate("robust", "textgrad", "yes"),
    ]
    selected = select_pilot_candidates(
        candidates,
        _structured(candidates, robust_ids={"robust"}),
        selection="structured-failures",
        limit=None,
        seed=44,
    )
    assert [row["item_id"] for row in selected] == ["failed"]


def test_lint_rejects_changes_outside_editable_atomic_slots():
    revised = {**SPEC, "objective": "a changed objective"}
    lint = lint_spec(revised, {}, parent_spec=SPEC)
    assert lint["valid"] is False
    assert "immutable_field_changed:objective" in lint["errors"]
