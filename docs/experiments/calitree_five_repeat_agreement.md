# Five-repeat agreement on 50 frozen CaliTree cases

## Protocol

Requested extension of the [two-repeat study](calitree_fresh_observation_expanded50.md): retain its two draws unchanged and add three new draws of every condition. This is 50 cases, 112 conditions, and 336 new observation calls. No new compilation, prompt optimization, criteria repair, or label fitting occurs. J16 remains excluded under its existing explicit review.

The same GPT-6 Luna model, temperature 0, reasoning none, instruction, condition, source image and edited image are used. Prior responses and human labels are not included in requests. The checker receives one condition at a time. Each repeat's final prediction uses the same conservative local reducer: any unknown/missing/invalid observation produces unresolved; otherwise any absent produces no, any partial produces partial, and all complete produces yes.

The additional request allowance is 336 calls, each capped at 1,024 completion tokens, with a shared ceiling of 344,064 completion tokens. One HTTP attempt per call; no schema repair, retries or model fallback. Three consecutive transport errors stop execution. Every attempted slot is durable, including failures and interruptions. Resume does not resample them. The original six transport failures remain part of the five-draw record.

Original source dependencies, templates, images, case identities, saved plans and prior jobs are checked and bound in the extension manifest before model calls. The extension writes a separate run directory and never changes the original run. Repeats 1–2 were recorded on September 29, 2026; repeats 3–5 are a later session, so this measures repeatability across sessions using the same requested model ID, without assuming an immutable provider backend.

## Predeclared agreement definitions

The primary measure is **modal resolved final-prediction frequency divided by five**. For example, `[no, no, partial, no, yes]` has 3/5 = 60% agreement; `[partial, partial, partial, partial, unresolved]` has 4/5 = 80%. Unresolved and failed draws do not vote for a resolved prediction and do not shrink the denominator. Five unknown/unresolved draws therefore have 0% resolved agreement. Unknown is reported separately from transport failures.

For each threshold, report the number and percentage of all 50 cases reaching **at least 60%, at least 80%, and 100%**. These are nested categories. Also report disjoint exact-frequency categories to avoid double counting.

Three supporting measures distinguish stable predictions from stable decision features:

- **Exact known condition vector:** count the most frequent complete vector of known statuses. All conditions must agree in the same repeats. An unresolved vector cannot vote.
- **Every condition individually:** every condition has a known modal status occurring at least three/four/five times; the matching repeat positions can differ between conditions. This is weaker than exact-vector agreement.
- **Individual conditions:** apply the same thresholds to all 112 conditions rather than cases.

These are self-consistency measures under the frozen prompt-derived criteria. There is no new raw-prompt judging arm, so the experiment does not measure agreement between direct prompt judgments and decomposition. Human labels remain provisional and are not used to define the modal answer. High repeat agreement does not establish correctness or repair the previously observed condition-scope errors.

## Reproduction and artifacts

```bash
.venv/bin/python -m run.calitree_observation_repeats \
  --output-dir logs/exps/260930-10:51:35-exps
# Add --live for the explicitly requested bounded three-repeat extension.
```

Default invocation verifies inputs and saves the manifest without contacting a model. The run directory contains `manifest.json`, `jobs/`, `budget.json`, `run.log`, `llm-histories.log`, and `results.json`. Original draws are read from `logs/exps/260929-22:30:00-exps/`; the manifest records their hashes.

Offline checks before execution: 18 tests passed covering the original checker contracts and extension metrics, unknown/failure handling, exact-vector distinctions, three-new-draw scheduling, label-free payloads, resume, interrupted slots, dependency checks and budgets.

The broader focused regression run also passed: **60 tests**, including provider and structured-output contracts. After 83 attempts, three consecutive TLS failures stopped the first process. A separate TLS handshake succeeded; execution resumed only unattempted slots with the same manifest and shared budget. All six existing failed slots remained untouched; the pre-resume result and resumption reason are saved.

The user subsequently requested **eight concurrent calls**. After 198 total reservations, the sequential process was interrupted; `check/3/N31/open_sandwich_maker` remained interrupted and was not retried. The remaining 138 unattempted slots use `run/calitree_observation_parallel.py --concurrency 8` with the original shared budget. Per-thread engines retain one HTTP attempt, and a shared thread-safe history writer records responses. An additional manifest binds the scheduling implementation. After three consecutive completed transport errors, dispatch stops and already submitted calls are drained. Concurrency affects scheduling only; prompts, criteria, images, model settings and aggregation remain unchanged.

```bash
.venv/bin/python -m run.calitree_observation_parallel \
  --output-dir logs/exps/260930-10:51:35-exps --concurrency 8
# Add --live to continue only unattempted authorized slots.
```

## Results

All 336 additional slots were attempted: **327 successful observations, eight transport failures, and one interrupted call** during the requested switch to parallel execution. Across all five repeats, there are 545 successful observations out of 560 planned, 14 transport failures and one interruption. No failed or interrupted draw was retried; no criteria or prompt was revised.

| Measure | At least 60% (3/5) | At least 80% (4/5) | 100% (5/5) |
|---|---:|---:|---:|
| Same resolved final prediction, out of 50 cases | **39/50 (78%)** | **36/50 (72%)** | **23/50 (46%)** |
| Same complete known condition vector, out of 50 cases | **35/50 (70%)** | **30/50 (60%)** | **17/50 (34%)** |
| Every condition individually meets threshold, out of 50 cases | 40/50 (80%) | 32/50 (64%) | 17/50 (34%) |
| Individual known conditions, out of 112 conditions | 102/112 (91.1%) | 89/112 (79.5%) | 65/112 (58.0%) |

The first two rows answer different questions: the same final answer can survive changing condition states. Exact-vector agreement requires every status to match together in the same repeats. Condition-wise modal agreement can draw its supporting votes from different repeats.

The final-answer categories without overlap are: **23 cases at exactly 100%, 13 at exactly 80%, three at exactly 60%, and 11 below 60%**. For full vectors they are 17, 13, five and 15 respectively.

### Coverage and interpretation

Of 250 planned case predictions, **199 were resolved**, 40 were unresolved because a condition was unknown, and 11 lacked a complete observation set because of transport failures or interruption. These categories do not overlap in this run. The 545 successful condition responses comprise 504 known statuses and 41 unknown statuses. J03, J17, N04 and N57 were unresolved in all five repeats; they have no resolved agreement votes, although their unresolved outcome repeats.

Examples from the saved results:

| Case | Five final predictions | Final agreement | Exact-vector agreement |
|---|---|---:|---:|
| J10 | partial, partial, partial, partial, partial | 100% | 100% |
| J13 | partial, partial, partial, partial, yes | 80% | 80% |
| J21 | unresolved, no, unresolved, no, no | 60% | 40% |
| J07 | no, no, no, no, no | 100% | 60% |
| N42 | no, yes, no, partial, partial | 40% | 40% |

For the requested **80% threshold, 72% of cases repeat a resolved final answer, while 60% repeat the full known decision set**. This supports useful repeatability on a subset, but the condition features are less stable than final predictions suggest. N42 remains a genuine output-instability example with all its responses available. Prior audits also found stable semantic errors, so this result does not establish correctness, validate human labels as gold, or justify automatically admitting high-agreement cases into training.

New successful usage was **417,789 input tokens and 46,949 completion tokens**. The budget ledger charges/reserves 56,165 completion tokens including eight failed calls and one interrupted call, below the 344,064 ceiling. No claim is made about billing for failed/interrupted requests. Parallelism was enabled for the final 138 slots at the user's request; the original two repeats and earlier sequential part were preserved.

### Verification and detailed artifacts

**65 focused offline tests passed**, including eight simultaneously active workers, shared request/token limits under contention, interruption reuse, transport-stop draining, repeat metrics, checker equivalence, label-free inputs, providers and structured responses. The post-run audit verified original source/image/criteria/job hashes, the parallel driver manifest, all successful response model IDs and finish reasons, the exact checker input allowlist, single-attempt transport, budgets, and an independent recalculation of final-prediction frequencies. One interrupted request has a durable budget reservation and job identity but no response/history line; it is explicitly accounted for.

- [All 50 cases and 112 condition sequences](../../logs/exps/260930-10:51:35-exps/case_table.md)
- [Per-case CSV](../../logs/exps/260930-10:51:35-exps/cases.csv)
- [All 560 observation slots and rationales](../../logs/exps/260930-10:51:35-exps/observations.csv)
- [Machine-readable audit](../../logs/exps/260930-10:51:35-exps/audit.json)
- [Run report](../../logs/exps/260930-10:51:35-exps/report.md)
- [Scheduling changes and resume record](../../logs/exps/260930-10:51:35-exps/resumptions.json)

Recompute exports without model calls:

```bash
PYTHONPATH=. .venv/bin/python logs/exps/260930-10:51:35-exps/analyze_saved_calls.py
```
