# AURORA Individual Prompt Repair and Prompt-Tree Reconstruction Guide

Snapshot date: 2026-09-11 17:20 PDT  
Implementation worktree: `/Users/zzhang/Documents/vejudge/.claude/worktrees/prompt-tree`  
Git branch: `prompt-tree`  
Base commit: `77176f5b18653b558d4c6e2bb77f0a88b4a142e7` (`Implement and evaluate CaliTree calibration variants`)  
Primary model alias: `gpt-5.4-mini`

This document is the reconstruction specification for the AURORA score-calibration work in
the `prompt-tree` worktree. It describes the implementation that exists in the working copy,
the exact settings used for the completed experiments, the later structured and prompt-tree
experiments, all important checkpoint and artifact contracts, the current results, known
limitations, and the cross-machine restoration procedure.

The archive containing this document is the most reliable representation of the current code.
The branch itself is **not** sufficient: at this snapshot, the latest work is uncommitted on top
of the base commit. The worktree has eight modified tracked files and 29 meaningful untracked
files, plus an unneeded `.DS_Store`. A clone or checkout of `prompt-tree` alone therefore does
not reproduce this implementation.

## 1. What “the current algorithm” means

There are two related but different configurations in the source:

| Configuration | Repeat gate | Generality anchors | Status |
| --- | ---: | --- | --- |
| CLI defaults | at least 7/10 | six-anchor guard | Retained for the original experiment design |
| Current intended and completed run | strict majority, at least 6/10 | none (`--focal-only`) | Canonical result used by the later experiments |

The user-facing requirement changed after the first anchor-based run: robustness now means that
the same judge prompt predicts the correct `0/1/2` category on a strict majority of repeated
calls for the focal item. Consequently, any exact recreation of the completed experiment must
explicitly pass both `--focal-only` and `--robust-min-correct 6`. The two PyCharm configurations
currently in `.run/` omit these flags and therefore launch the older anchor/7-of-10 mode unless
their parameter fields are edited.

The complete experimental sequence is:

```text
official AURORA release
    |
    v
deterministic 100-item, label-balanced sample
    |
    v
CaliTree-v2 baseline: temperature-0 screen + 10 temperature-0.3 repeats
    |
    +--> initially correct and repeat-robust: no repair
    |
    +--> wrong OR repeat-unstable: two independent focal repair tracks
           |                         |
           |                         +--> GEPA
           +--> TextGrad
                     |
                     v
             accepted optimized prompt-case pairs
                     |
                     v
       natural prompt -> semantic-decision extraction and clean ablations
                     |
                     v
       strict routing cascade evaluated at 8/10 search + 16/20 confirmation
           1. structured semantic prompt
           2. fixed semantic-requirement prompt tree
           3. independent label-evidence prompt tree
           4. unresolved
```

The routing cascade is an **evaluation inventory**, not yet a deployable router. It uses the
known human label to decide whether a representation passed its repeat gate. An unseen item
does not provide that label, so a separate target-free routing rule would have to be learned
and validated before this cascade could be deployed.

## 2. Source-of-truth files

### 2.1 Main implementation

| File | Responsibility |
| --- | --- |
| `run/aurora_prompt_repair.py` | CLI, phases, live judge, baseline orchestration, TextGrad/GEPA tracks, checkpoints, progress bars, reports |
| `vejudge/experiments/aurora_prompt_repair.py` | Pure sampling, parsing, metrics, robustness, repair-pool, anchor selection, lint, ranking, feedback |
| `run/aurora_prompt_repair/gepa_worker.py` | Isolated Python 3.11 GEPA adapter and one-line JSON protocol |
| `vejudge/core/calibration/textgrad_adapter.py` | TextGrad 0.1.8 adapter and bounded optimizer retry behavior |
| `run/aurora_structured_decision_test.py` | Natural-rubric to semantic-decision extraction and behavioral equivalence evaluation |
| `vejudge/experiments/structured_decision_test.py` | Decision-spec parser, renderers, candidate selection, distribution comparison |
| `run/aurora_structured_ablation.py` | Fresh-natural, semantic-JSON, controlled-prose, and mechanical-JSON ablation |
| `run/aurora_atomic_robustness.py` | Small dual-render atomic-spec optimization pilot |
| `run/aurora_prompt_tree.py` | Instruction decomposition, requirement/fidelity/preservation leaves, deterministic aggregation, first hybrid router |
| `run/aurora_label_prompt_tree.py` | Per-label evidence leaves, support aggregation, final hybrid router |
| `run/aurora_prompt_report.py` | Standalone HTML report entry point |
| `vejudge/experiments/prompt_repair_report.py` | Report payload construction and artifact recovery |
| `vejudge/experiments/prompt_repair_report_template.html` | Self-contained interactive report application |

### 2.2 AURORA materialization and loading

| File | Responsibility |
| --- | --- |
| `run/setup_aurora_bench.py` | Pinned downloads, safe extraction, validation, metadata, splits, manifest |
| `run/setup_aurora_bench.sh` | Python launcher |
| `vejudge/database/dl_aurora/loader.py` | Read-only loader, task/model filters, continuous and ordinal labels |
| `vejudge/database/dl_aurora/__init__.py` | Public dataset exports |
| `vejudge/config.py` | `VEJUDGE_AURORA_BENCH_ROOT` configuration |

### 2.3 Launchers, tests, and documentation

| File/group | Responsibility |
| --- | --- |
| `run/run_aurora_prompt_repair.sh` | Finds the shared main virtual environment or Python 3.11 and executes the module |
| `run/aurora_prompt_repair/setup_gepa_venv.sh` | Creates `.venv-gepa` with `gepa==0.1.4` |
| `.run/AURORA Prompt Repair (Dry Run).run.xml` | PyCharm dry-run configuration |
| `.run/AURORA Prompt Repair (Live Resume).run.xml` | PyCharm live/resume configuration; currently older anchor-mode settings |
| `tests/unit/database/test_aurora_*.py` | Dataset identity, split, score mapping, setup integrity tests |
| `tests/unit/experiments/test_aurora_*.py` | Sampling, repair, structured, tree, label-tree, and report tests |
| `docs/calitree.md`, `docs/data.md`, `run/README.md` | Dataset and workflow documentation |

## 3. Environment and dependencies

The recorded development environment was Apple Silicon macOS with:

```text
Darwin 25.6.0 arm64
Git 2.50.1 (Apple Git-155)
main Python 3.9.6
GEPA Python 3.11.15
```

Relevant installed package versions were:

```text
textgrad 0.1.8
gepa 0.1.4
numpy 2.0.2
pandas 2.3.3
requests 2.32.5 in the main environment
requests 2.34.2 in the GEPA environment
tqdm 4.68.3
Pillow 11.3.0
```

The project declares Python `>=3.9`; its `calitree` optional group pins
`textgrad==0.1.8` and includes `datasets` and Pillow. GEPA is deliberately isolated from the
main environment.

Recreate the environments instead of copying them:

```bash
cd /path/to/prompt-tree

python3.9 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e '.[dev,calitree]'

PYTHON311=/path/to/python3.11 \
  ./run/aurora_prompt_repair/setup_gepa_venv.sh
```

The GEPA setup script installs:

```text
gepa==0.1.4
requests>=2.31
```

Do not copy `.venv` or `.venv-gepa` between laptops. Virtual-environment executables contain
machine-specific paths and may contain platform-specific wheels.

### 3.1 Credentials and live-call gate

No credential is included in the portable archive. `load_creds()` resolves credentials in this
order:

1. A local manual credentials JSON used by the interface.
2. `CHAT_GPT_API_KEY` or `AZURE_OPENAI_API_KEY`, plus
   `OPENAI_COMPAT_BASE_URL` or `LLM_PROXY_BASE_URL` and optional
   `LLM_PROXY_MIRROR_URL`.
3. A human-readable `.env-raw` selected by `VEJUDGE_ENV_RAW`.

All billable CLIs call `require_live()` with the parsed `--live` value. Because the CLIs pass an
explicit false value when the flag is absent, `--live` is effectively required even though the
library-level gate also supports `VEJUDGE_ALLOW_LIVE=1` when no explicit value is supplied.

## 4. AURORA dataset reconstruction

### 4.1 Pinned release

The setup script materializes the AURORA human-rating release dated 2024-12-05:

```text
400 source-image/instruction tasks
5 editor outputs per task
2,000 scored outputs
8 task categories: ag, clevr, emu, epic, kubric, magicbrush, something, whatsup
```

Pinned source identifiers and digests:

```text
ratings Google Drive ID:
  1uWpVOit_eUvI6GnY_Bvaj_vPd3H8cTbT
ratings SHA-256:
  a420cf439f0ccbc02735b358d5cf77dda6f6dd5df872b30d17ace326c98de145

images Google Drive ID:
  1wUwlxN1ArqTlCQQgnsj7DoXNoPRX71Ao
images SHA-256:
  8a3430a01cda0139d4c99835a75dca98e16ec6ccc486fa30afa4504f3f18c69f
```

The five exact editor identifiers live in `AURORA_MODELS` in the loader; do not abbreviate them
when reconstructing item IDs. The full materialized class distribution under the fixed ordinal
mapping is:

```text
no       1,378
partial    450
yes        172
```

### 4.2 Safe setup algorithm

Run:

```bash
VEJUDGE_PYTHON="$PWD/.venv/bin/python" \
  ./run/setup_aurora_bench.sh --root /path/to/data/aurora/bench
```

The implementation:

1. Downloads the ratings JSON resumably.
2. Verifies its pinned SHA-256.
3. Parses and validates every rating row.
4. If all required images are already present and nonempty, skips the large image download.
5. Otherwise downloads the image ZIP resumably and verifies its pinned SHA-256.
6. Rejects absolute paths, `..` traversal, and any ZIP member outside top-level
   `human_ratings`.
7. Extracts through `.part` files and atomically replaces the destination; an existing file of
   the exact archive size is skipped.
8. Verifies exactly 2,000 outputs, exactly 400 task identities, known models/categories, and all
   five model outputs for every task.
9. Writes `metadata.jsonl`.
10. Writes task-grouped `seed_42.json`, `seed_43.json`, and `seed_44.json` splits, each with 80
    train and 320 test task IDs.
11. Writes a per-file SHA-256 manifest.
12. Deletes the approximately 482 MB source ZIP unless `--keep-archive` is passed.

Materialized layout:

```text
aurora/bench/
  source/human_ratings.json
  human_ratings/<task>/...
  metadata.jsonl
  splits/seed_42.json
  splits/seed_43.json
  splits/seed_44.json
  manifest.json
```

### 4.3 Stable identities

After stripping the instruction string at ingestion:

```text
canonical_task_bytes = source_relative_path + "\n" + instruction
task_uid = "aurora-task-" + SHA256(canonical_task_bytes)[0:20]
item_id = task_uid + "::" + exact_editor_model_name
```

The task UID intentionally groups all five editor outputs for the same source/instruction.

### 4.4 Human score and ordinal label

The public artifact contains the mean of repeated discrete human choices, so `human_score` can
be fractional. Individual votes cannot be reconstructed. The loader preserves:

```text
human_score            continuous value in [0,2]
normalized_sc          human_score / 2
ratings                []
raw_ratings_available  false
n_annotators            3, from dataset provenance rather than released votes
```

The fixed classification view is:

```text
human_score < 0.5        -> target_score 0 -> no
0.5 <= score < 1.5      -> target_score 1 -> partial
human_score >= 1.5       -> target_score 2 -> yes
```

This experiment predicts the ordinal category only. It records but does not regress the
continuous score.

### 4.5 Split behavior that must not be confused with sampling

`AuroraBenchLoader(repeat=3)` assigns the seed-44 train/test tag to each row. The prompt-repair
sampler then considers all 2,000 loaded rows; it does **not** filter to the predefined train or
test partition. `source_split` is provenance only in this experiment.

## 5. Deterministic balanced sample

The pure implementation is `build_balanced_sample()`.

For sample size `N`, quota construction is:

```python
base, remainder = divmod(N, 3)
quota[label_i] = base + (1 if i < remainder else 0)
labels = ("no", "partial", "yes")
```

For `N=100`, this gives:

```json
{"no": 34, "partial": 33, "yes": 33}
```

Selection processes the scarce labels first in this different order:

```text
yes -> partial -> no
```

For each label and each remaining quota slot:

1. Filter to that target label.
2. Remove any output whose `task_uid` has already been selected.
3. Choose the lexicographic minimum of:

```python
(
    count_selected_for_same_label_and_model,
    count_selected_for_same_label_and_task_category,
    count_selected_for_model_globally,
    count_selected_for_task_category_globally,
    SHA256(f"{seed}:{item_id}")
)
```

4. Update all four counters and mark the task UID used.

The seeded SHA is a platform-independent tie breaker. This is a greedy balancing algorithm,
not a global assignment optimizer. It balances source model and task category but does not
balance position within the continuous-score interval.

After selection, cases are sorted by `no`, then `partial`, then `yes`, and then by item ID.

The canonical seed-44 sample fingerprint is:

```text
100 outputs from 100 distinct tasks
labels: 34 no, 33 partial, 33 yes
models: exactly 20 per editor
task categories in declared order:
  ag 12, clevr 11, emu 14, epic 13,
  kubric 12, magicbrush 14, something 13, whatsup 11
```

The four unselected sibling outputs for each selected task are reserved, producing 400 excluded
sibling item IDs. The clean future holdout is all five outputs for the remaining 300 tasks:
exactly 1,500 outputs. Its observed labels are 1,081 `no`, 319 `partial`, and 100 `yes`.
The holdout is emitted but is not used by any current baseline, repair, structured, or tree
stage.

## 6. Exact seed judge rubric

The initial rubric is read verbatim from
`vejudge/core/prompts/templates/calitree_v2/initial_rubric.txt`. Its SHA-256 is
`3f72b992a4234652ce44be0ddcf1d9017d886dc9dac48091b7cba494a9167970`.

```text
You are a strict vision-language judge calibrated to ImagenHub Semantic Consistency (SC)
for text-guided image editing.

The first image is SOURCE and the second is EDITED. Evaluate only whether every semantic
condition in the edit instruction is followed while the source remains the same scene.
Do not score standalone perceptual quality: blur, artifacts, realism, or beauty matter only
when they make a requested condition or preserved source content unrecognizable.

Decision procedure:
1. Decompose the instruction into its explicit semantic conditions: requested objects,
   attributes, counts, actions, spatial relations, additions, removals, or replacements.
2. Compare SOURCE and EDITED for each condition. Do not infer success from the instruction;
   cite visible evidence from the images.
3. Check edit locality. A substantially different background, wrong subject, or replacement
   of unrelated source content is a failed semantic condition, not merely a quality issue.
4. Apply these labels with the tie-break rules below.

Labels:
- no: at least one required condition is not followed at all, the requested change is absent
  or contradicted, the wrong subject is changed, or the editing scene/background is replaced.
- partial: every required condition has recognizable evidence, but one or more conditions is
  only partly followed, incomplete, or semantically inaccurate.
- yes: every required condition is followed in its overall idea and the source remains the
  same editing scene. Minor visual artifacts alone do not reduce SC.

Tie breaks:
- no versus partial: use partial only if every condition has some visible, recognizable
  evidence. If any condition has none, use no.
- partial versus yes: use yes only when every condition follows the overall requested idea;
  otherwise use partial.

Return exactly one compact JSON object and nothing else:
{"label":"no|partial|yes","rationale":"brief condition-by-condition image evidence"}
```

The reference to ImagenHub is deliberately retained because the experiment required the
existing CaliTree v2 rubric verbatim.

## 7. Live judge, parsing, and checkpoint semantics

### 7.1 Multimodal request

For every judgment, the rubric is the system message. The user message is multimodal:

```text
Instruction: <exact AURORA instruction>
The first image is SOURCE; the second is EDITED.

<source image as base64 data URI>
<edited image as base64 data URI>
```

Source is always first. An in-process LRU cache holds up to 512 encoded image parts to avoid
re-reading images across repeats.

### 7.2 Parser

`parse_judgment()`:

1. Strips whitespace.
2. Removes an outer Markdown code fence only when the response begins with a fence.
3. Parses the remaining entire string with `json.loads`.
4. Requires the parsed value to be an object with a lowercased label in
   `no|partial|yes`.
5. Treats a missing rationale as an empty string.

Extra JSON keys are accepted. Prose surrounding JSON is not accepted. An invalid response
becomes an empty label with `valid=false` and a parse error.

### 7.3 Transport

The OpenAI-compatible transport sends `/chat/completions` requests and uses endpoint failover.
For the main judge and TextGrad, `max_retries=4` means up to five attempts per endpoint.
Retryable cases are network errors and HTTP 408, 429, 500, 502, 503, or 504. A parseable
`Retry-After` is honored; otherwise exponential waits are 1, 2, 4, 8 seconds, capped at 30.
With a mirror configured, 429 moves immediately to the mirror. Other retryable errors exhaust
the current endpoint before failover. GEPA's private client follows the same design and also
treats 409 as retryable.

The result records the model identifier returned by the API, rather than assuming the requested
alias handled the call. It also records prompt/completion/total tokens, latency, and endpoint
host.

### 7.4 Checkpoint behavior

The run-scoped store is append-only, JSONL, and thread-safe:

```json
{"key":"logical-work-key","value":{"...":"..."}}
```

On load, malformed/torn JSON lines are ignored and the last value for a duplicate key wins.

Judge checkpoint key:

```text
aurora-repair::judge::<call_id>::<SHA256(system_prompt)>::t=<temperature>
```

A completed HTTP response is checkpointed even if its content is invalid, because it is a
completed repeat and must count as a miss. A transport failure is returned as invalid for the
current process but is not checkpointed, so resume attempts it again.

The key does not include the requested model. Never reuse the same checkpoint directory after
changing model unless old entries are intentionally desired.

## 8. Baseline algorithm

For each of 100 sampled cases, construct all 11 logical jobs before execution:

```text
temperature 0.0:
  baseline:init:<item_id>

temperature 0.3:
  baseline:repeat:<item_id>:00
  ...
  baseline:repeat:<item_id>:09
```

The 1,100 jobs run in a `ThreadPoolExecutor`, default concurrency eight. Every repeat has a
unique call ID, so local checkpoint reuse cannot masquerade as a fresh repeat. The initial call
is not included in the repeat robustness statistic.

### 8.1 Robustness statistics

For predictions `P`, target `y`, and threshold `k`:

```text
target_hits = number of valid predictions with label y
target_hit_rate = target_hits / len(P)
robust = len(P) > 0 and target_hits >= k
```

Invalid output is a fourth category and always a miss. The implementation reports:

- `n`, `required_correct`, target hits and rate.
- `robust`.
- `no/partial/yes/invalid` histogram.
- Modal label and share. Tied modes prefer `no`, then `partial`, then `yes`, then `invalid`.
- Shannon entropy in bits across all observed categories.
- Invalid rate.
- Two-sided 95% Wilson interval around the target-hit rate.

This is empirical repeat stability, not a strong statistical confidence claim. Some prose in
the helpers is hard-coded to say “7/10” or denominator ten even when the numeric configuration
is changed; the calculations use the actual passed values.

### 8.2 Baseline classification metrics

The single temperature-zero initial call drives:

- Accuracy, including invalid outputs as errors.
- Balanced accuracy, the mean per-label recall.
- Macro-F1.
- Per-label support, precision, recall, and F1.
- Confusion matrix with prediction columns `no`, `partial`, `yes`, `invalid`.
- Valid prediction rate and invalid count.
- Ordinal MAE after mapping labels to `0,1,2`.
- Quadratic-weighted kappa.

Ordinal MAE and kappa exclude invalid predictions rather than assigning them an ordinal
penalty; invalid count is reported separately.

### 8.3 Repair-pool union

```text
initial_wrong = initial_label != target_label
unstable = repeat_target_hits < configured threshold
repair iff initial_wrong OR unstable
```

The reason is one of:

```text
initial_error_and_unstable
initial_error
unstable_only
```

## 9. Independent per-case repair

Every repair-pool case receives one TextGrad track and one GEPA track. Both start from the
unchanged seed rubric. No case inherits another case's prompt, and neither optimizer inherits
the other optimizer's prompt.

### 9.1 Exact focal-only outer loop

For one `(case, method)` track:

```text
best_prompt = seed_prompt
best_rank = rank(baseline repeats, baseline screen, seed length)

for round in 1..5:
    if complete round checkpoint exists:
        restore it, update best if rank is strictly greater, stop if accepted
        continue

    feedback = failure evidence from baseline (round 1) or previous chronological round
    parent = best_prompt
    candidate = exactly one TextGrad or GEPA outer proposal(parent, feedback)
    lint candidate

    if lint passes:
        screen once at temperature 0
        if screen == human target:
            run 10 fresh temperature-0.3 focal predictions

    accepted = target_hits >= 6       # canonical completed run
    candidate_rank = (target_hits, 0, screen_correct, -character_length)
    save prompt, diff, full round record, and checkpoint

    if candidate_rank > best_rank:
        best_prompt = candidate
        best_rank = candidate_rank

    if accepted:
        force accepted candidate to final and stop

write accepted.txt if accepted else best.txt
```

Screen correctness is an implicit prerequisite because repeats run only after a correct screen.
There is no early stop for an unchanged/duplicate proposal, lint failure, wrong screen,
optimizer error, or stochastic failure. Each consumes one of five rounds.

Feedback comes from the most recent chronological round, while the next proposal parent is the
best-ranked prompt. These can refer to different candidates.

### 9.2 Candidate lint

The candidate is rejected when:

- It is empty.
- Its normalized tokens omit any of `no`, `partial`, `yes`, `label`, or `rationale`.
- It contains normalized `item_id`, `task_uid`, or editor model identifier of at least five
  normalized characters.
- It contains the entire normalized focal instruction when that string is at least 12
  normalized characters.
- A narrow regular expression detects a direct directive assigning the focal target to “this
  case/example/image.”

Normalization lowercases and retains runs of ASCII letters/digits separated by spaces. This is
a heuristic anti-leak guard. It does not prove generality, reject all paraphrased target leakage,
or reject partial copies/distinctive details that do not reproduce the full instruction.

### 9.3 Candidate rank

The exact lexicographic rank is:

```python
(
    focal_repeat_target_hits,
    anchor_correct_count,
    int(screen_correct),
    -len(prompt)
)
```

In focal-only mode the anchor count is always zero. Strict `>` means ties keep the earlier best.
An accepted candidate is forced to be final even if its numeric rank is below the seed's rank.

One edge case follows from the exact implementation: in focal-only mode, when the seed has zero
repeat hits and a wrong screen, a shorter lint-failed candidate can outrank it because both have
the first three rank components equal to zero. This is not special-cased.

### 9.4 Feedback supplied to optimizers

The optimizer is shown:

```text
Revise the general Semantic Consistency rubric, not this item's answer.
Observed prediction: <label or invalid>
Human target: <target label>
Judge rationale: <rationale>
Instruction: <exact focal instruction>
Repeated label distribution: <JSON histogram>
Repeated target hits: <hits>/<n>

Diagnose the reusable no/partial/yes boundary that failed. Return a complete,
standalone rubric preserving exactly the compact JSON label/rationale contract.
Do not include item IDs, editor/model names, the focal instruction, distinctive
image details, or a rule that directly assigns this case's target label.
```

Anchor mode adds prior anchor regressions by label. Focal-only mode omits them.

The optimizer intentionally sees the target label and exact instruction. Anti-overfitting comes
only from textual constraints and linting; there is no hidden-label training design.

### 9.5 TextGrad track

One outer round constructs a new TextGrad variable/optimizer from scratch:

- Current best prompt is a trainable variable.
- Externally observed failure feedback is a non-trainable gradient variable.
- `tg.TGD` uses the VEJudge model adapter at temperature zero.
- Proposal budget is 4,096 tokens by default.
- No TextGrad gradient memory persists between outer rounds.

The constraints require a reusable rubric, the `no/partial/yes` and
`label/rationale` contract, Semantic Consistency-only scoring, preservation of any `sc-v3`
structured fields that appear, and no target-leaking shortcuts.

TextGrad 0.1.8 can raise `IndexError` when its expected improved-variable delimiter is absent.
The adapter rebuilds the variable and optimizer and retries up to three times. If all attempts
fail or yield no nonempty rewrite, the parent prompt is returned unchanged. The proposal section
is protected by a process-wide lock because TextGrad changes module-global logging state;
judging outside that section remains concurrent.

### 9.6 GEPA track

Every GEPA outer round starts an isolated Python 3.11 subprocess. The parent writes exactly one
JSON request to stdin; the worker writes exactly one JSON response to stdout. Credentials are
passed only in `AURORA_GEPA_TOKEN` and `AURORA_GEPA_ENDPOINTS`.

GEPA configuration:

```python
seed_candidate = {"system_prompt": parent_prompt}
trainset = [focal]
valset = [focal]                 # focal-only; anchor mode appends six anchors
candidate_selection_strategy = "current_best"
skip_perfect_score = False
reflection_minibatch_size = 1
use_merge = False
stop_callbacks = MaxCandidateProposalsStopper(1)
seed = experiment_seed + round_index
track_best_outputs = True
display_progress_bar = False
cache_evaluation = False
```

Internal metric calls use temperature zero and 1,024 output tokens; reflection uses temperature
zero and 4,096 tokens. In anchor mode a correct focal is worth 0.70 and each correct anchor 0.05.
In focal-only mode the lone possible score is 0.70; its scale does not alter ranking.

The worker returns the last new candidate, not necessarily GEPA's `best_idx`. It preserves
candidate/parent lineage, aggregate/subscores, evaluation counts, best index, returned index,
and metric-call counts. The outer repair loop independently lints, screens, repeats, and ranks
that returned candidate.

The subprocess timeout is `max(900, timeout * 20)`, which is 2,400 seconds when the CLI timeout
is 120. Worker errors become unchanged proposals with an error payload and consume a round.

In the completed focal run, GEPA returned its parent unchanged in 173 of 199 outer rounds and
produced only 27 distinct candidate hashes. Duplicate proposals are not rejected; they are
screened under new round-specific call IDs and consume rounds.

### 9.7 Historical anchor mode

Anchor mode is retained but is not the current canonical experiment. It selects two initially
correct examples per label. Robust candidates are ranked by:

```text
distance of human aggregate score from prototype 0/1/2, ascending
repeat target hits, descending
modal share, descending
seeded SHA tie break
```

If a label has fewer than two robust initially correct cases, current code fills from the best
nonrobust initially correct candidates, ordered by hit count, score distance, modal share, and
seeded tie. Fallbacks are marked `best_available_nonrobust`, and the guard is marked degraded.
This differs from the original design's hard abort and was added because only one robust
`partial` anchor existed in the real baseline. If a fallback anchor itself enters repair, that
focal track recomputes anchors excluding itself.

In anchor mode, a correct screen triggers repeats; passing repeats triggers six one-shot
temperature-0.3 anchor checks; acceptance requires all six. In focal-only mode none of those
anchors is selected, sent to GEPA, fed back, judged, ranked, or required. Baseline may still
write an unused `anchors.json`, which can produce a confusing but cosmetic warning.

## 10. Repair concurrency, resume, and outputs

Baseline submits 1,100 call jobs at concurrency eight. Repair submits 110 track jobs for the
canonical 55-case pool and two methods; at most eight tracks run concurrently. All stages inside
one track, including ten repeats, are sequential. GEPA can add nested metric concurrency of up
to seven items per worker, though focal-only batches contain only one item.

The progress bar for baseline advances per logical call. The repair bar advances per completed
track; its postfix shows method, item, round, and current gate, so it can remain at the same total
for a long time while tracks make progress.

Checkpoint identities include:

```text
baseline:init:<item>
baseline:repeat:<item>:<index>

repair:<method>:<item>:<round>:screen
repair:<method>:<item>:<round>:repeat:<index>
repair:<method>:<focal>:<round>:anchor:<anchor-index>:<anchor-item>

aurora-repair::optimizer::<method>::<item>::<round>::<digest(parent+feedback)>
aurora-repair::round::<method>::<item>::<round>
```

Per-call and optimizer checkpoints are written before the complete-round record. An interrupted
round can therefore reuse already completed subcalls when reconstructed. `repair_traces.jsonl`
is written only after all submitted tracks finish; `checkpoints.jsonl` is authoritative during
an interruption.

The main run config refuses a nonempty explicit run directory without `--resume`. It treats
model, seed, sample size, repeat count, repeat threshold, temperature, round count, methods,
focal-only mode, and prompt digest as critical immutable resume fields. Dataset root,
concurrency, timeouts/token limits, GEPA interpreter, and prices are not checked and are not
updated in an existing config.

Main run artifacts:

```text
run_config.json
preflight.json                       # dry run only
sample_manifest.json
clean_holdout_manifest.json
baseline_predictions.jsonl
baseline_metrics.json
anchors.json                         # may be unused
checkpoints.jsonl
llm-histories.log
repair_traces.jsonl
prompts/<case-slug>/<method>/
  round-00-seed.txt
  round-01.txt ... round-05.txt
  round-01.diff ... round-05.diff
  accepted.txt OR best.txt
gepa/<case-slug>/round-N/...
case_reports/*.md
summary.json
summary.csv
summary.md
report.html
```

A complete repair trace stores identity/target metadata, repair reason, optimizer method and
acceptance mode, seed and best hashes, baseline evidence, every round's full prompt/diff,
feedback, optimizer payload/lineage, lint, screen, repeats, robustness, optional anchors, rank,
accepted flag, and stop reason.

Track stop reasons are:

```text
accepted_focal_robust
accepted_robust_with_anchors
max_rounds_exhausted
track_error                       # wrapper-level uncaught exception
```

## 11. Canonical focal-only result fingerprint

Canonical completed source run:

```text
/Users/zzhang/Documents/data/vejudge/experiments/worktrees/prompt-tree/
  aurora-prompt-repair-focal-only
```

Exact run settings:

```text
model                    gpt-5.4-mini
seed                     44
sample_size              100
repeats                  10
robust_min_correct       6
focal_only               true
repeat_temperature       0.3
max_rounds               5
methods                  textgrad, gepa
concurrency              8
timeout                  120
judge max_tokens         1024
optimizer max_tokens     4096
input price/M tokens     $0.75
output price/M tokens    $4.50
```

Observed baseline:

```text
accuracy                    0.51
balanced accuracy           0.51010101010101
macro-F1                    0.4772748136230329
ordinal MAE                 0.58
quadratic-weighted kappa    0.4883533055069341
valid predictions           100/100
repeat robust               47/100
repair pool                 55/100
```

Confusion matrix, rows human target and columns model prediction:

| Target | no | partial | yes | invalid |
| --- | ---: | ---: | ---: | ---: |
| no | 17 | 8 | 9 | 0 |
| partial | 10 | 6 | 17 | 0 |
| yes | 0 | 5 | 28 | 0 |

Repair-pool reasons:

```text
initial_error                 2
initial_error_and_unstable   47
unstable_only                 6
```

Repair results:

| Method | Accepted | Eligible | Rounds attempted |
| --- | ---: | ---: | ---: |
| TextGrad | 19 | 55 | 218 |
| GEPA | 30 | 55 | 199 |

Accepted by target:

| Method | no | partial | yes |
| --- | ---: | ---: | ---: |
| TextGrad | 2/18 | 15/32 | 2/5 |
| GEPA | 6/18 | 21/32 | 3/5 |

Recorded usage:

```text
external judge calls       2,216
optimizer outer rounds       417
optimizer model calls      1,040
GEPA metric calls            623
GEPA reflection calls        199
all recorded model calls   3,256
tokens                    3,904,335
estimated cost            $4.42820625
```

These 49 accepted tracks correspond to 33 distinct AURORA outputs: 17 outputs were accepted by
one method, and 16 were accepted by both.

## 12. Natural prompt to structured semantic decisions

### 12.1 Candidate cohort

`select_candidate_rounds()` selects every repair round whose temperature-zero screen was valid
and equal to the human target. It tags the round:

- `accepted_primary` when the original repair round passed its repeat gate.
- `screen_correct_secondary` when the screen was correct but the repeat gate failed.

This is a prompt-round dataset, not one record per item. The completed run contains 70 selected
rounds, including 49 accepted-primary pairs, 21 secondary pairs, and 54 unique prompt strings.

### 12.2 Extracted spec contract

The extractor sees only the natural-language rubric, not the images, case identity,
instruction, prediction, or human target. It must return:

```json
{
  "objective": "short string",
  "evidence_rules": ["atomic rule"],
  "decision_steps": [
    {"order": 1, "decision": "atomic test", "outcomes": "routing effect"}
  ],
  "label_boundaries": {
    "no": ["conditions"],
    "partial": ["conditions"],
    "yes": ["conditions"]
  },
  "tie_breaks": ["ordered boundary rule"],
  "output_contract": {
    "format": "json",
    "labels": ["no", "partial", "yes"],
    "rationale": "requirement"
  }
}
```

Validation requires the six top-level keys, three label-boundary keys, and a nonempty decision
step list. It does not reject extra keys or deeply validate the remaining nested types.

Extraction is deduplicated by prompt SHA and model:

```text
structured-decision::extract::<extractor-model>::<prompt-SHA>
```

It uses temperature zero, 2,048 output tokens, transport retry/failover, and up to three outer
attempts. On schema failure, the invalid assistant answer and a corrective user turn are added
before retrying. Only valid extraction is checkpointed.

### 12.3 Semantic-JSON rendering

The spec is serialized with `indent=2` and `sort_keys=True`, wrapped in
`<semantic_decision_policy>`, and prefaced with an instruction to execute it “in its listed
order.” Because dictionaries are sorted, the usual top-level order becomes:

```text
decision_steps
evidence_rules
label_boundaries
objective
output_contract
tie_breaks
```

The decision-step list itself remains in extractor-emitted array order. This detail matters:
the semantic JSON does not preserve the natural rubric's top-level rhetorical/order structure.

### 12.4 Equivalence evaluation

For every selected pair:

1. Run a structured-prompt screen at temperature zero.
2. Run ten structured-prompt repeats at temperature 0.3 regardless of screen result.
3. Compare with the original round evidence.

Call IDs contain method, item, source round, stage, and repeat index. Comparison reports screen
label preservation, screen correctness, transformed robustness, target-hit delta, total
variation distance over `no/partial/yes/invalid`, Jensen-Shannon divergence in bits, and the full
new robustness record.

Actual accepted-primary result at the original 6/10 gate:

```text
screen label preserved      27/49 = 55.1%
repeat robustness preserved 24/49 = 49.0%
mean target-hit change      -4.06 of 10
mean TV distance             0.437
```

By target, robustness was `no 4/8`, `partial 15/36`, and `yes 5/5`. By optimizer it was GEPA
`9/30` and TextGrad `15/19`.

## 13. Clean representation ablation

Only the 49 accepted-primary prompt-case pairs are used.

| Arm | Representation | New calls |
| --- | --- | ---: |
| Original | Historical accepted screen/repeats | 0 |
| `fresh_natural` | Exact same optimized natural prompt, newly sampled | 11 per pair |
| `semantic_json` | Extracted semantic JSON from prior stage | 0; prior evidence reused |
| `controlled_prose` | Extracted spec rendered in fixed prose | 11 per pair |
| `mechanical_json` | Every original line losslessly encoded in ordered JSON | 11 per pair |

The three new arms make `49 * 3 * 11 = 1,617` judge calls. Arms are sequential inside a pair;
pairs run concurrently.

Controlled prose orders sections as objective, evidence rules, numerically sorted decision
steps, label boundaries `no/partial/yes`, tie breaks, and output contract. Mechanical JSON stores
every original line, including blanks/repetition, as `{"order": n, "text": ...}` under
`lossless_ordered_prompt_lines_v1`, then adds a wrapper asking the model to preserve exact text,
order, repetition, and priority.

Actual results:

| Arm | Screen correct | Robust at 6/10 | Mean hit delta | Mean TV |
| --- | ---: | ---: | ---: | ---: |
| Historical original | 49/49 | 49/49 | 0.00 | 0.000 |
| Fresh natural | 36/49 | 36/49 | -1.76 | 0.235 |
| Semantic JSON | 27/49 | 24/49 | -4.06 | 0.437 |
| Controlled prose | 26/49 | 26/49 | -3.86 | 0.429 |
| Mechanical JSON | 27/49 | 26/49 | -3.35 | 0.384 |

The fresh-natural drop is crucial: much of the apparent loss is resampling/nonstationarity and
selection on the successful historical run, not semantic restructuring alone. Mechanical JSON
still loses more, showing that serialization/wrapping changes behavior even when line content
and order are preserved. Similar semantic-JSON and controlled-prose results imply that semantic
compression and salience also matter. These are independent stochastic samples, not paired
random-seed trials.

## 14. Atomic-spec robustness pilot

This optional pilot tries to optimize the extracted decision spec itself across two renderings.
It is not part of the final 43/49 routing count.

Candidate selection can choose all accepted-primary pairs or only prior structured failures. A
bounded pilot buckets by optimizer and target label, sorts each bucket by seeded SHA, alternates
methods alphabetically, and rotates available label buckets.

For each track, rounds are `0..4`:

1. Round zero evaluates the extracted seed spec without a proposal.
2. Later rounds propose a complete revised spec at temperature zero.
3. Lint rejects focal IDs/instruction, optimizer meta-language, schema failures, and changes to
   `objective` or `output_contract` relative to the parent.
4. Compile a canonical prose form and a differently ordered/worded alternate prose form.
5. Run ten temperature-0.3 calls for each form.
6. Require both forms to reach 8/10.
7. Only then run 20 fresh canonical confirmations and require 16/20.
8. Stop on acceptance; otherwise feed all distributions and the human target to the next
   proposal.

Invalid proposals consume a round while retaining the preceding valid spec. Ranking is:

```python
(
    min(canonical_hit_rate, alternate_hit_rate),
    confirmation_hit_rate,
    canonical_hit_rate + alternate_hit_rate,
    -len(canonical_prompt)
)
```

The alternate rendering changes wording as well as section order, so this tests
representation/order sensitivity, not pure ordering causality. Confirmation covers only the
canonical rendering.

The six-case structured-failure pilot accepted 3/6: TextGrad 2/3 and GEPA 1/3. No seed passed
both renderings; 558 model calls used 735,000 tokens, estimated at $0.7291. The most diagnostic
track alternated canonical/alternate target hits `0/8 -> 10/2 -> 4/9 -> 2/10 -> 5/10`, showing
that revisions could move salience between renderings without reaching invariant behavior.

## 15. Fixed semantic-requirement prompt tree

`run/aurora_prompt_tree.py` is a new evaluator, not a transformation of each optimized prompt.
The accepted repair identity chooses the cohort and target, but the evaluator uses only:

- the focal edit instruction;
- source and edited images;
- fixed decomposition/leaf prompts;
- deterministic aggregation.

Thus two accepted optimizer tracks for the same AURORA item share the same tree behavior and can
reuse identical checkpoints.

### 15.1 Cohort and stricter reinterpretation

The source cohort is the 49 accepted-primary repair pairs. Existing structured-prompt repeats
are reinterpreted as robust only if exactly ten repeats exist and at least eight hit the target.
Although the earlier structured summary reported 24/49 at 6/10, only 19/49 satisfy this stricter
8/10 route gate.

Pilot defaults are `--selection structured-failures --limit 6`. The completed full-v4 run used
`--selection all` and a limit at least 49.

### 15.2 Instruction decomposition

The temperature-zero decomposer returns one to four nonoverlapping requirements:

```json
{
  "requirements": [
    {
      "id": "r1",
      "text": "visually checkable condition",
      "role": "core|modifier",
      "kind": "object|action|relation|attribute|outcome"
    }
  ]
}
```

Requested objects, transformations, actions, and relations are core. Color, size, count,
degree, or fine placement can be modifiers. Explicit causal instructions should separate actor
or contact, action, and observable result; `outcome` is reserved for an explicit causal result
or before/after comparison. Ordinary final-state spatial instructions remain `relation`.
Preservation and visual quality are not emitted as instruction requirements.

The parser extracts the first-to-last JSON braces, normalizes whitespace, requires 1-4 entries,
rejects unsupported roles/kinds and duplicate text, ignores model IDs, renumbers `r1..r4`, and
requires at least one core. On decomposition failure, the entire instruction becomes one
fallback `core/action` requirement. The decomposition remains marked invalid, but the tree still
runs on that fallback.

### 15.3 Calls per tree repetition

For each requirement, independently judge:

1. **Presence**: absent/contradicted=`no`; directionally correct but weak/incomplete/ambiguous=
   `partial`; clear/sufficient=`yes`.
2. **Strict fidelity**: actively inspect meaningful semantic shortfalls. Contact, holding,
   motion, and relations must be visibly demonstrated; attributes must cover the requested
   target.

Then independently judge collateral preservation across the two images. Low-level aesthetics
are ignored unless they change semantic content.

For `R` requirements, one tree repetition makes `2R + 1` VLM calls. With 1-4 requirements that
is 3, 5, 7, or 9 calls.

### 15.4 Deterministic combination

Per requirement:

```text
invalid presence/fidelity                         -> invalid
presence == no                                    -> no
kind == outcome AND fidelity == no                -> no
presence == yes AND fidelity == yes               -> yes
otherwise                                          -> partial
```

Whole tree:

```text
any invalid leaf                                  -> invalid
any core requirement == no OR preservation == no -> no
any core == partial
  OR preservation == partial
  OR any modifier != yes                          -> partial
otherwise                                          -> yes
```

A modifier can therefore be `no` while the overall tree is only `partial`; a missing core forces
`no`. There is no final LLM aggregation call.

### 15.5 Search, confirmation, and route precedence

For each prompt-case identity:

1. Run ten complete tree repetitions.
2. Require 8/10 target hits.
3. Only then run 20 new complete tree repetitions.
4. Require 16/20.

First routing manifest precedence:

```text
if structured prompt passes strict 8/10 gate:
    structured_prompt
else if semantic tree passes both gates:
    prompt_tree
else:
    unresolved
```

Completed full-v4 result:

```text
tree accepted                    27/49
strict structured passed         19/49
hybrid union                     37/49 = 75.51%
tree search passed               29/49
tree confirmation passed         27/29
recorded calls                    2,783
tokens                         2,406,047
estimated cost                  $2.26576275
```

Only 18 of the 27 tree successes become tree routes, because 9 were already claimed by the
higher-priority structured route. Tree acceptance by target was `no 4/8`, `partial 23/36`, and
`yes 0/5`.

## 16. Independent label-evidence prompt tree

This final fallback runs only on the 12 identities still marked unresolved.

For each candidate label `no`, `partial`, and `yes`, build one proposition prompt containing:

- `spec["label_boundaries"][candidate_label]`;
- only tie-break strings whose lowercase text literally contains that label.

It omits the extracted objective, evidence rules, decision steps, and output contract. The leaf
does not choose among categories; it rates support for its one proposition:

```text
leaf label no      -> support 0
leaf label partial -> support 1
leaf label yes     -> support 2
```

Aggregation:

```text
any invalid/missing leaf -> invalid
unique highest support   -> that proposition's category
any tie for maximum      -> partial
```

Every tie, including `no` versus `yes`, resolves to the ordinal middle. This creates an explicit
`partial` bias and matters because 9/12 unresolved identities target `partial`.

Each complete repetition makes three temperature-0.3 calls and has no separate temperature-zero
screen. The same 8/10 search and 16/20 confirmation gates apply.

The completed fallback accepted 6/12: all six were `partial`; none of three `no` cases passed.
It made 780 calls, used 780,914 tokens, and cost approximately $0.7222.

Final manifest precedence:

```text
structured_prompt > prompt_tree > label_prompt_tree > unresolved
```

Final pair-level routes:

| Route | Count |
| --- | ---: |
| Structured prompt | 19 |
| Semantic requirement tree | 18 |
| Label-evidence tree | 6 |
| Unresolved | 6 |
| Total | 49 |

Final empirical robust coverage is `43/49 = 87.7551%`, over 49 accepted optimizer
prompt-case pairs representing 33 distinct images. It is not coverage over all 100 baseline
items or a held-out population estimate.

## 17. Interpretation of ordering and prediction changes

The experiments support several different ordering effects, which should not be conflated:

1. **Historical-selection effect.** An optimized prompt was accepted because one particular
   screen/repeat sample passed. Re-running the exact same natural prompt reduced robustness from
   49/49 to 36/49. This is winner's curse, stochastic nonstationarity, or both.

2. **Serialization/context effect.** Mechanical JSON preserves every line and line order, yet
   only 26/49 remain robust. The wrapper, nesting, delimiters, and the instruction to execute an
   encoded prompt change what the model treats as salient.

3. **Semantic compaction effect.** Extraction removes rhetoric, examples, redundancy, and local
   phrasing. Semantic JSON and controlled prose perform similarly poorly, implying that the lost
   surface cues and relative emphasis mattered beyond JSON syntax.

4. **Top-level ordering effect.** Semantic JSON alphabetizes dictionary keys, placing ordered
   decisions before the objective and tie breaks last. Controlled prose restores a more natural
   objective/evidence/steps/boundaries/ties order. Alternate prose moves label boundaries before
   evidence and decisions. Because wording changes too, observed differences are
   representation/order sensitivity, not a clean causal estimate of order alone.

5. **Operational factorization effect.** The semantic prompt tree prevents one monolithic call
   from letting a salient observation dominate everything. Presence, strict fidelity, and
   preservation are separate calls, and typed deterministic rules establish priority. This
   improves the hybrid union to 37/49 at the stricter gate.

6. **Category-competition effect.** The label tree asks three independent proposition questions
   rather than making one model call choose among competing categories. This recovers six more
   `partial` pairs, but its tie-to-partial rule is an important built-in bias.

The strongest current hypothesis is therefore not simply “JSON order changes the answer.” The
judge is sensitive to presentation, local criterion salience, and stochastic resampling. Making
the decision graph operational through independent calls and deterministic typed aggregation is
more reliable than expecting one prompt rendering to preserve an invariant internal program.

## 18. Standalone front-end report

Generate or refresh a report without model calls:

```bash
python -m run.aurora_prompt_report /path/to/compatible/run
```

Optional `--output` chooses another HTML path. `baseline_predictions.jsonl` is required. The
builder optionally joins repair traces, structured results, ablation results, all three summary
JSONs, run config, sample manifest, prompt files, and diffs.

The report contains:

- Summary metrics and repair acceptance.
- Search plus target/status filters.
- All sampled cases and metadata.
- Source/edited image panes.
- Baseline screen and all repeated predictions/rationales.
- TextGrad and GEPA tabs.
- Every round's prompt, diff, feedback, lint, screen, repeats, distribution, Wilson interval,
  anchor evidence when present, and optimizer lineage.
- Nested structured-equivalence and clean-ablation evidence for matching rounds.
- Raw JSON evidence.
- Folder/file drag-and-drop loading for compatible experiment directories.

The HTML embeds application code and experiment JSON but not the images. Image URLs remain local
absolute `file://` paths. Copying only the HTML to another laptop will not preserve image display
unless those paths are recreated or remapped. Python artifact recovery can repair old prompt/diff
paths when the old absolute path contains the same run-directory name; it does not generally
repair dataset paths. Embedded JSON escapes `<`, `>`, and `&` to prevent terminating the script
element.

## 19. Exact commands to recreate the current sequence

Set paths for the new laptop. The `--data-root` used by the two tree scripts is the directory
corresponding to the old `.claude/data` root, so it must contain `aurora/bench`, not be the
`aurora/bench` directory itself.

### 19.1 Canonical focal-only repair

```bash
./run/run_aurora_prompt_repair.sh all \
  --live \
  --run-dir /path/to/experiments/aurora-prompt-repair-focal-only \
  --resume \
  --focal-only \
  --robust-min-correct 6 \
  --model gpt-5.4-mini \
  --sample-size 100 \
  --seed 44 \
  --repeats 10 \
  --repeat-temperature 0.3 \
  --max-rounds 5 \
  --methods textgrad,gepa \
  --concurrency 8 \
  --timeout 120 \
  --max-tokens 1024 \
  --optimizer-max-tokens 4096 \
  --dataset-root /path/to/data-root/aurora/bench \
  --gepa-python "$PWD/.venv-gepa/bin/python"
```

Omit `--resume` only when the target directory does not yet exist or is empty.

### 19.2 Structured equivalence

```bash
python -m run.aurora_structured_decision_test \
  --run-dir /path/to/experiments/aurora-prompt-repair-focal-only \
  --model gpt-5.4-mini \
  --extractor-model gpt-5.4-mini \
  --repeats 10 \
  --robust-min-correct 6 \
  --concurrency 8 \
  --timeout 120 \
  --live \
  --resume
```

### 19.3 Clean ablation

```bash
python -m run.aurora_structured_ablation \
  --run-dir /path/to/experiments/aurora-prompt-repair-focal-only \
  --model gpt-5.4-mini \
  --repeats 10 \
  --robust-min-correct 6 \
  --concurrency 8 \
  --timeout 120 \
  --live \
  --resume
```

### 19.4 Optional six-case atomic pilot

```bash
python -m run.aurora_atomic_robustness \
  --run-dir /path/to/experiments/aurora-prompt-repair-focal-only \
  --output-dir /path/to/experiments/aurora-atomic-robustness-pilot \
  --data-root /path/to/data-root \
  --model gpt-5.4-mini \
  --selection structured-failures \
  --limit 6 \
  --seed 44 \
  --search-repeats 10 \
  --search-min-correct 8 \
  --confirmation-repeats 20 \
  --confirmation-min-correct 16 \
  --max-rounds 5 \
  --concurrency 8 \
  --timeout 120 \
  --live \
  --resume
```

### 19.5 Full semantic prompt tree

```bash
python -m run.aurora_prompt_tree \
  --run-dir /path/to/experiments/aurora-prompt-repair-focal-only \
  --output-dir /path/to/experiments/aurora-prompt-tree-full-v4 \
  --data-root /path/to/data-root \
  --model gpt-5.4-mini \
  --selection all \
  --limit 100 \
  --seed 44 \
  --repeats 10 \
  --min-correct 8 \
  --confirmation-repeats 20 \
  --confirmation-min-correct 16 \
  --concurrency 6 \
  --timeout 120 \
  --live \
  --resume
```

Any limit at least 49 evaluates the complete accepted-primary cohort.

### 19.6 Label-evidence fallback

```bash
python -m run.aurora_label_prompt_tree \
  --run-dir /path/to/experiments/aurora-prompt-repair-focal-only \
  --prior-routing-manifest \
    /path/to/experiments/aurora-prompt-tree-full-v4/hybrid_routing_manifest.jsonl \
  --output-dir /path/to/experiments/aurora-label-prompt-tree \
  --data-root /path/to/data-root \
  --model gpt-5.4-mini \
  --repeats 10 \
  --min-correct 8 \
  --confirmation-repeats 20 \
  --confirmation-min-correct 16 \
  --concurrency 8 \
  --timeout 120 \
  --live \
  --resume
```

Both tree CLIs parse `--resume` but reuse checkpoints based on output-directory contents
regardless of the flag. They do not persist/validate a complete run configuration. Start a new
output directory when changing model or prompt semantics.

## 20. Current data and artifact locations after repository reorganization

The full movement record is `/Users/zzhang/Documents/repo_reorg_traces.md`.

Current relevant paths on the source laptop:

```text
central AURORA dataset:
  /Users/zzhang/Documents/data/vejudge/datasets/hidden-claude/main/aurora/bench

compatibility/local AURORA copy that currently also exists:
  /Users/zzhang/Documents/vejudge/.claude/data/aurora/bench

complete focal repair + structured/ablation cache:
  /Users/zzhang/Documents/data/vejudge/experiments/worktrees/prompt-tree/
    aurora-prompt-repair-focal-only

latest atomic pilot:
  /Users/zzhang/Documents/vejudge/.claude/worktrees/calitree-goal-plan-1940df/
    logs/exps/aurora-atomic-robustness-pilot

latest full semantic tree:
  /Users/zzhang/Documents/vejudge/.claude/worktrees/calitree-goal-plan-1940df/
    logs/exps/aurora-prompt-tree-full-v4

latest label tree:
  /Users/zzhang/Documents/vejudge/.claude/worktrees/calitree-goal-plan-1940df/
    logs/exps/aurora-label-prompt-tree
```

The similarly named `prompt-tree/logs/exps/aurora-prompt-repair-focal-only` is an incomplete
stub and cannot drive the downstream experiments. The centralized 72 MB run is authoritative.

The newer tree scripts can remap a stored path containing the exact marker
`/vejudge/.claude/data/` by appending its suffix to `--data-root`. Main repair and structured
scripts do not apply that remapper. For exact cached continuation on another laptop, either
recreate compatible paths, mechanically update recorded image paths, or make a fresh baseline
run under the new paths.

## 21. File-by-file working-copy changes

### Modified tracked files

- `docs/calitree.md`: AURORA calibration track and score semantics.
- `docs/data.md`: AURORA materialized layout and task-grouped split description.
- `logs/updates/updates_summary.md`: AURORA integration change record.
- `run/README.md`: repair/report/structured workflow commands and progress behavior.
- `vejudge/config.py`: adds `AURORA_BENCH_ROOT` with
  `VEJUDGE_AURORA_BENCH_ROOT` override.
- `vejudge/core/calibration/textgrad_adapter.py`: changes the optimized-variable role from
  ImagenHub-specific to general Semantic Consistency.
- `vejudge/lm_engine/lm_template/base.py`: propagates the API-returned model, latency, and
  endpoint host into engine output/history.
- `vejudge/lm_engine/openai_compat.py`: preserves the model identifier returned by the service.

### New meaningful files

```text
.run/AURORA Prompt Repair (Dry Run).run.xml
.run/AURORA Prompt Repair (Live Resume).run.xml
run/aurora_atomic_robustness.py
run/aurora_label_prompt_tree.py
run/aurora_prompt_repair.py
run/aurora_prompt_repair/gepa_worker.py
run/aurora_prompt_repair/setup_gepa_venv.sh
run/aurora_prompt_report.py
run/aurora_prompt_tree.py
run/aurora_structured_ablation.py
run/aurora_structured_decision_test.py
run/run_aurora_prompt_repair.sh
run/setup_aurora_bench.py
run/setup_aurora_bench.sh
tests/unit/database/test_aurora_loader.py
tests/unit/database/test_aurora_setup.py
tests/unit/experiments/test_aurora_atomic_robustness.py
tests/unit/experiments/test_aurora_label_prompt_tree.py
tests/unit/experiments/test_aurora_prompt_repair.py
tests/unit/experiments/test_aurora_prompt_tree.py
tests/unit/experiments/test_prompt_repair_report.py
tests/unit/experiments/test_structured_decision_test.py
vejudge/database/dl_aurora/__init__.py
vejudge/database/dl_aurora/loader.py
vejudge/experiments/__init__.py
vejudge/experiments/aurora_prompt_repair.py
vejudge/experiments/prompt_repair_report.py
vejudge/experiments/prompt_repair_report_template.html
vejudge/experiments/structured_decision_test.py
```

`vejudge/.DS_Store` is unrelated metadata and is excluded from the portable archive.

## 22. Key implementation fingerprints

These hashes identify the implementation immediately before this document was added:

```text
9fdd5ce271252106e7d9425bb61e4fb0176ce354b37e3beec8b93796820343da  run/aurora_prompt_repair.py
10a31f766e840ced8f4e5a4fa6317d5422417bab237b58091394ddc030c6937d  vejudge/experiments/aurora_prompt_repair.py
a1a775ce3e8a1eebe2ac27790f0414960593ea1d2430fb13e3815b79c195d943  run/aurora_prompt_repair/gepa_worker.py
68a7e0eb618593b81c0263d68b4cf3fe1a3e30cd5f4b7393615f41931d24121a  vejudge/core/calibration/textgrad_adapter.py
13c6d1076679579cc868d06a0d7389afd483c0581469612621eb5b53eebe3b22  run/aurora_structured_decision_test.py
f0ca68281258a1b8166ce11c1d5ad81bdb4e15e80ea998fe08fae497dfc2f91a  vejudge/experiments/structured_decision_test.py
71b85ee12228e8f4039ced5f6040e04753641aadb063a581528f367be69e272a  run/aurora_structured_ablation.py
d53751a376229dc5e71825f1689335734021be08f3c421d66aebd9ed469688d0  run/aurora_atomic_robustness.py
21c8ff7a0030b1e548d228dbf1569eb46fb5a1e436d627bbecaca4af8a1c92ad  run/aurora_prompt_tree.py
7a6a2df26c3f7191097b367508ac0d9bd2fb0e5009d5cbc1304cf15fc39ccba8  run/aurora_label_prompt_tree.py
08c993bb4648c8bba57348e887943e82d663622bbea5659059c624ca0c511368  vejudge/experiments/prompt_repair_report.py
e719a699365300c744d2505d14e0ab20efa82b02516d104d05b8ff41e4bc75cb  vejudge/experiments/prompt_repair_report_template.html
a4727617bf23cd8af66faad4729cddf2c785644d76b226c6f74d2f37d1be75b7  run/setup_aurora_bench.py
e39c7e64568c67b28bb96d9989ec94ed2ef3a6a82c1d0e80a401d9dd11e3f5c4  vejudge/database/dl_aurora/loader.py
ddbf737ad925ee35e451f4f4b7b192f76a2011c1911d9a8e03c515fb8ef23bca  vejudge/lm_engine/openai_compat.py
3f72b992a4234652ce44be0ddcf1d9017d886dc9dac48091b7cba494a9167970  vejudge/core/prompts/templates/calitree_v2/initial_rubric.txt
```

The transfer package includes an archive-level SHA-256 and a content manifest generated after
this document was inserted.

## 23. Tests and verification boundaries

Relevant unit tests cover:

- Exact quotas, task uniqueness/disjointness, deterministic balancing, and 1,500-output holdout.
- Score cutoffs, split grouping, stable identities, archive safety, and asset validation.
- Invalid predictions as misses, Wilson interval, 7/10 boundary, confusion/ordinal metrics, and
  repair-pool union.
- Anchor preflight/fallback/exclusion, lint, rank, fresh checkpoint identities, focal-only
  no-anchor behavior, acceptance, exhaustion, anchor regression, and round resume.
- Structured spec parsing/rendering, candidate cohorts, and behavior-distance calculations.
- Pilot selection and immutable-field lint.
- Requirement parsing, typed deterministic tree aggregation, presence/fidelity combination.
- Label-leaf isolation, unique support winner, tie-to-partial, and invalidation.
- Report payload joining and HTML generation.

Tests do not make live model calls and do not establish reproducibility of stochastic API
responses. They do not provide end-to-end GEPA orchestration, browser E2E, live Google Drive
download, or full live tree orchestration coverage.

The repair/data/transport subset passed 41 tests during this audit. The prompt-tree,
label-tree, report, and dataset subset passed 34 tests. The final combined eight-file suite
listed in the restoration section passed 52 tests with one existing Python 3.9 LibreSSL warning.

## 24. Limitations and exact-reproduction caveats

1. Seed 44 determines data choice, stable tie ordering, and GEPA library randomness. It is not
   sent as an API sampling seed.
2. A moving `gpt-5.4-mini` alias, endpoint changes, provider nondeterminism, and temperature
   sampling prevent exact response recreation from code alone. Checkpoint JSONL is the
   authoritative prediction evidence.
3. Focal-only prompts are optimized and selected on the same item. Their success is not evidence
   of cross-item generalization.
4. The final routing order is chosen with known target labels and is not deployable as written.
5. The 49-pair denominator double-counts 16 items repaired by both methods; there are 33 unique
   items.
6. The holdout exists but remains unused.
7. The structured extractor is only shallowly schema-validated and may discard rhetorically
   important information.
8. The clean ablation's “original” is selected historical evidence, not a simultaneous fresh
   control; `fresh_natural` is the proper resampling reference.
9. Alternate prose changes wording and order together.
10. Label-tree tie resolution creates a middle-class bias.
11. Duplicate optimizer proposals are not rejected.
12. Some robustness/Markdown prose hard-codes default denominators even when numeric CLI values
    change.
13. Atomic confirmation tests canonical prose only.
14. Transport failures are absent from usage totals unless they eventually succeed.
15. Cost uses a static 2026-09-09 estimate of $0.75/M input and $4.50/M output and excludes
    cache discounts and gateway/provider adjustments.
16. Absolute artifact/image paths in historical runs must be mapped on another laptop.
17. `--resume` is syntactic but unused by several downstream runners; directory/checkpoint
    contents actually control reuse.
18. Tree runners do not catch each future's exception, so one uncaught case error can abort final
    result materialization even while completed calls remain checkpointed.
19. Tree call IDs omit optimizer method/source round at item level. Prompt hashes keep differing
    label-tree specs distinct, but concurrently submitted identical prompt-tree identities can
    race before the first checkpoint write.
20. The current PyCharm launchers reflect the older anchor-default experiment, and their dataset
    environment paths predate the repository reorganization.

## 25. Portable archive restoration

The archive intentionally excludes:

```text
.git                         linked-worktree pointer tied to this laptop
.venv and .venv-gepa         nonportable environments
.idea                        machine-specific PyCharm workspace state; shared .run files remain
web/node_modules             reproducible frontend dependencies
web/dist
web/playwright-report
web/test-results
.pytest_cache
all __pycache__ directories
*.pyc
.DS_Store
credentials and .env-raw
large AURORA dataset
central 72 MB focal-repair experiment, already under the data backup
```

The package additionally carries the three small, latest post-reorganization output directories
(`atomic-robustness-pilot`, `prompt-tree-full-v4`, and `label-prompt-tree`) because they otherwise
live in a different worktree and would not be captured with the code.

On the destination laptop:

```bash
cd /path/to/vejudge

# If prompt-tree does not already exist there:
git worktree add -b prompt-tree /desired/path/prompt-tree \
  77176f5b18653b558d4c6e2bb77f0a88b4a142e7

# If the branch already exists:
# git worktree add /desired/path/prompt-tree prompt-tree

# Extract the transfer package somewhere temporary, then overlay only its
# prompt-tree-overlay directory. Do not copy a .git file from the source laptop.
rsync -a /path/to/extracted/prompt-tree-overlay/ /desired/path/prompt-tree/
```

Then recreate environments, configure credentials separately, set
`VEJUDGE_AURORA_BENCH_ROOT`, and restore the central focal-repair run and the included latest
outputs under whatever experiment root you choose. Update all command-line paths accordingly.

Before continuing, verify:

```bash
cd /desired/path/prompt-tree
git status --short --branch
shasum -a 256 run/aurora_prompt_repair.py run/aurora_prompt_tree.py \
  run/aurora_label_prompt_tree.py
.venv/bin/python -m pytest -q -p no:cacheprovider \
  tests/unit/experiments/test_aurora_prompt_repair.py \
  tests/unit/experiments/test_structured_decision_test.py \
  tests/unit/experiments/test_aurora_atomic_robustness.py \
  tests/unit/experiments/test_aurora_prompt_tree.py \
  tests/unit/experiments/test_aurora_label_prompt_tree.py \
  tests/unit/experiments/test_prompt_repair_report.py \
  tests/unit/database/test_aurora_loader.py \
  tests/unit/database/test_aurora_setup.py
```

If exact past predictions are needed, transfer and retain their checkpoint/history/result JSONL
files. If only the algorithm is needed, the worktree overlay, base commit, environment pins,
dataset manifest, and this document are sufficient to reconstruct the code path.

## 26. Exact prompt constants for downstream reconstruction

The source files and their hashes remain the final authority. These copies make the main
prompt-bearing parts of the later algorithms reconstructable from this document alone. Preserve
line breaks, braces, and capitalization. Double braces in the two requirement templates are
Python format-string escapes; after `.format(...)`, the judge receives single JSON braces.

### 26.1 Semantic-decision extraction system prompt

Source: `run/aurora_structured_decision_test.py`, constant `EXTRACTION_SYSTEM`.

```text
Convert a natural-language vision-judge rubric into a compact,
case-agnostic semantic decision specification. You will receive only the rubric. Never add
examples, image details, task IDs, model IDs, focal instructions, predicted labels, or target
answers. Preserve every decision boundary and its priority, but remove rhetorical prose.
Return exactly one JSON object with these keys:
{
  "objective": "short string",
  "evidence_rules": ["atomic rule"],
  "decision_steps": [{"order": 1, "decision": "atomic test", "outcomes": "routing effect"}],
  "label_boundaries": {"no": ["conditions"], "partial": ["conditions"], "yes": ["conditions"]},
  "tie_breaks": ["ordered boundary rule"],
  "output_contract": {"format": "json", "labels": ["no","partial","yes"], "rationale": "requirement"}
}
```

### 26.2 Atomic-spec proposer system prompt

Source: `run/aurora_atomic_robustness.py`, constant `PROPOSER_SYSTEM`.

```text
You improve a reusable, case-agnostic atomic decision specification
for a no/partial/yes image-edit judge. Return the complete revised JSON object only. Keep the
same schema and output contract. Modify only evidence_rules, decision_steps,
label_boundaries, and tie_breaks. Use atomic decisions, preserve explicit priority, and make
the no/partial and partial/yes boundaries executable. Never mention a particular image,
instruction, item, editor, prediction, target answer, training process, or feedback.
```

The user message is exactly the concatenation:

```text
Current atomic specification:
<pretty-printed current spec>

Aggregate behavioral failure signal:
<feedback>
```

### 26.3 Instruction decomposer system prompt

Source: `run/aurora_prompt_tree.py`, constant `DECOMPOSER_SYSTEM`.

```text
Decompose one image-edit instruction into independent, visually
checkable semantic requirements. Return JSON only:
{"requirements":[{"id":"r1","text":"...","role":"core|modifier","kind":"object|action|relation|attribute|outcome"}]}

A core requirement is the requested object, transformation, action, or relationship whose
absence means the main edit did not happen. A modifier is an attribute such as color, size,
count, degree, or fine placement: if the core edit is present but a modifier fails, the edit
is partial rather than wholly absent. Actions and requested spatial relationships are core.
For a causal action with an explicit result, emit separate core requirements for the actor or
contact, the action, and the observable resulting state. For example, do not combine "a hand
pushes an object farther right" into one requirement: separately check the hand/contact and
that the object is visibly farther right than in the source; mark the latter as kind=outcome.
Express ordinary requested final states directly. For example, "move the candles close to
each other" becomes "the candles are close to each other" with kind=relation, not a comparison
of source and edited spacing. Use kind=outcome only for an explicit causal result or explicit
before/after comparison that must be observed.
Do not add scene preservation, visual quality, or unstated requirements. Use one to four
non-overlapping requirements and include at least one core requirement.
```

### 26.4 Requirement-presence leaf

Source: `run/aurora_prompt_tree.py`, constant `REQUIREMENT_LEAF`.

```text
You are one leaf in a prompt-tree image-edit evaluator.
Evaluate ONLY whether there is visible, directionally correct evidence for the single
requirement below. Do not score scene preservation, unrelated objects, image aesthetics,
or the overall instruction.

Focused requirement ({role}, {kind}): {text}

Choose:
- no: the edited image has no visible evidence for this requirement, or visibly contradicts it.
- partial: there is visible, directionally correct evidence, but it is incomplete, ambiguous,
  weak, approximate, or not fully realized.
- yes: the requirement is clearly and sufficiently satisfied.

Use the SOURCE image only to establish the before-state. Return exactly one compact JSON
object and nothing else:
{{"label":"no|partial|yes","rationale":"brief visible evidence for this requirement only"}}
```

### 26.5 Strict-fidelity leaf

Source: `run/aurora_prompt_tree.py`, constant `FIDELITY_LEAF`.

```text
You are the strict fidelity-audit leaf for one image-edit requirement.
Evaluate ONLY whether the visible result realizes this requirement completely and precisely.
Actively look for semantic shortfalls. Do not score unrelated content or overall quality.

Focused requirement ({role}, {kind}): {text}

Choose:
- no: the requirement is absent, contradicted, applied to the wrong target, or has no credible
  visible evidence.
- partial: the intended effect is recognizable, but any meaningful part is incomplete,
  approximate, ambiguous, weak, misplaced, or not visibly demonstrated.
- yes: the full requirement is clearly and unambiguously realized with no meaningful semantic
  shortfall.

For contact, holding, motion, and spatial relationships, require the requested state to be
visibly demonstrated; proximity or a plausible pose alone is partial. For a color or attribute
change, require the full target to have the requested attribute. Return JSON only:
{{"label":"no|partial|yes","rationale":"the strongest visible fidelity evidence"}}
```

### 26.6 Collateral-preservation leaf

Source: `run/aurora_prompt_tree.py`, constant `PRESERVATION_LEAF`.

```text
You are the collateral-change leaf in a prompt-tree evaluator.
Evaluate ONLY semantic changes outside the requested target/effect by comparing SOURCE and
EDITED. Do not judge whether the requested edit succeeded. Ignore style, realism, blur, text
artifacts, and low-level quality unless they change semantic content.

Choose:
- no: the scene/main subject is replaced or unrecognizable, the wrong subject is edited, or
  identities/shapes of multiple important non-target objects are replaced.
- partial: the same scene and object identities remain recognizable, but at least one clear
  unintended attribute, color, count, position, or extra-object change exists.
- yes: important non-target content remains semantically intact; only the requested target
  and effect changed.

Return exactly one compact JSON object and nothing else:
{"label":"no|partial|yes","rationale":"brief preservation evidence only"}
```

### 26.7 Label-evidence leaf template

Source: `run/aurora_label_prompt_tree.py`, function `compile_label_support_leaf()`.
`{candidate_label}` is one of `no`, `partial`, or `yes`; `{criteria}` is one bullet per boundary
condition; `{ties}` is one bullet per matching tie rule or `- No additional tie rule.`.

```text
You are one independent evidence leaf in an ordinal image-edit judge.
Evaluate ONLY how strongly the visible SOURCE/EDITED evidence supports this proposition:

    The overall satisfaction category is {candidate_label.upper()}.

Criteria for this proposition:
{criteria}

Relevant boundary guidance:
{ties}

Do not choose among no/partial/yes categories and do not evaluate another category's rubric.
Instead return a 0/1/2 support score encoded with these tokens:
- no = 0, visible evidence does not support this proposition.
- partial = 1, evidence gives mixed, ambiguous, or incomplete support for this proposition.
- yes = 2, visible evidence strongly and clearly supports this proposition.

Use only visible semantic evidence. Return exactly one compact JSON object and nothing else:
{{"label":"no|partial|yes","rationale":"brief evidence for this proposition only"}}
```

### 26.8 Fixed structured-prompt wrapper

`compile_structured_prompt()` serializes the spec using
`json.dumps(spec, ensure_ascii=False, indent=2, sort_keys=True)` and inserts it into:

```text
You are a vision-language judge. Execute the structured semantic decision policy below in its listed order. Use only visible evidence from the SOURCE and EDITED images and the supplied edit instruction. Do not invent, remove, or reorder criteria.

<semantic_decision_policy>
<sorted, indented JSON specification>
</semantic_decision_policy>

Return exactly one compact JSON object and nothing else:
{"label":"no|partial|yes","rationale":"brief condition-by-condition image evidence"}
```

### 26.9 GEPA reflective-record template

For each captured focal or optional anchor trajectory, GEPA receives a record shaped as:

```text
Inputs:
  instruction: <exact instruction>
  role: focal|anchor

Generated Outputs:
  label: <prediction or invalid>
  rationale: <judge rationale>

Feedback:
  Target label: <human target>. This is the <role> example. <outer feedback>
  Revise a reusable semantic-consistency decision boundary; never copy the instruction,
  identify the item/model, or prescribe this answer.
```

The third-party TextGrad optimizer instruction is supplied by `textgrad==0.1.8`; exact
reconstruction therefore requires that pinned package version in addition to the local adapter
and constraints recorded above.
