# Rich label-blind evidence and local reusable rules

This experiment adds generic factual observations to the v1 evidence response:
appearance drift, unrequested entity loss, entity addition/duplication, relation
change, scene replacement, and verification-content visibility. The same fixed
schema and prompt apply to every case. Authorized edits do not count as collateral
changes; cropping/occlusion is observed without prescribing an output label.

The extractor receives only the instruction and SOURCE/EDITED images. It sees no
reference labels, human scores, earlier predictions, case IDs, or optimizer
feedback. Schema design follows earlier error analysis, so this is label-blind
extraction on historically inspected cases, not a blind study design.

The rule learner retains the original limits: depth two, at most three splits,
at least two distinct source cases per learned leaf, fixed No/unresolved guards,
and monotonicity. It adds two categorical predicates: no unrequested collateral
entity/relation changes, and verification content fully visible. Appearance-only
drift is distinguished from structural collateral changes. Unknown relevant facts
remain unresolved; they are not fitted to the target label.

No rule can inspect raw text, objects, case IDs, task labels, exact instructions,
or condition counts. Exhaustive search checks monotonicity over 162 anonymous
evidence summaries using adjacent improvement edges. The same twelve labels are
used for fitting and scoring; no held-out or repeat-robustness claim is made.

## Run

```sh
.venv/bin/python -m run.calitree_rich_local_calibration --preflight \
  --output-dir logs/exps/NEW-RICH-LOCAL-RUN
.venv/bin/python -u -m run.calitree_rich_local_calibration --live \
  --output-dir logs/exps/NEW-RICH-LOCAL-RUN
.venv/bin/python -m run.calitree_rich_local_calibration --replay \
  --output-dir logs/exps/NEW-RICH-LOCAL-RUN
```

Preflight freezes the schema/prompt, rule grammar, source snapshot, case/image
hashes, and prior results. There are at most twelve new image calls, one per case,
with four workers and GPT-6.1 Sol high at the same SOURCE-first presentation. No
retries, reverse presentations, voting, or additional reviewer models are used.

The report compares:

1. Original cached v1 local fit (10/12).
2. The old frozen policy applied to fresh base fields.
3. The old rule grammar refitted to fresh base fields.
4. The richer rule grammar fitted to the same fresh response's richer fields.

The last two arms share the exact same response and differ in allowed features.
The fresh-base controls help separate observation changes from richer-rule
effects. All post-extraction fitting and prediction are offline. The original
caches, earlier policies and default optimizer remain unchanged.
