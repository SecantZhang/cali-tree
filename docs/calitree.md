# Cali-Tree image-judge calibration

This implementation translates the five-page *Cali-Tree: Hierarchical Calibration for VLM
Judges* demo paper into VEJudge's workflow system. The paper specifies the construction
stages and the 179-task, three-repeat evaluation, but not its exact clustering thresholds,
merge acceptance threshold, optimizer step limit, routing rule, split manifests, or original
Gemma checkpoint. Those values are therefore explicit, versioned configuration rather than
claims of exact paper reproduction.

## Public data setup

Install the optional dependencies and materialize the public assets:

```bash
pip install -e '.[calitree]'
./run/setup_imagenhub.sh
```

The resumable setup pins ImagenHub's `filtered` split to revision
`a393c006cd0c843d8ca57ae4a6ee954ee376ef67`, downloads the eight editor output sets actually
published in ImagenMuseum and the three official human-rating TSVs, and writes a SHA-256
manifest. The ratings have a ninth `Imagic` column, and the loader accepts locally supplied
Imagic assets, but the cited public repository contains no Imagic output directory.

Setup also writes task-grouped splits for seeds 42, 43, and 44. Each split contains 29
training tasks and 150 test tasks; all eight public outputs for a task stay together, giving
232 train and 1,200 test cases (1,432 total). Set `VEJUDGE_IMAGENHUB_ROOT` to use a
non-default location.

The source material is:

- <https://huggingface.co/datasets/ImagenHub/Text_Guided_Image_Editing>
- <https://github.com/ChromAIca/ChromAIca.github.io>
- <https://github.com/TIGER-AI-Lab/ImagenHub/tree/main/eval/human_ratings/Text-Guided_IE>

Semantic Consistency (SC) is the target. The median of the three raters maps `0`, `0.5`, and
`1` to `no`, `partial`, and `yes`; Perceptual Quality (PQ) remains attached as provenance.

An independent zero-shot validation track uses the public
[EditInspector benchmark](https://github.com/editinspector/EditInspector), pinned to commit
`e18cd6b6b80311d8514787618c2a6cbebff563ef`. Its 783 MagicBrush edits have three human
ratings and a published four-level instruction-accuracy target. The mapping was frozen
before inference: `0 → no`, `1 → partial`, and `2/3 → yes`. Level 2 is grouped with `yes`
because the official benchmark calls it “Accurate But Unexpected” and its published binary
accuracy field normally treats levels 2 and 3 as accurate.

Materialize a deterministic class-stratified subset with:

```bash
VEJUDGE_EDITINSPECTOR_ROOT=/path/to/editinspector \
  ./run/setup_editinspector.sh --ratio 0.1 --seed 44
```

The 10% slice contains 80 frozen development cases. Expanding the same seed to `--ratio
0.5` produces a strict nested sample with those same 80 cases plus 312 confirmation
cases. These 392 cases are now the calibration half. Expanding to `--ratio 1.0` preserves
that half and adds the final 391 cases, whose labels and predictions have not been used to
choose the two-cutpoint model described below. The setup downloads source/edited images
resumably, stores the three individual ratings, and hashes the pinned CSV, metadata, and
every selected image. Graph execution never downloads implicitly.
`workflows/examples/rubric_lite_editinspector_zero_shot.json` loads the frozen ImagenHub
Rubric-Lite artifact with the verifier disabled and its model field blank. The reproducible
CLI defaults to a no-call dry run:

```bash
./run/run_editinspector_rubric_lite.sh \
  --partition confirmation --disable-boundary \
  --model gpt-4.1-mini

./run/run_editinspector_rubric_lite.sh \
  --partition confirmation --disable-boundary \
  --live --model gpt-4.1-mini
```

## Workflow

Load `workflows/examples/calitree_imagenhub.json`. Its judge model, optimizer model, and
embedding model are deliberately blank. Live execution returns an error until each is
configured explicitly; no provider or model is selected silently.

The graph uses:

- `imagenhub_source` to emit image samples and raw labels.
- `dataset` to sample once and join the connected labels by item ID.
- `calitree_train` to train leaves, merge the hierarchy, run matched-budget baselines, and
  emit the prompt tree plus diagnostics.
- `calitree_judge` to semantically route samples through the validated hierarchy.
- `calitree_eval` to report overall, split, per-editor, confusion, and distribution metrics.

Dry runs do not download data or call models. The source reports expected counts, and the
training node reports expected calls and the optimizer completion-token budget.

## Algorithm defaults

Prompt templates live under `vejudge/core/prompts/templates/calitree_v1/` through
`calitree_v4/`; v2 is the default and separates the ImagenHub Semantic Consistency target
from standalone Perceptual Quality. V3's four-field decomposition and v4's single
fulfillment field remain explicit experimental alternatives after underperforming v2 in
small live comparisons. Leaf prompts use
official `textgrad==0.1.8` for at most three updates, stopping early when correct or when the
shared completion-token cap is exhausted. TextGrad's own optimizer prompt is supplied by the
pinned package; VEJudge versions the task-specific gradient context and output constraints.

The `split_label_stratified` sampling mode preserves the official train/test boundary and
exposes independent train/test sampling ratios. With `group_by_task=true`, sampling is by
task UID, so all eight editor outputs stay together and there is zero task leakage. A
deterministic `test_group_offset` rotates the ordered held-out groups; at a `0.5` ratio,
offsets `0` and `1` are exact, disjoint 75-task halves. A task-grouped subset of the official
training side is reserved as an internal merge guard.

Leaf optimization groups the eight editor outputs for each task into one joint leaf, rather
than fitting one prompt to one image. Instructions are also preprocessed into target-blind
operation families such as add, remove, color, spatial, replacement, and style. The first
two merge levels require semantic-family compatibility before the component embedding is
considered.

The component extractor returns criteria, priorities, and constraints. Normalized components
are embedded with the required configured embedding model. Active nodes are greedily paired
using true complete-link cosine similarity, starting at `0.90`, relaxing `0.05` per level,
and stopping at `0.70`. A rejected pair is not retried at later thresholds. Merge prompts are
checked for semantic conflict, covered-case accuracy, and balanced task-grouped
internal-validation generalization before acceptance:

- `100%` covered-case accuracy: full merge.
- `>=80%`: partial merge; correct cases stay on the parent and incorrect original leaves are
  promoted.
- `<80%`: reject without replacing the children.
- incompatible criteria: retain separate branches.

Equivalent unoptimized prompts that already fail the shared generalization guard are pruned
without repeating image judgments, and at most 20 merge candidates are attempted by
default. Routing embeds only inference-time information (instruction and editor family),
never the target. Unseen cases start at the initial or TextGrad global root selected on the
internal validation slice and descend while a supported child centroid clears its calibrated
threshold. Unsupported one-case leaves require a near-exact match; otherwise routing stays
at the nearest validated ancestor.

Final classification uses a target-blind three-way consensus among the initial rubric,
matched-budget global TextGrad rubric, and an independent image critic. A strict majority
wins; total three-way disagreement maps to `partial` as the uncertainty class. Candidate
patterns may be calibrated by a hierarchy of global, operation, editor, and
editor-operation rules. Rule capacity is chosen only on the task-grouped internal validation
slice, then refit on the official training partition. An optional editor prior requires at
least 20 cases and a 98% empirical majority before it can override consensus.

For noisy human labels, `calibration_agreement_filter=unanimous` fits calibration rules and
editor priors only on training cases where all three official SC raters agree; disputed
cases remain in the reported train/test metrics. The selective operating point is also
deployable without test labels: it accepts only three-way-unanimous predictions from editors
whose consensus accuracy clears a configured threshold on the filtered training partition.
The default requires 10 supported training cases and 85% training accuracy. Every candidate,
override, abstention decision, and fitted editor reliability is retained for audit.

All successful judgments, component extractions, embeddings, prompt updates, and merge
decisions are checkpointed. Image judgments run at the configured engine concurrency.
Training stores prompt-hashed predictions in the tree so an immediately downstream route
node can reuse identical judgments without another billable or nondeterministic model call.
The workbench uses the global stop/resume controls and shows the tree, prompts/components,
timeline, usage, raw and balanced baseline accuracy, confusion matrices, per-editor metrics,
running accuracy, and source/edited image cases.

The initial-rubric and global-TextGrad baselines use the same configured optimizer
completion-token cap as Cali-Tree:

```text
max_steps * training_case_count * optimizer.max_tokens
```

With defaults this is three passes over the training-case count. Real gateway calls still
require the interface's live-run confirmation and are recorded in the run-scoped
`llm-histories.log`; TextGrad's auxiliary log is confined to that same experiment directory.

## Prompt-version comparison

`calitree_v1` through `calitree_v4` are versions of the complete prompt bundle: initial
rubric, TextGrad feedback, component extraction, and merge synthesis. They are not four
independently frozen versions of the entire Python algorithm. Tree guards and consensus
features evolved while the prompt experiments were running, so configuration differences
are called out below.

| Version | Decision representation | Main intended improvement | Observed issue |
|---|---|---|---|
| v1 | Generic `no` / `partial` / `yes` rubric | Simple image-edit success plus preservation | Mixes semantic consistency with visible quality and has weak class boundaries |
| v2 | Explicit semantic conditions and `no↔partial↔yes` tie breaks | Match ImagenHub SC; exclude standalone perceptual quality | Still depends on free-form label generation |
| v3 | Four fields: requested change, subject, spatial relation, scene continuity | Make conflicts and label resolution deterministic and auditable | More schema/prompt complexity; merge attempts all failed in the small run |
| v4 | One `none` / `partial` / `full` fulfillment field mapped directly to the label | Reduce output complexity while retaining visible-evidence boundaries | Over-predicts partial/yes on the dominant `no` class |

The most comparable prompt experiment used the exact same three training cases and eleven
test cases for v2, v3, and v4. The archived v1-era corrected run also used 3/11 cases, but
used the earlier unified sampler: its training set contained only `no` labels and its test
items differ. V4 additionally used one optimization step, disabled warm start, and disabled
the conflict resolver, so its row is not a pure prompt-only ablation.

### Accuracy and class metrics on the small version runs

Balanced accuracy is the mean recall over the represented `no`, `partial`, and `yes`
classes. V1 did not persist it directly; the value below is reconstructed from its complete
confusion matrix.

| Version | Initial test | TextGrad test | Cali-Tree train | Cali-Tree test | Balanced test | Recall no | Recall partial | Recall yes |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| v1-era | 63.64% | 63.64% | 100.00% | 63.64% | 58.33% | 75.00% | 0.00% | 100.00% |
| v2 | 63.64% | 54.55% | 100.00% | 63.64% | 55.56% | 66.67% | 100.00% | 0.00% |
| v3 | 63.64% | 63.64% | 66.67% | 63.64% | 55.56% | 66.67% | 0.00% | 100.00% |
| v4 | 54.55% | 54.55% | 100.00% | 54.55% | 81.48% | 44.44% | 100.00% | 100.00% |

The v4 balanced score is unstable: the eleven-case test set has nine `no` cases but only one
`partial` and one `yes`. Correctly predicting the two minority cases while missing five
`no` cases yields high balanced accuracy but lower ordinary accuracy.

### Confusion matrices and prediction distributions

Each confusion entry is `target → [predicted no, partial, yes]`.

| Version | Target no | Target partial | Target yes | Predicted distribution `[no, partial, yes]` |
|---|---|---|---|---|
| v1-era | `[6, 2, 0]` | `[0, 0, 2]` | `[0, 0, 1]` | `[6, 2, 3]` |
| v2 | `[6, 2, 1]` | `[0, 1, 0]` | `[0, 1, 0]` | `[6, 4, 1]` |
| v3 | `[6, 2, 1]` | `[0, 0, 1]` | `[0, 0, 1]` | `[6, 2, 3]` |
| v4 | `[4, 2, 3]` | `[0, 1, 0]` | `[0, 0, 1]` | `[4, 3, 4]` |

### Cali-Tree test accuracy by editor

The editor composition differs for v1. A dash means that editor was absent from the
v2/v3/v4 eleven-case test set.

| Editor | v1-era | v2 | v3 | v4 |
|---|---:|---:|---:|---:|
| CycleDiffusion | 0.00% (2) | 66.67% (3) | 66.67% (3) | 0.00% (3) |
| DiffEdit | 100.00% (1) | 100.00% (2) | 100.00% (2) | 100.00% (2) |
| InstructPix2Pix | 50.00% (2) | 0.00% (2) | 50.00% (2) | 50.00% (2) |
| MagicBrush | 100.00% (1) | 100.00% (1) | 0.00% (1) | 100.00% (1) |
| Pix2PixZero | 100.00% (1) | — | — | — |
| Prompt2prompt | 50.00% (2) | — | — | — |
| SDEdit | 100.00% (1) | 50.00% (2) | 50.00% (2) | 50.00% (2) |
| Text2Live | 100.00% (1) | 100.00% (1) | 100.00% (1) | 100.00% (1) |

### Tree construction and model usage

| Version | Accepted / rejected merges | Specialized roots | Judge calls | Optimizer calls | Embedding calls | Total tokens |
|---|---:|---:|---:|---:|---:|---:|
| v1-era | 2 / 0 | not recorded | 28 | 4 | 16 | 35,718 |
| v2 | 2 / 0 | 1 | 50 | 7 | 5 | 65,807 |
| v3 | 0 / 3 | 3 | 50 | 14 | 3 | 95,613 |
| v4 | 2 / 0 | 1 | 17 | 4 | 4 | 31,269 |

The small-run evidence selects v2 as the default: it tied v3 on ordinary test accuracy,
successfully merged its leaves, and was materially cheaper. V4's simpler output was cheaper
but reduced ordinary accuracy, while its high balanced score rests on two minority examples.
These runs are useful diagnostics, not a statistically adequate ranking.

### Large-scale report for the selected v2 system

Only v2 was advanced to the full 1,200-case, 150-task held-out evaluation. These figures
include the later task-level tree, consensus calibration, unanimous-label preprocessing,
and editor-reliability selective policy; they should not be attributed to prompt wording
alone.

| Metric | N / coverage | Accuracy | Balanced | Recall no | Recall partial | Recall yes | 95% grouped-task accuracy CI |
|---|---:|---:|---:|---:|---:|---:|---:|
| Initial rubric | 1,200 / 100% | 78.25% | 59.81% | 86.90% | 30.37% | 62.16% | 75.67–80.92% |
| Global TextGrad | 1,200 / 100% | 77.75% | 58.59% | 86.69% | 29.63% | 59.46% | 75.17–80.42% |
| Cali-Tree v2 | 1,200 / 100% | 82.83% | 60.41% | 93.29% | 26.67% | 61.26% | 80.67–84.92% |
| Selective Cali-Tree v2 | 771 / 64.25% | 92.87% | 60.07% | 98.02% | 8.11% | 74.07% | 91.04–94.58% |

The selective result is optimized for high-confidence accuracy, not macro recall. In
particular, it accepts only 37 human-`partial` cases, so its low partial recall must be shown
alongside the 92.87% headline.

| v2 report slice | N | Accuracy | Balanced accuracy |
|---|---:|---:|---:|
| Cali-Tree, unanimous human ratings | 940 | 90.53% | 61.89% |
| Cali-Tree, disputed human ratings | 260 | 55.00% | 54.27% |
| Selective, unanimous human ratings | 683 | 96.63% | 61.13% |
| Selective, disputed human ratings | 88 | 63.64% | 55.92% |

The source reports are:

- v1-era: `logs/exps/260727-15:19:26-exps/calitree_train.json`
- v2 small comparison: `logs/exps/260728-01:28:26-exps/calitree_train.json`
- v3 small comparison: `logs/exps/260728-01:16:18-exps/calitree_train.json`
- v4 small comparison: `logs/exps/260728-01:32:41-exps/calitree_train.json`
- v2 combined evaluation:
  `logs/exps/260728-14:29:10-exps/calitree_combined_1200_summary.json`

## Live validation

The current evaluation uses `gpt-4.1-mini` for judging and optimization and
`text-embedding-3-small` for routing. Training is no longer subsampled with the test set:
every run uses all 232 cases from the 29 official training tasks. The test ratio controls
only the 1,200-case official held-out partition.

The 10% development run evaluated 120 cases from 15 held-out tasks:

- Initial rubric: `78.33%`.
- Global TextGrad: `80.00%`.
- Cali-Tree: `85.00%`, grouped-task bootstrap 95% interval `77.50–92.50%`.
- Human-unanimous cases: `92.78%` on 97 cases; disputed cases: `52.17%` on 23.
- Three-way-unanimous predictions: `91.35%` at `86.67%` coverage.

Artifacts are under `logs/exps/260728-12:15:48-exps/`.

The first 50% development half uses offset `0`: 600 cases from 75 held-out tasks. Fitting
the consensus calibrator and editor prior only on the 181 human-unanimous training cases
produced:

- Initial rubric: `78.67%`; global TextGrad: `77.83%`.
- Cali-Tree: `82.50%`, balanced accuracy `58.95%`, grouped-task bootstrap 95% interval
  `79.67–85.50%`.
- Human-unanimous cases: `91.86%` on 467; disputed cases: `49.62%` on 133.
- The fixed selective policy: `92.42%` at `66.00%` coverage (396/600), with balanced
  accuracy `60.87%`.

The 50% development results selected the selective editor-reliability threshold and are not
an untouched publication claim. Offset `1` is the disjoint 75-task confirmation half; its
configuration was frozen before reading its outcomes:

- Full-coverage Cali-Tree accuracy: `83.17%`, balanced accuracy `61.13%`, grouped-task
  bootstrap 95% interval `80.17–86.17%`.
- Fixed selective policy: `93.33%` on 375/600 cases (`62.50%` coverage), balanced accuracy
  `60.63%`, grouped-task bootstrap 95% interval `90.79–95.62%`.
- The accepted subset is `96.12%` accurate on 335 human-unanimous cases and `70.00%` on
  40 disputed cases.

Across both disjoint halves—all 1,200 cases and 150 official held-out tasks—the fixed policy
is `92.87%` accurate on 771 accepted cases (`64.25%` coverage), with grouped-task bootstrap
95% interval `91.04–94.58%`. Full-coverage Cali-Tree accuracy is `82.83%` versus `78.25%`
for the initial rubric and `77.75%` for global TextGrad.

The large accuracy gap between unanimous and disputed annotations is reported explicitly:
reaching 90% on the unfiltered median target would require resolving cases where the three
human raters themselves do not agree, while the selective result is a deployable
judge-with-abstention operating point. Development artifacts are under
`logs/exps/260728-13:48:13-exps/`; confirmation and combined metrics are under
`logs/exps/260728-14:29:10-exps/`.

## Rubric-Lite: the promoted simple architecture

### Why the hierarchy is not the deployment recommendation

The large held-out experiment shows that prompt-tree routing is not the main source of the
reported gain. On the same 1,200 cases, the routed tree prediction before consensus and
editor-prior resolution was `77.58%` accurate, below the fixed v2 initial rubric at `78.25%`.
The complete Cali-Tree reached `82.83%` only after three global judgments plus a fitted
editor prior. Its `92.87%` result is selective: it abstains on `35.75%` of cases. This does
not justify task leaves, embeddings, semantic clustering, merge synthesis, routing
thresholds, and promoted branches as the default full-coverage system.

The partial class is principally a decision-boundary problem. Full Cali-Tree v2 predicted
`partial` 94 times over 1,200 held-out cases, with precision `38.30%`, recall `26.67%`, and
F1 `31.50%`. More routing did not make the semantic boundary reliable.

### Final graph

The promoted path is `Rubric-Lite v4 + Partial Progress Verify`:

```text
SOURCE + EDITED + instruction
  -> one global v4 rubric call
  -> [change evidence, specification fidelity, source preservation]
  -> minimum score + two train-fitted global cutpoints
  -> no / partial / yes
  -> only if the result is yes: one partial-progress verifier call
  -> final no / partial / yes
```

There is no prompt tree, embedding model, clustering, merge operation, TextGrad optimizer,
critic ensemble, editor feature, task ID, or per-instruction learned prompt. The second call
is conditional and was used for `51 / 600 = 8.5%` of confirmation cases.

The primary v4 rubric produces three `0..100` visual-evidence scores:

1. `change_evidence`: whether a requested source-to-edited delta is visibly present;
2. `specification_fidelity`: exact identity, count, container, relation, removal, and
   residual constraints;
3. `source_preservation`: whether the result remains a local edit of the source scene.

The evidence score is their minimum. Two cutpoints are fitted on official training tasks
only, with a nonzero-recall constraint for every represented class. The deployment cutpoints
are `75.000001` and `89.000001`. These are global scalar parameters, not dataset/editor
lookup rules.

The partial-progress verifier was learned from the failure pattern of the earlier condition
rubric. That rubric treated *any* unsatisfied subcondition as `no`. The new rubric instead
uses this deterministic evidence rule:

```text
zero recognizable requested progress                         -> no
all requested conditions visibly exact                       -> yes
some recognizable requested progress, but not everything exact -> partial
```

It decomposes the instruction into atomic visible conditions and records
`none|partial|full`, requested-delta presence, intended-subject correctness, and scene
continuity. Code derives the label from those fields, so a free-form label cannot contradict
the evidence. Of 27 small global fusion policies, the policy selected on 232 training cases
and a task-disjoint 120-case development slice was: retain v4 `no` and `partial`; rejudge
only v4 `yes` and accept the verifier result. The policy does not inspect an editor or task.

### Version results

All development runs used the official 232-case training partition plus 120 held-out
outputs from 15 offset-0 tasks. All confirmation results use the disjoint 600 outputs from
75 offset-1 tasks. The image judge was `gpt-4.1-mini`, temperature `0`.

| Version | Development accuracy | Development partial P / R / F1 | Main finding |
|---|---:|---:|---|
| v1 condition evidence | 76.67% | 55.56 / 35.71 / 43.48% | Better partial F1, inadequate overall accuracy |
| v2 three-view vote | 73.33% | 25.00 / 14.29 / 18.18% | Voting reduced both accuracy and partial quality |
| v3 ordinal scores | 83.33% | 41.94 / 92.86 / 57.78% | High partial recall but erased `yes`; rejected |
| v4 class-preserving ordinal | 86.67% | 62.50 / 35.71 / 45.45% | Passed development gate; one global call |
| v4 + broad v1 verifier | 87.50% | 61.54 / 57.14 / 59.26% | Promising on development, failed confirmation |
| **v4 + yes-only partial-progress verifier** | **88.33%** | **66.67 / 42.86 / 52.17%** | Selected simple policy |

The broad v1 verifier is a useful negative control. On the 600-case confirmation set it
changed v4 from `82.17%` to `79.67%` accuracy and partial F1 from `29.51%` to `29.33%`.
Raising recall by broadly predicting partial destroyed precision; it is not promoted.

### Frozen 600-case confirmation

| Metric | v4 primary | v4 + partial-progress verify | Delta |
|---|---:|---:|---:|
| Accuracy | 82.17% | **82.33%** | +0.17 pp |
| Balanced accuracy | 57.18% | 57.00% | -0.18 pp |
| Macro F1 | 58.56% | **58.78%** | +0.22 pp |
| Partial precision | 28.13% | **28.17%** | +0.04 pp |
| Partial recall | 31.03% | **34.48%** | +3.45 pp |
| Partial F1 | 29.51% | **31.01%** | +1.50 pp |
| Yes recall | 47.06% | 42.65% | -4.41 pp |
| Calls beyond primary | 0 | 51 | +8.5% |

The final confusion matrix is:

| Human target | Predicted no | Predicted partial | Predicted yes |
|---|---:|---:|---:|
| no | 445 | 24 | 5 |
| partial | 30 | 20 | 8 |
| yes | 12 | 27 | 29 |

The 95% grouped-task accuracy interval is `79.00–85.17%`. A paired 10,000-repeat
task bootstrap gives an accuracy-delta interval of `-0.83 to +1.17` percentage points and
a partial-F1-delta interval of `-1.77 to +6.02` points. The verifier changed nine cases,
corrected four, and regressed three; exact McNemar `p=1.0`. The observed gain is therefore
small and not statistically established. It should be described as a promising,
cost-efficient partial-boundary refinement, not a 90% or publishable accuracy result.

The simple path is nevertheless the better engineering default for full coverage:
`82.33%` is only `0.50` points below complete Cali-Tree v2's `82.83%`, while removing the
hierarchy and replacing three global judgments with one primary call plus an 8.5% conditional
second pass. The selective Cali-Tree result remains appropriate only when abstention is
acceptable.

### External generalization: EditInspector

Cross-dataset validation is now complete, and it changes the conclusion. The frozen
ImagenHub v4 rubric does **not** generalize as a full-coverage three-class classifier, but
its strict perfect-evidence operating point does generalize as a high-precision selective
`yes` detector.

The deployed selective rule is target-blind and contains no dataset/editor lookup:

```text
accept iff calibrated label == yes and
           min(change_evidence, specification_fidelity, source_preservation) == 100
otherwise abstain
```

This rule is stored in `rubric_lite_v4_imagenhub.json`. A score of 100 already means all
three v4 dimensions are visibly exact; no EditInspector label was used to alter the prompt,
score, or accepted prediction. The 80-case development slice was used only as the gate for
advancing the frozen rule to the disjoint confirmation partition.

| External split | N | Full accuracy | Balanced | Partial P / R / F1 | Selective accepted | Coverage | Selective accuracy | 95% accepted-accuracy CI |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 10% development | 80 | 60.00% | 65.99% | 10.53 / 40.00 / 16.67% | 40 | 50.00% | 100.00% | 91.24–100% Wilson |
| Untouched confirmation | 312 | 58.65% | 51.95% | 4.23 / 15.79 / 6.67% | 168 | 53.85% | **97.62%** | **94.04–99.07% Wilson** |

The confirmation task-bootstrap interval for selective accuracy is `95.24–99.40%`. Its
168 accepted cases contain 164 human-`yes`, three human-`no`, and one human-`partial`
case. All 153 accepted cases with unanimous human ratings are correct; the 15 disputed
accepted cases are `73.33%` accurate. This passes the predeclared `>=90%` selective gate,
but it is not balanced three-class success: the accepted set predicts only `yes`, and
full-coverage accuracy is far below the external majority baseline.

The partial verifier also failed to transfer. Rejudging the 40 primary-`yes` development
cases changed three correct `yes` predictions to `partial`, reducing accuracy from `60.00%`
to `56.25%`. Reusing the primary checkpoints and applying the verifier to the 40 primary
`no/partial` cases improved ordinary accuracy to `70.00%`, but balanced accuracy fell to
`59.71%` and partial F1 remained `17.39%`. Neither policy was advanced to confirmation.
Across both development experiments, exactly 160 paid calls were made: 80 primary calls and
one verifier call for each of the 80 cases. The untouched confirmation used exactly 312
primary calls, zero verifier, optimizer, or embedding calls, and 729,567 total tokens.

Therefore the publishable statement is narrow: **a one-call, target-blind perfect-evidence
abstention rule transfers to a different image-edit dataset at 97.62% accuracy and 53.85%
coverage.** It does not establish full-coverage 90% accuracy, cross-dataset no/partial
calibration, or a solution to the partial boundary. The next research target should be a
separately validated high-confidence no/partial rule, not more tree routing.

### Two-cutpoint domain adaptation: the next frozen candidate

The external full-coverage result also shows that adding another prompt tree is the wrong
complexity. Rubric-Lite v4 already emits a single interpretable scalar: the minimum of its
three visible-evidence scores. The new domain-adaptation model learns only two global
cutpoints on that scalar:

```text
score < 25.000001             -> no
25.000001 <= score < 75.000001 -> partial
score >= 75.000001            -> yes
```

There are no prompt leaves, embeddings, semantic clusters, merge rules, routers, editor
identities, instruction features, or second model calls. Fitting enumerates the finite
cutpoints immediately above observed scores, rejects candidates that fail the configured
minimum recall for a represented class, and selects macro F1. Five-fold stratification is
deterministic (`seed=44`), and every out-of-fold prediction is made by cutpoints fitted
without that case's label.

The complete 392-case calibration half has 26 `no`, 24 `partial`, and 342 `yes` cases:

| Candidate on calibration half | Accuracy | Balanced | Macro F1 | Partial precision | Partial recall | Partial F1 |
|---|---:|---:|---:|---:|---:|---:|
| Frozen ImagenHub v4 cutpoints | 58.93% | 55.03% | 39.87% | 5.56% | 20.83% | 8.77% |
| Raw model label | 63.52% | 57.20% | 43.02% | 13.79% | 83.33% | 23.67% |
| **Two cutpoints, 5-fold out of fold** | **81.12%** | **68.03%** | **58.22%** | **25.45%** | **58.33%** | **35.44%** |

All five folds independently selected the same `25.000001 / 75.000001` pair, as did the
deployment fit on all 392 calibration cases. This is evidence of threshold stability, not
an untouched test result: the old 312-case “confirmation” partition is part of model
selection in this iteration and must no longer be described as confirmation for this
candidate. The accuracy is still below 90%, but partial F1 is more than four times the
frozen cross-dataset value while using the smallest plausible calibration model.

#### Partial-label reliability and rejected soft-label calibration

The official target is a useful benchmark label, but `partial` is not a cleanly agreed
class in EditInspector. The new evaluation report preserves the usual hard-label metrics
and also measures the individual SC ratings. `modal_rater_agreement_ceiling` means the
maximum expected agreement with a randomly selected rater if an item-specific oracle
always chose the modal rating; it is not a ceiling on accuracy against the released target.
`prediction_expected_rater_agreement` is the fraction of individual raters agreeing with
the model prediction, averaged over cases.

| EditInspector target | N | Unanimous ratings | Majority supports target | Mean entropy (bits) | Modal-rater ceiling |
|---|---:|---:|---:|---:|---:|
| no | 26 | 38.46% | 84.62% | 0.642 | 75.64% |
| **partial** | **24** | **8.33%** | **66.67%** | **1.008** | **61.11%** |
| yes | 342 | 87.43% | 99.42% | 0.119 | 95.61% |
| all | 392 | 79.34% | 96.43% | 0.208 | 92.18% |

Only two of the 24 `partial` targets have three matching ratings. On the 81 disputed
items, the two-cutpoint model has 61.73% accuracy and 58.33% partial F1. On the 311
unanimous items it has 86.17% accuracy, but the unanimous subset contains only two
`partial` cases, neither predicted correctly. The model's expected agreement with one
randomly selected human rater is 78.49% overall and 48.61% on `partial` targets. This does
not excuse errors against the released label; it identifies partial as both a visual
decision-boundary problem and a human-label-reliability problem.

The same effect exists, but is weaker, in the 1,432 ImagenHub cases: 31.52% of the 165
`partial` targets are unanimous and 84.24% have majority support, compared with only 8.33%
and 66.67% on EditInspector. Dataset-specific partial definitions therefore remain a
material cross-dataset generalization risk.

Several compact probabilistic alternatives were evaluated from the same three v4 scores.
The important comparison is fully nested five-by-four-fold validation: model family,
regularization, class weights, and the partial probability threshold were selected only
inside each outer training fold.

| Calibration model | OOF accuracy | Balanced | Macro F1 | Partial P / R / F1 |
|---|---:|---:|---:|---:|
| **Two scalar cutpoints** | 81.12% | **68.03%** | **58.22%** | 25.45 / **58.33** / **35.44%** |
| Nested soft-rater multinomial | **85.46%** | 58.28% | 56.54% | 28.00 / 29.17 / 28.57% |
| Nested partial-F1-selected multinomial | 84.95% | 58.29% | 56.54% | **29.03** / 37.50 / 32.73% |

The soft-label models improved ordinary accuracy by following the dominant `yes` class,
but reduced balanced accuracy and leakage-safe partial F1. A fixed balanced logistic
variant reached 39.39% partial F1 in a non-nested exploratory run, but its minority gain
did not survive nested selection or the historical 80-to-312 transfer. It is therefore
not added to the runtime. This negative result is important: the deployed candidate
remains one rubric call plus two cutpoints, while the evaluator now makes label ambiguity
explicit instead of hiding it behind one accuracy number.

The frozen artifact is
`vejudge/core/calibration/artifacts/rubric_lite_v4_editinspector_cutpoints_v1.json`.
`rubric_lite_fit` learns and reports the same two values generically;
`rubric_lite_apply` applies them without a model call. The fully wired fit/apply graph is
`workflows/examples/rubric_lite_editinspector_calibrated.json`. For the pending final
evaluation, `workflows/examples/rubric_lite_editinspector_final.json` loads the frozen
artifact and evaluates only the final 391 cases, so the 392 calibration judgments are not
billed again. Both workflow engine model fields are intentionally blank.

#### Generalization audit and v5 rubric-learning negative result

The tempting 89.80% calibration-half rule was not promoted. It used four exact score
patterns discovered on EditInspector and reached 42.86% partial F1 there, but applying it
unchanged to the existing 600-case ImagenHub holdout collapsed to 54.83% accuracy and 8.70%
partial F1. A simpler `specification_fidelity` rule also fell to 71.83% accuracy and 9.09%
partial F1. These are direct evidence that hand-coded score-pattern rules overfit the label
schema even when they never use dataset or editor identity.

The global two-cutpoint design is more stable. On that same 600-case ImagenHub holdout, the
EditInspector `25/75` pair gives 75.50% accuracy, 63.94% balanced accuracy, and 23.29%
partial F1, versus 74.50%, 62.52%, and 33.33% for the original ImagenHub pair. It does not
solve partial transfer, but it avoids the catastrophic failure of the richer rule list.
Retrospectively fitting only the 80 EditInspector development cases selected `50/75`; on
the separate 312 cases it gives 80.13% accuracy and 30.30% partial F1. Thus even a small
in-domain calibration sample transfers better than a cross-domain fixed rule, although
this retrospective analysis is no substitute for the untouched final half.

Rubric-Lite v5 tested whether a better partial definition could provide the missing signal
without a tree or a second pass. It replaced fuzzy severity scores with `0/50/100` core
completion states and explicitly ignored generation-quality defects. The 80-call
development run produced:

| Rubric on 80 development cases | Accuracy | Balanced | Macro F1 | Partial P / R / F1 |
|---|---:|---:|---:|---:|
| v4 + development-fitted cutpoints | **80.00%** | **68.65%** | **59.00%** | **50.00 / 40.00 / 44.44%** |
| v5 core completion | 72.50% | 44.35% | 42.41% | 7.14 / 20.00 / 10.53% |

V5 made 80 primary calls, zero verifier/optimizer/embedding calls, and used 178,156 total
tokens. It was not advanced to the 312-case partition. The model converted the leniency
instruction mostly into `yes` predictions rather than separating partial from no. The
version remains available as an explicitly experimental negative control, not a deployment
candidate. Its raw outputs and parser-corrected report are in
`logs/exps/260729-14:20:00-editinspector-rubric-lite-v5-core-exps/`.

The evidence therefore favors the one-call v4 rubric plus two fitted cutpoints. Improving
partial further requires a genuinely stronger visual signal or judge model; adding
score-pattern rules, text classifiers, or another leniency prompt increases complexity
without transferring.

The stronger-judge test is preregistered in
`docs/experiments/rubric_lite_gpt41_editinspector_ab.json`. It changes only
`gpt-4.1-mini` to `gpt-4.1` on the frozen 80-case development partition. Advancement
requires at least a five-point partial-F1 gain while keeping accuracy at or above 78% and
balanced accuracy at or above 66.65%; otherwise the candidate stops before confirmation.

The candidate failed that gate:

| 5-fold OOF model | Accuracy | Balanced | Macro F1 | Partial P / R / F1 | Expected agreement with one rater |
|---|---:|---:|---:|---:|---:|
| gpt-4.1-mini | 80.00% | **68.65%** | **59.00%** | **50.00 / 40.00 / 44.44%** | 77.08% |
| gpt-4.1 | **82.50%** | 59.47% | 57.05% | 25.00 / 40.00 / 30.77% | **79.17%** |
| Candidate delta | +2.50 pp | -9.18 pp | -1.95 pp | -25.00 / 0.00 / **-13.68 pp** | +2.08 pp |

All five candidate folds selected `25.000001 / 50.000001`; all five baseline folds
selected `50.000001 / 75.000001`. The larger model made nine uniquely correct predictions
and seven unique regressions, but concentrated its improvement in the dominant `yes` class.
It used exactly 80 primary calls and 157,387 tokens, with no verifier, optimizer, or
embedding calls. Because partial F1 and balanced accuracy both failed their preregistered
thresholds, no confirmation calls were made. The complete result is
`docs/experiments/rubric_lite_gpt41_editinspector_ab_result.json`.

#### Monotone rubric-feature audit: no replacement for the minimum

The next experiment changed neither the prompt nor the model. It compared 30 convex,
monotone scalar combinations of the three v4 scores on the 392 EditInspector calibration
cases. Each scalar still received only two cutpoints. `specification_fidelity` alone was
best on EditInspector, reaching 82.14% accuracy and 37.84% partial F1 versus 81.12% and
35.44% for the minimum.

That gain did not transfer. The external audit used 600 ImagenHub cases from 75 tasks, with
five balanced folds of exactly 15 tasks and 120 cases each:

| Task-grouped ImagenHub OOF scalar | Accuracy | Balanced | Macro F1 | Partial P / R / F1 |
|---|---:|---:|---:|---:|
| **minimum of three** | **80.83%** | 60.15% | 59.77% | **27.78 / 43.10 / 33.78%** |
| specification fidelity | 77.50% | 59.92% | 56.93% | 26.97 / 41.38 / 32.65% |
| change evidence + preservation | 79.50% | **63.79%** | **60.57%** | 24.10 / 34.48 / 28.37% |

No candidate improves partial F1 on both datasets. The ImagenHub-selected
change/preservation scalar also falls below the minimum when transferred back to
EditInspector: 32.91% versus 35.44% partial F1 and 64.37% versus 68.03% balanced accuracy.
Therefore no learned scalar is added to the runtime, and the frozen final workflow continues
to use the minimum-score artifact.

A preliminary fold allocator kept task groups intact but accidentally left two of five
folds empty. It made specification fidelity appear externally better. The production
allocator now balances both task and label load, tests assert non-empty grouped folds, and
the corrected audit confirms all five ImagenHub folds contain data. The invalid preliminary
result was withdrawn before commit. The corrected negative audit is
`docs/experiments/rubric_lite_monotone_feature_audit.json`.

#### Progress/completion gate and score-information audit

A second two-threshold alternative tested a more direct definition of partial:
`no` when requested-edit progress is below a lower threshold, `yes` when minimum
all-dimension completion clears an upper threshold, and `partial` otherwise. The only
candidate choice was whether progress meant the minimum, mean, or maximum of change
evidence and specification fidelity. The protocol and gate were committed before scores
were inspected.

EditInspector selected the requested-dimension minimum, but it was exactly equivalent to
the existing rule there. On ImagenHub, the fixed definition regressed:

| Task-grouped OOF rule | Dataset | Accuracy | Balanced | Macro F1 | Partial P / R / F1 |
|---|---|---:|---:|---:|---:|
| minimum baseline | EditInspector 392 | 81.12% | 68.03% | 58.22% | 25.45 / 58.33 / 35.44% |
| progress/completion | EditInspector 392 | 81.12% | 68.03% | 58.22% | 25.45 / 58.33 / 35.44% |
| minimum baseline | ImagenHub 600 | 80.83% | 60.15% | 59.77% | 27.78 / 43.10 / 33.78% |
| progress/completion | ImagenHub 600 | 75.83% | 58.21% | 55.90% | 19.82 / 37.93 / 26.04% |

The rule failed every partial-improvement gate and was not implemented. More importantly,
an exact score-tuple audit explains why downstream score engineering keeps failing:

| Score-representation diagnostic | EditInspector | ImagenHub |
|---|---:|---:|
| Cases | 392 | 600 |
| Distinct three-score tuples | 25 | 39 |
| Partial cases | 24 | 58 |
| Partial sharing its entire tuple with `no` or `yes` | **23 (95.83%)** | **55 (94.83%)** |
| Optimistic in-sample modal-tuple accuracy | 90.05% | 85.17% |
| Partial recall at that accuracy-maximizing lookup | **29.17%** | **17.24%** |

The modal-tuple calculation uses all labels and is not held-out performance. It is an
optimistic diagnostic of how much information the representation retains: a deterministic
lookup can maximize ordinary accuracy by assigning each exact tuple its modal class, but
then loses most partial cases. Of the 23 tuples appearing in both datasets, 16 even have
different modal labels; for `[0, 0, 100]`, EditInspector counts are
`no=4 / partial=2 / yes=10`, while ImagenHub counts are
`no=107 / partial=1 / yes=2`.

This changes the research direction. The next experiment does not add another classifier,
router, verifier, or score formula. `rubric_lite_v6` remains one judge call and two
cutpoints, but asks the judge to preserve an at-most-four-condition evidence ledger,
the strongest achieved evidence, the most important missing evidence, a semantic residual
type, and one continuous semantic-completion score. Because its categories were learned
from all 392 calibration cases, those cases are development diagnostics only. The untouched
391-case final partition remains the clean in-domain confirmation. The preregistered
stage-1 gate requires at least 78% accuracy, 66% balanced accuracy, 99% valid schemas, and
a five-point partial-F1 gain over v4 before any final calls.

Artifacts:

- progress/completion protocol:
  `docs/experiments/rubric_lite_progress_completion_gate.json`
- progress/completion result:
  `docs/experiments/rubric_lite_progress_completion_gate_result.json`
- score collision audit:
  `docs/experiments/rubric_lite_score_collision_audit.json`
- v6 evidence-ledger protocol:
  `docs/experiments/rubric_lite_v6_evidence_ledger_ab.json`

The final partition has not been downloaded or judged. Testing it requires expanding setup
to `--ratio 1.0` (roughly another 391 source/edited pairs) and exactly 391 primary judge
calls. Until that happens, this model is a promising calibration-half result, not a
publishable external test result.

Artifacts:

- v4 development: `logs/exps/260729-11:14:03-exps/`
- v4 600-case primary confirmation: `logs/exps/260729-11:33:04-exps/`
- broad-verifier negative control: `logs/exps/260729-12:10:30-exps/`
- partial-progress development: `logs/exps/260729-12:24:54-exps/`
- promoted 51-call confirmation: `logs/exps/260729-12:30:24-exps/`
- paired uncertainty: `logs/exps/260729-12:30:24-exps/paired_task_bootstrap.json`
- EditInspector zero-shot primary + yes-only verifier:
  `logs/exps/260729-12:59:08-editinspector-rubric-lite-exps/`
- EditInspector ambiguous-case verifier:
  `logs/exps/260729-13:04:22-editinspector-rubric-lite-exps/`
- EditInspector no-call selective development report:
  `logs/exps/260729-13:12:30-editinspector-rubric-lite-exps/`
- EditInspector untouched 312-case confirmation:
  `logs/exps/260729-13:22:51-editinspector-rubric-lite-exps/`
- EditInspector v5 core-completion negative control:
  `logs/exps/260729-14:20:00-editinspector-rubric-lite-v5-core-exps/`
- monotone rubric-feature audit:
  `docs/experiments/rubric_lite_monotone_feature_audit.json`
- gpt-4.1 stronger-judge negative control:
  `docs/experiments/rubric_lite_gpt41_editinspector_ab_result.json`
- progress/completion and score-information audits:
  `docs/experiments/rubric_lite_progress_completion_gate_result.json` and
  `docs/experiments/rubric_lite_score_collision_audit.json`
- v6 evidence-ledger preregistration:
  `docs/experiments/rubric_lite_v6_evidence_ledger_ab.json`

During analysis, an attempted server checkpoint restore appended 60 duplicate v4 training
calls to the old `260729-11:33:04` checkpoint before it was stopped. They are excluded from
every reported metric and token count. The promoted confirmation preflight reconstructed
the original 600 `judge::` records, matched the saved base confusion matrix exactly, and
made zero primary calls before the 51 verifier calls.
