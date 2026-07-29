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

## Rubric-Lite: the simpler generalization experiment

The large held-out run shows that the hierarchy is not the source of the reported gain. On
the same 1,200 held-out cases, the routed tree prediction *before* consensus and editor-prior
resolution was `77.58%` accurate, below the fixed v2 initial rubric at `78.25%`. The final
full-coverage result rose to `82.83%` only after three-way global consensus and a training-set
editor prior. The `92.87%` figure additionally abstains on `35.75%` of cases. Therefore, the
current evidence does not justify the complexity of task leaves, embeddings, semantic
clustering, merge synthesis, routing thresholds, or promoted branches for deployment.

The partial class is a boundary problem rather than a tree-routing problem. Across the 1,200
held-out cases, Cali-Tree v2 predicted `partial` 94 times, with 36 true positives among 135
human-partial cases:

- precision: `38.30%` (`36 / 94`)
- recall: `26.67%` (`36 / 135`)
- F1: `31.50%`

Rubric-Lite is a deliberately small alternative available as the `rubric_lite_train` workflow
node and in `workflows/examples/rubric_lite_imagenhub.json`. It has one learned global prompt,
one judge call per case, and no embedding, tree, merge, route, critic ensemble, or editor prior.
Its rubric decomposes every requested condition onto a single ordinal evidence scale:

```text
any condition = none, or source scene replaced  -> no
else any condition = partial                    -> partial
else all conditions = full                      -> yes
```

The JSON condition evidence is mapped back to the label deterministically, so a free-form
model label cannot contradict its own evidence. Learning uses the official training tasks
only. By default it excludes disputed human ratings, creates a task-disjoint internal
validation slice, and mines four reusable kinds of feedback: missed partials, false partials,
other outer-class errors, and correct boundary anchors. An optimizer rewrite is selected by
partial F1 only when validation accuracy remains within one percentage point of the initial
rubric. The feedback explicitly forbids item IDs, editor names, dataset-frequency rules, and
instruction-only shortcuts.

Two billable experiments used the frozen 10% offset-0 slice: all 232 official training cases
(181 unanimous cases eligible for rubric learning) and 120 held-out cases from 15 unseen tasks.
Both used `gpt-4.1-mini` as the image judge. V1 also evaluated three optimizer rewrites with
`gpt-4.1-mini`; its task-grouped validation guard retained the unmodified step-0 rubric. V2
used one completion containing three structured rubric views and a deterministic majority,
with no optimizer call.

| Rubric-Lite version | Test accuracy | Balanced accuracy | Macro F1 | Partial precision | Partial recall | Partial F1 | Unanimous accuracy | Disputed accuracy | Calls / tokens |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| v1 condition evidence | 76.67% | 65.96% | 52.74% | 55.56% | 35.71% | 43.48% | 89.69% | 21.74% | 895 judge + 3 optimizer / 1,408,677 |
| v2 three-view vote | 73.33% | 52.43% | 42.48% | 25.00% | 14.29% | 18.18% | 85.57% | 21.74% | 354 judge / 564,116 |

V1 improved partial F1 over the tree system while missing the overall-accuracy criterion.
V2 reduced prompt cost and removed optimization, but degraded both overall accuracy and the
partial boundary. Neither version is a replacement for the full-coverage Cali-Tree v2 result.
The negative result supports keeping the single-rubric architecture as an experiment while
continuing rubric learning, rather than adding another routing hierarchy.

The frozen promotion criteria were:

- overall accuracy at least `84.00%` (within one point of the existing v2 run's `85.00%`)
- partial F1 above the existing run's `31.58%` (`3/5` precision, `3/14` recall)
- no use of editor identity, held-out labels, embeddings, or per-task prompts

Because neither version cleared both criteria, no 50% confirmation run was performed. The
complete reports are in `logs/exps/260729-09:54:40-exps/rubric_lite_train.json` (v1) and
`logs/exps/260729-10:27:07-exps/rubric_lite_train.json` (v2). Any next version should remain
frozen on the 10% development slice before the unchanged rubric is promoted to the disjoint
50% offset-1 confirmation slice.
