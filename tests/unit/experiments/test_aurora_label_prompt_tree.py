from run.aurora_label_prompt_tree import aggregate_label_support, compile_label_support_leaf


def _leaf(label, valid=True):
    return {"label": label, "valid": valid}


def test_each_leaf_contains_only_one_candidate_boundary():
    spec = {
        "label_boundaries": {
            "no": ["requested change is absent"],
            "partial": ["requested change is incomplete"],
            "yes": ["requested change is complete"],
        },
        "tie_breaks": ["choose partial for an incomplete edit", "choose no when absent"],
    }
    prompt = compile_label_support_leaf(spec, "partial")
    assert "category is PARTIAL" in prompt
    assert "requested change is incomplete" in prompt
    assert "requested change is absent" not in prompt
    assert "requested change is complete" not in prompt


def test_unique_support_winner_is_selected():
    result = aggregate_label_support({
        "no": _leaf("no"), "partial": _leaf("partial"), "yes": _leaf("yes")
    })
    assert result["valid"] is True
    assert result["label"] == "yes"
    assert result["support_scores"] == {"no": 0, "partial": 1, "yes": 2}


def test_tied_support_resolves_to_ordinal_middle():
    result = aggregate_label_support({
        "no": _leaf("yes"), "partial": _leaf("no"), "yes": _leaf("yes")
    })
    assert result["label"] == "partial"


def test_invalid_support_leaf_invalidates_tree():
    result = aggregate_label_support({
        "no": _leaf("yes"), "partial": _leaf("", False), "yes": _leaf("no")
    })
    assert result["valid"] is False
