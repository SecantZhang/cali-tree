# Matched 36-case flat versus frozen CaliTree comparison

This runner benchmarks the latest experimental pipeline from the current study:
rich label-blind evidence v2 followed by its constrained rule policy, frozen after
fitting the original twelve cases. It does not run the separate canonical
weighted-fulfillment leaf optimizer or a merged hierarchy.

The evaluation sample has twelve No, twelve Partial and twelve Yes references,
all using the AURORA editing model's outputs. Cases come from official seed-42
test tasks, have unique source-pixel groups, and exclude the original twelve,
earlier fitting sources, reserved fifty-case holdout and separate calibration
thirty-six. Category spreading and fixed hash tie-breaking select the sample
without model predictions. Historically queried project cases may remain.

Both arms use GPT-6.1 Sol/high, no temperature, one SOURCE-first image presentation,
one model response and one HTTP attempt per case. The original flat prompt and
rich prompt/schema are unchanged. The rich policy is restored from its immutable
registry artifact; no evaluation labels enter fitting or inference. Human classes
remain aggregate-mean classes with 0.5/1.5 cutoffs, not majority votes.

There are at most 72 calls, processed with four workers. Arm order alternates by
case; each arm/case has its own durable one-attempt ledger. Interrupted/failed
slots cannot be silently resampled. Failures and unresolved cases remain in the
36-case accuracy denominator. The report includes per-class recall, confusion,
coverage, paired improvements/regressions, uncertainty diagnostics, all case
evidence, and per-arm token usage.

```sh
.venv/bin/python -m run.calitree_benchmark36 --preflight \
  --output-dir logs/exps/NEW-BENCHMARK36
.venv/bin/python -u -m run.calitree_benchmark36 --live \
  --output-dir logs/exps/NEW-BENCHMARK36
.venv/bin/python -m run.calitree_benchmark36 --replay \
  --output-dir logs/exps/NEW-BENCHMARK36
```

Preflight freezes cases, image hashes, code, prompt/schema, policy and existing
fit-manifest hashes before calls. Replay reproduces all saved predictions and
metrics without new calls. The result tests transfer from the listed fitting
sources; it differs from the previous 10/12 local fitting score. Single draws do
not establish repeat robustness, and 36 cases remain a small diagnostic.
