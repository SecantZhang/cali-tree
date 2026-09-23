import json

import pytest

from run.aurora_prompt_tree import (
    aggregate_tree,
    combine_requirement_leaves,
    compile_fidelity_leaf,
    compile_requirement_leaf,
    parse_requirements,
)


def _leaf(label, valid=True):
    return {"label": label, "valid": valid}


def test_requirement_parser_requires_core_and_normalizes_ids():
    content = json.dumps({"requirements": [
        {"id": "anything", "text": "add a sphere", "role": "core", "kind": "object"},
        {"id": "duplicate-id", "text": "make it red", "role": "modifier", "kind": "attribute"},
    ]})
    rows = parse_requirements(content, "add a red sphere")
    assert rows == [
        {"id": "r1", "text": "add a sphere", "role": "core", "kind": "object"},
        {"id": "r2", "text": "make it red", "role": "modifier", "kind": "attribute"},
    ]

    with pytest.raises(ValueError, match="core"):
        parse_requirements(json.dumps({"requirements": [
            {"text": "red", "role": "modifier", "kind": "attribute"}
        ]}), "make it red")


@pytest.mark.parametrize(
    "core,modifier,preservation,expected",
    [
        ("yes", "yes", "yes", "yes"),
        ("partial", "yes", "yes", "partial"),
        ("yes", "no", "yes", "partial"),
        ("no", "yes", "yes", "no"),
        ("yes", "yes", "no", "no"),
        ("yes", "yes", "partial", "partial"),
    ],
)
def test_deterministic_tree_aggregation(core, modifier, preservation, expected):
    requirements = [
        {"id": "r1", "text": "core", "role": "core"},
        {"id": "r2", "text": "modifier", "role": "modifier"},
    ]
    result = aggregate_tree(
        requirements, [_leaf(core), _leaf(modifier)], _leaf(preservation)
    )
    assert result["valid"] is True
    assert result["label"] == expected


def test_invalid_leaf_invalidates_tree_prediction():
    requirements = [{"id": "r1", "text": "core", "role": "core"}]
    result = aggregate_tree(requirements, [_leaf("", valid=False)], _leaf("yes"))
    assert result == {"label": "", "valid": False, "reason": "invalid_leaf"}


def test_requirement_leaf_compiles_decomposition_record():
    requirement = {"id": "r1", "text": "add a sphere", "role": "core", "kind": "object"}
    prompt = compile_requirement_leaf(requirement)
    assert "Focused requirement (core, object): add a sphere" in prompt
    assert "strict fidelity-audit" in compile_fidelity_leaf(requirement)


def test_requirement_combines_presence_and_fidelity_conservatively():
    ordinary = {"kind": "relation"}
    outcome = {"kind": "outcome"}
    assert combine_requirement_leaves(ordinary, _leaf("yes"), _leaf("partial"))["label"] == "partial"
    assert combine_requirement_leaves(ordinary, _leaf("yes"), _leaf("no"))["label"] == "partial"
    assert combine_requirement_leaves(ordinary, _leaf("partial"), _leaf("no"))["label"] == "partial"
    assert combine_requirement_leaves(ordinary, _leaf("no"), _leaf("yes"))["label"] == "no"
    assert combine_requirement_leaves(ordinary, _leaf("yes"), _leaf("yes"))["label"] == "yes"
    assert combine_requirement_leaves(outcome, _leaf("yes"), _leaf("no"))["label"] == "no"
