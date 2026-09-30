"""Execution semantics for automatically generated veto/base/cap policies."""

from dataclasses import asdict
from itertools import product

import pytest

from .generated_policy import parse_policy
from .hard_cases import HARD_SAMPLES
from .two_way import reference_plan


RUBRIC = "Forbidden preservation changes veto.\nNo successful edits means no.\nAll edits succeed means yes.\nMixed edits means partial.\nUncertain preservation caps success at partial."


def staged_policy():
    def expr(fact, value, op="eq"):
        return {"fact": fact, "operator": op, "value": value}
    return {
        "supported_edits": ["color", "position", "count"], "criteria": [],
        "guards": [{"key": "background", "expected": "preserved", "unless_permission": "allow_background_change"}],
        "veto_rules": [{"when": expr("guard.background", "violated"), "label": "no", "source": 1}],
        "decision_rules": [
            {"when": expr("edit_count", 0), "label": "yes", "source": 3},
            {"when": expr("satisfied_count", 0), "label": "no", "source": 2},
            {"when": expr("satisfied_count", {"fact": "edit_count"}), "label": "yes", "source": 3},
        ],
        "caps": [{"when": expr("guard.background", "unknown"), "label": "partial", "source": 5}],
        "default": {"label": "partial", "source": 4},
    }


def rows(conditions, statuses):
    return [{"condition": asdict(c), "status": s} for c, s in zip(conditions, statuses)]


def test_all_edit_status_combinations_keep_failure_below_uncertainty_cap():
    policy = parse_policy(staged_policy(), RUBRIC)
    plan = reference_plan(HARD_SAMPLES["h01"]["instruction"])
    for edits in product(("satisfied", "violated", "unknown"), repeat=3):
        for guard in ("satisfied", "violated", "unknown"):
            label, trace = policy.decide(rows(policy.edits(plan), edits), rows(policy.guards(plan), [guard]), plan)
            if guard == "violated" or "satisfied" not in edits:
                expected = "no"
            elif all(x == "satisfied" for x in edits) and guard == "satisfied":
                expected = "yes"
            else:
                expected = "partial"
            assert label == expected, (edits, guard, trace)


def test_empty_set_uncertainty_and_exemption():
    policy = parse_policy(staged_policy(), RUBRIC)
    plan = reference_plan({**HARD_SAMPLES["h01"]["instruction"], "required_edits": []})
    assert policy.decide([], rows(policy.guards(plan), ["unknown"]), plan)[0] == "partial"
    exempt = reference_plan({**HARD_SAMPLES["h01"]["instruction"], "required_edits": [], "allow_background_change": True})
    label, trace = policy.decide([], [], exempt)
    assert label == "yes"
    assert trace["exempt_guards"] == ["background"]


def test_fixed_rubric_criteria_use_the_same_interpreter():
    value = staged_policy()
    value.update({"supported_edits": ["color", "shape"],
                  "criteria": [{"key": "color", "operator": "equals", "expected": "red"},
                               {"key": "shape", "operator": "equals", "expected": "circular"}],
                  "guards": [], "veto_rules": [], "caps": []})
    policy = parse_policy(value, RUBRIC)
    plan = reference_plan({**HARD_SAMPLES["h01"]["instruction"], "required_edits": []})
    assert [c.key for c in policy.edits(plan)] == ["color", "shape"]
    assert policy.decide(rows(policy.edits(plan), ["satisfied", "violated"]), [], plan)[0] == "partial"


@pytest.mark.parametrize("base,cap,expected", [
    ("no", "partial", "no"), ("no", "yes", "no"),
    ("partial", "yes", "partial"), ("yes", "partial", "partial"),
    ("partial", "no", "no"),
])
def test_caps_are_upper_bounds_not_overrides(base, cap, expected):
    value = staged_policy()
    value["decision_rules"] = []
    value["default"]["label"] = base
    value["caps"][0]["label"] = cap
    policy = parse_policy(value, RUBRIC)
    plan = reference_plan(HARD_SAMPLES["h01"]["instruction"])
    assert policy.decide(rows(policy.edits(plan), ["satisfied"] * 3), rows(policy.guards(plan), ["unknown"]), plan)[0] == expected
