# Prepared 80-output AURORA pilot

Completed follow-up: see [the frozen pilot results](calitree_aurora_pilot_results.md). The material below records the original preparation; collection has since completed in the corrected `-run1` directory.

**Preparation record:** The cohort compares the
regular judge with the frozen v27 and v28 gates. Each gate version has three
split-specific expert banks; all six receive the same evidence and share the
same regular-judge response for fallback.

## Cohort and exposure audit

The local catalog contains 2,000 outputs from 400 source–instruction tasks and
five editing models. Decoded source-pixel hashing identifies 394 distinct source
groups. The audit scanned 106,080 historical artifacts in the original checkout
and 17,425 in this worktree, covering experiment logs, historical test caches,
experiment documents and fixtures.

The combined audit found prior references for 392 tasks / 386 source groups.
Only eight tasks have no recorded prior exposure: epic 2, kubric 2, clevr 1,
something 1 and whatsup 2. Consequently, a completely unused 80-output pilot
with two tasks per category is not available locally.

The user explicitly chose the 80-case alternative allowing disclosed older
exposure while excluding recent CaliTree sources. The frozen selection:

- Uses 16 distinct source groups, two tasks in each of eight categories.
- Includes all five editors per task: 80 outputs, ten per category and sixteen
  per editing model.
- Prioritizes all eight tasks with no recorded prior exposure: 40 outputs.
- Includes eight historically referenced tasks: another 40 outputs.
- Excludes all 244 source groups in the recent compiler-v3 study and its declared
  exclusions, including earlier development/reservation sources.
- Selects by category, exposure preference and a fixed seeded hash; human labels
  do not determine which tasks are selected.

The resulting labels are **60 No, 15 Partial, 5 Yes** under the existing half-point
cutoffs on AURORA's mean human score. The small Yes count limits class-specific
conclusions. This is a broader-coverage pilot, not a globally untouched benchmark.

Historical references include inference, evaluation, fixtures and case-specific
reports; they do not necessarily prove a successful paid call for every event.
There were zero parse errors. The scanner also reports unresolved aliases
(7,912 original / 1,962 worktree); their contexts remain in the ledger. Thus
“no exposure found” is scoped to identifiable references in these repository
records, not a guarantee about all possible prior use or model pretraining.

## Frozen execution setting

- Existing GPT-6 Luna identity, reasoning effort `none`, temperature 0.
- Compiler-v3 once per unique instruction: 16 instructions, with at most one
  validator repair each.
- Fresh bound observation and interpretation per output, plus one regular
  judgment per output.
- Six deterministic gate evaluations per output; no additional model call for a
  tree node, expert, gate variant or fallback reuse.
- No fitting, relabeling, threshold changes, retries, replacement cases or
  repeated draws. Single-worker durable collection avoids budget-ledger races.
- Compilation/extraction failures defer to the regular judge. Invalid regular
  responses remain unresolved and count as incorrect; cases are not dropped.

Input metadata and reference labels are in separate files. References are
hash-verified in preflight and used for scoring only after inference; they never
enter model requests. Source and image hashes, six gate artifacts, prompts,
runtime dependencies, request/token budgets and the execution plan are frozen.

## Requests and estimated cost

| Stage | Normal requests | Maximum completion tokens per request |
|---|---:|---:|
| Instruction compilation | 16 | 8,192 |
| Conditional compiler repair | 0 normally, at most 16 | 8,192 |
| Visual observation | 80 | 16,384 |
| Evidence interpretation | 80 | 8,192 |
| Regular judge | 80 | 2,048 |

Normal total: **256 requests**. Hard request ceiling: **272**. Completion-token
ceiling including every compiler repair: **2,392,064**.

The official GPT-6 Luna page, checked October 20, 2026, lists Standard short-context
prices of **$0.10 per million input tokens**, **$0.50 per million output tokens**,
and $0.125 per million cache-write tokens. [Official model pricing](https://developers.openai.com/api/docs/models/gpt-6-luna)

The forecast uses actual prompt/completion usage from earlier runs of the same
pipeline and model; prompt usage already includes image inputs. It does not assume
an undocumented image-token multiplier or free image processing.

| Planning scenario | Input tokens | Output tokens | Estimated USD |
|---|---:|---:|---:|
| Historical per-stage mean | 689,554 | 125,720 | $0.1318 |
| Historical per-stage 90th-percentile usage | 862,208 | 143,328 | $0.1579 |
| Same high-usage scenario, charging all input at cache-write rate | 862,208 | 143,328 | $0.1794 |

**Expected planning range: approximately $0.13–$0.18.** These are scenarios, not a
statistical confidence interval or a guaranteed bill. Actual input/image lengths,
repairs and provider accounting may differ. The full completion allowance costs
**$1.196032 plus input charges** at the listed rates; it is not a total dollar cap.
No paid model calls, account probes or credential reads were made during preparation.

## Reporting

The report will include accuracy, macro-F1, No/Partial/Yes recall, tree coverage,
accepted-decision accuracy, unresolved counts and breakdowns by task, editor and
historical exposure status. Each v28 bank's newly accepted subset is compared
with its matching v27 bank and the shared regular response.

Accuracy intervals resample source groups, keeping all five sibling outputs
together. The effective pilot size is 16 source clusters, not 80 independent
sources or 480 independent gate evaluations. The three bank replicas are
reported separately rather than selected or pooled as independent examples.

## Artifacts and commands

Prepared directory: `logs/exps/261020-aurora-pilot80-v29`.

- `inputs.json`, `references.json`, `instructions.json`: frozen cohort and
  label-free collection inputs.
- `exposure/`, `exposure_summary.json`, `recent_source_exclusions.json`: full
  historical audit, category shortages and explicit exclusions.
- `gates/`: six frozen v27/v28 artifacts.
- `protocol.json`, `manifest.json`, `preflight_seal.json`: design and source hashes.
- `estimate.json`, `usage_history.json`: pricing and empirical token forecast.
- `execution_plan.json`: pinned collector, dependencies and call limits.

Offline verification:

```bash
PYTHONPATH=. python run/calitree_aurora_pilot_v29.py \
  --verify --output-dir logs/exps/261020-aurora-pilot80-v29
```

Only after explicit user authorization of paid collection:

```bash
PYTHONPATH=. python run/collect_calitree_aurora_pilot_v29.py \
  --live --output-dir logs/exps/261020-aurora-pilot80-v29
```

The collection command has not been run. The preflight and pinned execution plan
verify successfully. All **124 relevant tests pass**, including mocked collection,
source exclusion, deterministic sampling, budgets, resume behavior, failure
retention, label-free payloads and source-cluster reporting.
