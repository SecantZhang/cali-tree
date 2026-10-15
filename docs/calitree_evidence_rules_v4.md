# Class-balanced evidence-rule optimization

The v3 learner allowed all three labels but optimized total correct cases. On the
balanced 36-case fit it selected a No/Yes-only policy with 22 matches and zero
Partial recall. Balanced accuracy does not fix this on a class-balanced batch:
it is identical to ordinary accuracy.

V4 changes only the selection objective and class-coverage eligibility. It reuses
the same rich observations, seven anonymous features, eleven categorical
predicates, depth-two/three-split/minimum-two-source limits, monotonicity and
decision-dependent uncertainty. V1/v2/v3 code and saved artifacts remain unchanged.

## Objective

1. Require at least two correctly recognized distinct fitting sources for each
   of No, Partial and Yes. Predicting a class without any correct matches does not
   qualify. If no candidate qualifies, fitting fails explicitly rather than
   returning a collapsed fallback.
2. Maximize macro-F1: the equal average of the three class F1 values.
3. Break ties by worst-class recall, total correct, fewer split nodes, fewer
   departures from the fixed reference policy, then deterministic enumeration.

F1 for a class is `2*true_positive / (reference_count + predicted_count)`.
Unresolved cases remain false negatives for their reference class; they are not
dropped or assigned guessed labels. Exact rational scores determine selection.
The coverage requirement is about fitting data, not a guarantee on unseen cases.

This objective may sacrifice a small number of correct labels to avoid abandoning
a class. The report always shows overall accuracy, macro-F1, each class recall
and resolution coverage so the tradeoff is visible.

## Offline same-36 fit

```sh
.venv/bin/python -m run.calitree_recalibrate_balanced --preflight \
  --output-dir logs/exps/NEW-V4-LOCAL
.venv/bin/python -m run.calitree_recalibrate_balanced --fit \
  --output-dir logs/exps/NEW-V4-LOCAL
.venv/bin/python -m run.calitree_recalibrate_balanced --replay \
  --output-dir logs/exps/NEW-V4-LOCAL
```

The runner pins the original 36-case cache and v3 comparison, publishes a new
immutable v4 policy, and verifies exact refit/replay without API calls. This is
local fitting on those same labels; it does not measure held-out accuracy,
repeated-model robustness or semantic correctness. Anonymous evidence conflicts
and shallow-tree limitations remain.
