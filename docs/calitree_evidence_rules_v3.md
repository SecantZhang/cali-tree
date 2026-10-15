# Corrected three-label evidence calibration

`EvidenceRuleCalibrator` in `critical/core/calibration/evidence_rules_v3.py` is the
corrected experimental calibration layer. The canonical fulfillment optimizer
remains separate. Historical v1/v2 classes and policies retain their original
contracts for exact replay.

The earlier v2 learner could only learn Partial/Yes, froze preassigned No labels,
and abstained on any unknown relevant fact. V3 learns all three labels and has no
immutable label guards. Target correspondence and source meaning are categorical
inputs. Worst and best core fulfillment distinguish no core progress from a
mixture of fulfilled and missing aspects without using numerical condition counts.

## Decision-dependent uncertainty

Unknown observations are represented by feasible lower/upper feature values.
They are never replaced by failure, a guessed known state, or the human target.
Under a globally monotone policy, the lowest/highest evidence completions bound
every possible outcome. The layer returns a label only when those endpoints
produce the same label. Otherwise it returns unresolved.

Thus unknown collateral loss need not block a decision based solely on core
fulfillment. Unknown core fulfillment still blocks a decision when its possible
values cross a learned label boundary. Known unobservable visibility is recorded
as low observability; unknown fulfillment remains an independent interval.

## Reusable rule restrictions

- Tree depth at most two, three split nodes, at least two distinct source cases
  guaranteed to reach each fitted leaf. Ambiguous routing does not invent support.
- Predicates use only target match, source integrity, minimum/maximum core
  fulfillment, minimum constraint fulfillment, collateral continuity and visibility.
- No case IDs, raw instruction predicates, object names, evidence-text vocabulary,
  editing-model/task labels, or exact condition counts.
- All three labels may be learned. Improving known evidence cannot lower the
  label across 972 feasible categorical summaries. Fully fulfilled, matched and
  source-preserved evidence retains Yes at the best-evidence endpoint.
- Exact search maximizes local correct labels, including unresolved cases in the
  denominator, then favors fewer split nodes and fewer departures from a fixed
  complete/partial/absent reference policy. No reference label changes evidence.

## Offline same-case fit

```sh
.venv/bin/python -m run.calitree_recalibrate --preflight \
  --output-dir logs/exps/NEW-V3-LOCAL
.venv/bin/python -m run.calitree_recalibrate --fit \
  --output-dir logs/exps/NEW-V3-LOCAL
.venv/bin/python -m run.calitree_recalibrate --replay \
  --output-dir logs/exps/NEW-V3-LOCAL
```

The default input is the exact 36-case benchmark cache. All extraction calls and
flat responses are reused; fitting/replay makes no API calls. The runner freezes
inputs, code and policy grammar, publishes a new immutable versioned policy,
compares with old v2 and flat, and reports changed decisions and unresolved cases.

These are same-case fitting results, not held-out estimates. Rich evidence errors,
conflicting anonymous summaries and bounded tree capacity can still limit accuracy.
The corrected contract makes calibration meaningful; it does not establish
semantic correctness, unseen generalization or repeated-model robustness.
