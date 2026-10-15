# Constrained local evidence calibration

This mode fits and scores the **same twelve cached evidence records**. It answers
whether a small shared evidence policy can reproduce those human reference labels.
Its result is local fitting accuracy, not held-out calibration or repeat robustness.
No image/model calls or evidence re-optimization occur.

## Executable rule grammar

The learner subclasses `Calibrator` and searches every tree in a fixed grammar:

- At most two learned levels, three split nodes, and four leaves.
- Each fitted leaf must cover at least two distinct unguarded source cases.
- Allowed predicates: source preserved, every core has progress, every core
  complete, every constraint has progress, every constraint complete.
- These predicates use only source-integrity state and worst core/constraint
  fulfillment state. No constraint means there is no unmet constraint.
- Learned leaves return Partial or Yes. Decisive fixed-policy No is protected.
  Unknown evidence is kept unresolved rather than inferred from its human label.
- On all 18 possible anonymous known-evidence summaries, improving fulfillment
  or source integrity cannot lower the label. Fully complete, source-preserved
  evidence must remain Yes.

No predicate can use raw instructions, source IDs, object names, evidence words,
editing-model identity, task categories, numerical condition counts, or learned
text features. IDs and source groups appear only in reporting/provenance and to
enforce distinct-source support. Renaming entities/evidence, reordering conditions,
duplicating checks, or adding fully satisfied constraints cannot change the
anonymous summary.

Among supported monotone trees, exact search maximizes fitting accuracy, then
prefers fewer splits and fewer departures from the original complete-only policy
over the finite evidence domain. Remaining ties use a fixed enumeration order.
This is bounded empirical fitting, not semantic proof that a rule is reusable.

## Run

```sh
.venv/bin/python -m run.calitree_local_calibration --preflight \
  --output-dir logs/exps/NEW-LOCAL-RULE-RUN
.venv/bin/python -m run.calitree_local_calibration --fit \
  --output-dir logs/exps/NEW-LOCAL-RULE-RUN
.venv/bin/python -m run.calitree_local_calibration --replay \
  --output-dir logs/exps/NEW-LOCAL-RULE-RUN
```

The default cache is `logs/exps/261013-single-call-evidence-balanced12-v1`.
Preflight pins code, caches, reference labels, predicates and complexity limits.
Fit publishes the policy to a content-versioned immutable registry. Replay
repeats exact fitting, checks the artifact and reproduces the same predictions.

Reports compare local fit with the saved flat and fixed-policy scores. They also
show cases with identical anonymous evidence but conflicting labels, giving an
optimistic upper bound before additional support/monotonicity constraints.

A fitted rule may be too permissive despite a good local score. For example,
ignoring incomplete core conditions when source integrity is preserved may fit a
batch without accurately expressing semantic completion. The restrictions prevent
identity lookup and isolated exceptions; they do not establish real-world
generalization or visual correctness.
