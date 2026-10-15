# Fast-model comparison on the fixed AURORA groups

The completed run is `logs/exps/261014-fast-models-four-groups-v2/`.
Its `report.md` contains accuracy, macro-F1, all-class recall, coverage,
per-group results, common-resolved comparisons, latency, costs and caveats.

The exact previous four groups (48 source-distinct cases, four references per
class in each group) were evaluated with GPT-6 Luna and GPT-5.4 mini. Both used
reasoning disabled, temperature 0, the existing flat and semantic-v5 prompts,
one source-first presentation per arm and case, one HTTP attempt, and eight
shared workers. Each model produced its own new observations; strong-model
evidence was never substituted. The v6 rule budget and all-class floor stayed
unchanged. Each local policy was fitted and scored on its same twelve cases.

| Model | Flat | Strict shared local | Shared after literal quote normalization | Clustered after normalization |
|---|---:|---:|---:|---:|
| GPT-6 Luna | 31/48 | 39/48 | 39/48 | 39/48 |
| GPT-5.4 mini | 24/48 | 23/48 | 34/48 | 37/48 |

Luna shared counts by group: 8/12, 11/12, 10/12, 10/12. Mini's strict G1 fit
was infeasible because only one Partial record passed evidence validation;
the required two-correct-source floor could not be met. That group's twelve
cases remain unresolved in the 23/48 pipeline result.

Seven mini responses failed literal instruction-span validation. The opt-in
post-hoc diagnostic `normalize_literal_quotes` fixes six by removing only one
pair of decorative outer quotes, and only when the inner text occurs exactly
in the instruction. It never modifies any visual facts or grades, uses no
reference labels, and makes no model calls. An ellipsis-based paraphrase remains
invalid. Raw responses and the strict protocol results remain preserved.

The ten SSL failures across all arms remain denominator losses. There were no
retries, substitutions, resampling, or label changes. A frozen Sol-policy control
is also reported separately from local refitting. These are local fit results,
not held-out model comparisons or repeat-robustness measurements.

Replay with zero API calls:

```bash
.venv/bin/python -m run.calitree_small_models --replay --models luna mini --output-dir logs/exps/261014-fast-models-four-groups-v2
.venv/bin/python -m run.calitree_small_models_calibration --output-dir logs/exps/261014-fast-models-four-groups-v2
.venv/bin/python -m run.report_calitree_small_models --output-dir logs/exps/261014-fast-models-four-groups-v2
```

New collection directories require `--preflight`, then explicit `--live`.
`--models` defaults to Luna; adding another model must be authorized. Existing
manifests reject model-list changes. The collection manifest seals the exact
models, cases, prompts/schema, source and image hashes. All learned policies,
normalization receipts, raw ledgers and source snapshots are retained.
