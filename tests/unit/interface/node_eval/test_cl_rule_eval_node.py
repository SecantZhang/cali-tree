"""Rule Comparison node: it re-surfaces an upstream Rule/Tree node's judge_rule report as
a standalone comparison, and derives the held-out (LOO) verdict from it. Pure display — no
gateway calls, no dry-run/--live gating."""

from vejudge.interface.node_eval.cl_rule_eval_node import ClRuleEvalNodeExecutor


_UNSET = object()


def _judge_rule(*, insample=_UNSET, loo=_UNSET, **extra):
    jr = {
        "n_items": 13,
        "metric": "M5",
        "insample_mae": {"base": 1.83, "bias": 0.46, "score_linear": 0.35,
                         "linear": 0.27, "tree": 0.27}
        if insample is _UNSET else insample,
        "loo_mae": {"base": 1.83, "bias": 0.50, "score_linear": 0.40,
                     "linear": 0.37, "tree": 0.31}
        if loo is _UNSET else loo,
        "tree_rule": "|--- q2 <= 0.5\n|   |--- value: [2.0]",
        "tree": {"leaf": False, "feature": "q2", "threshold": 0.5, "samples": 13, "value": 3.0,
                 "left": {"leaf": True, "samples": 8, "value": 2.0},
                 "right": {"leaf": True, "samples": 5, "value": 4.0}},
        "bank": [{"question": "Does the judge over-penalize a flaw?", "raises_score_when": "no"}],
        "evaluation_mode": "frozen_holdout",
        "n_validation_items": 6,
        "per_item_errors": {
            f"item-{i}": {"bias": 0.50, "score_linear": 0.40,
                           "linear": 0.37, "tree": 0.30}
            for i in range(6)
        },
    }
    jr.update(extra)
    return jr


def test_missing_judge_rule_is_a_node_error(make_ctx):
    result = ClRuleEvalNodeExecutor().run(make_ctx(inputs={}))
    assert result.status == "error"
    assert "judge_rule" in result.error


def test_comparison_rows_include_score_only_and_rule_comparators(make_ctx):
    ctx = make_ctx(inputs={"judge_rule": _judge_rule()})
    result = ClRuleEvalNodeExecutor().run(ctx)
    assert result.status == "done"
    rows = result.outputs["comparison"]["rows"]
    assert [r["key"] for r in rows] == ["base", "bias", "score_linear", "linear", "tree"]
    tree_row = next(r for r in rows if r["key"] == "tree")
    assert tree_row["insample"] == 0.27
    assert tree_row["loo"] == 0.31  # held-out column carried through verbatim
    # The structured tree (for the UI diagram) passes through untouched.
    comp = result.outputs["comparison"]
    assert comp["tree"]["feature"] == "q2"
    assert comp["tree"]["right"]["value"] == 4.0


def test_verdict_says_rules_help_when_a_rule_model_beats_bias_held_out(make_ctx):
    # tree LOO 0.41 < bias LOO 0.50 → rules earn their keep.
    ctx = make_ctx(inputs={"judge_rule": _judge_rule()})
    result = ClRuleEvalNodeExecutor().run(ctx)
    comp = result.outputs["comparison"]
    assert comp["beats_bias"] is True
    assert result.meta["beats_bias"] is True
    assert "tree beats a plain bias" in comp["verdict"]
    assert comp["score_calibration_beats_bias"] is True
    assert comp["rules_beat_score_linear"] is True


def test_semantic_tree_can_earn_verdict_when_score_linear_alone_does_not(make_ctx):
    loo = {"base": 1.8, "bias": 1.18, "score_linear": 1.11, "semantic": 1.06}
    errors = {
        f"item-{i}": {"bias": 1.18, "score_linear": 1.11, "semantic": 1.06}
        for i in range(7)
    }
    comp = ClRuleEvalNodeExecutor().run(make_ctx(inputs={
        "judge_rule": _judge_rule(loo=loo, per_item_errors=errors, n_validation_items=7),
    })).outputs["comparison"]
    assert comp["beats_bias"] is True
    assert comp["best_calibration_beats_bias"] is True
    assert "semantic beats a plain bias" in comp["verdict"]


def test_verdict_says_rules_do_not_help_when_bias_wins_held_out(make_ctx):
    # Both rule models are worse held-out than the bias term → the bias captures it all.
    loo = {"base": 1.83, "bias": 0.40, "linear": 0.55, "tree": 0.52}
    ctx = make_ctx(inputs={"judge_rule": _judge_rule(
        loo=loo,
        per_item_errors={
            f"item-{i}": {"bias": 0.40, "linear": 0.55, "tree": 0.52}
            for i in range(6)
        },
    )})
    result = ClRuleEvalNodeExecutor().run(ctx)
    comp = result.outputs["comparison"]
    assert comp["beats_bias"] is False
    assert "Indistinguishable" in comp["verdict"]


def test_verdict_handles_missing_loo_gracefully(make_ctx):
    ctx = make_ctx(inputs={"judge_rule": _judge_rule(loo={})})
    result = ClRuleEvalNodeExecutor().run(ctx)
    comp = result.outputs["comparison"]
    assert comp["beats_bias"] is False
    assert "Not enough data" in comp["verdict"]


def test_negligible_tree_gain_is_not_reported_as_an_improvement(make_ctx):
    loo = {"base": 1.76, "bias": 0.9444, "linear": 2.09, "tree": 0.9439}
    errors = {
        f"item-{i}": {"bias": 0.9444, "linear": 2.09, "tree": 0.9439}
        for i in range(6)
    }
    comp = ClRuleEvalNodeExecutor().run(make_ctx(inputs={
        "judge_rule": _judge_rule(loo=loo, per_item_errors=errors),
    })).outputs["comparison"]
    assert comp["beats_bias"] is False
    assert "Indistinguishable from global bias" in comp["verdict"]


def test_writes_report_json_to_run_dir(make_ctx):
    ctx = make_ctx(node_id="rule_eval1", inputs={"judge_rule": _judge_rule()})
    ClRuleEvalNodeExecutor().run(ctx)
    assert (ctx.run.run_dir / "rule_eval_rule_eval1.json").is_file()


def test_makes_no_calls_and_ignores_live_gating(make_ctx):
    # A dry run and a non-allow-live run both succeed — this node never calls the gateway.
    for kw in ({"dry_run": True}, {"dry_run": False, "allow_live": False}):
        ctx = make_ctx(inputs={"judge_rule": _judge_rule()}, **kw)
        assert ClRuleEvalNodeExecutor().run(ctx).status == "done"
