# Real-data decomposition development

The goal remains human-label agreement on real image-editing data. Schema
validity and matching a direct model prediction are insufficient success gates.

## Implemented strategy

`decomposition_twoway_vision.py` adds `DecompositionTwoWayVision` alongside the
older bounded structured-evidence strategy. It partitions optimized rubrics
without losing source text, generates open-vocabulary instruction conditions,
checks each against actual source/edited images, separately observes preservation,
and applies the rubric to these findings. All stages are traced and cached by
their actual inputs, templates/model settings and image contents.

Human annotations are never provided to rubric/instruction compilation, image
checks, aggregation, review or disagreement resolution. They are used after
predictions to score agreement. All model experiments below use temperature 0
and one decision per arm/case; they are not repeated robustness estimates.

## Evidence so far

| Configuration | Seven development cases | Fifty disjoint tasks | Substantively rewritten subset of those 50 |
|---|---:|---:|---:|
| Direct optimized, gpt-5.4-mini (frozen v2 baseline) | 6/7 | 32/50 | 11/15 |
| Unreviewed two-way vision, gpt-5.4-mini | 7/7 | 31/50 | 8/15 |
| Instruction audit + observation review, gpt-5.4-mini | 7/7 | 26/50, two invalid | 4/15, one invalid |
| Resolve direct/decomposed disagreements, gpt-5.4-mini | Not run | 28/50 | 7/15 |
| Direct optimized, gpt-4.1 (fresh frozen baseline) | 4/7 | 29/50 | 7/15 |
| Unreviewed two-way vision, gpt-4.1, after reference fixes | 6/7 | 31/50 | 9/15 |

The initial v1 development run scored 5/7 with two schema errors. Canonicalizing
rubric line order and handling standalone instruction connectors fixed those
errors in v2. The seven-case success did **not** generalize to the fifty tasks.

The unreviewed pipeline corrected ten direct-optimized mistakes but introduced
eleven regressions. Review and resolution did not improve net performance and
remain opt-in experimental options; neither is selected as the default.
Resolver evaluation reused frozen direct/decomposed predictions to avoid
confounding resolution with resampling. Review also reused matching baselines
and valid intermediate checkpoints. After these development experiments, the
fifty tasks must no longer be presented as untouched validation data.

The first default-model run scored 25/50 with six invalid decomposition outputs.
Fixing casing-only source quotes raised this to 29/50 with two invalid outputs;
recognizing purpose connectors and question wrappers removed the remaining
reference errors and yielded 31/50. Original/optimized baselines and valid stage
checkpoints were reused for these development repairs. Negation and action-word
omissions are still rejected. The final model-specific development gain is
small and is not proof of generalization.

An additional offline five-fold exploratory calibration probe using the fifty
unreviewed observation records achieved at most 26/50 out-of-fold agreement
across four simple classifiers, below the existing 31/50. It was not selected
or integrated. This probe used training-fold labels only, but its small dataset
does not support claims of calibration efficacy.

## Remaining failure mechanisms

- The earlier lost-action problem is addressed: plans now explicitly contain
  grasping, movement, removal, arbitrary spatial placement and style requirements.
- Some generated requirements add stricter staging/visibility constraints than
  the instruction states. Source-span coverage prevents textual omissions but
  cannot prove semantic equivalence.
- Vision findings can mistake unchanged spatial relationships for movements,
  identify the wrong target, miss unintended changes, or demand stronger
  evidence than human graders used.
- Preservation and requested-change interpretations sometimes conflict,
  especially for global style transformations. A separate reviewer can amplify
  errors rather than correct them.
- The default-model comparison exposed case-only quoted-source mismatches as
  avoidable schema errors. That first run is preserved before a reference fix.

These are measured limitations, not reasons to substitute handwritten labels
or claim that a better representation alone solves ground-truth agreement.

The authors describe the published human target as absolute edit success,
emphasizing semantic interpretation over aesthetics; this provides annotation
context, not an excuse to relabel mismatches.
[AURORA paper, human evaluation and Appendix D.2](https://arxiv.org/html/2407.03471v3#A4.SS2).
The project's fixed loader discretizes the released 0–2 mean scores at 0.5/1.5;
the continuous scores remain in the experiment fixtures.

## New validation set

`fixtures/aurora_vision_fresh64.json` freezes **64 further task groups**, eight
per AURORA category, with no overlap with the ten original diagnostic tasks or
the fifty development tasks. One editor output per task was selected using seed
260926, without selecting by labels or predictions. Cached substantive prompts
are routed by category using a predeclared rule, not test labels. This set will
measure both decomposition and prompt transfer beyond optimizer focal cases.

Every source/edited image in all fixtures was verified pixel for pixel against
the authors' public archive, SHA-256
`8a3430a01cda0139d4c99835a75dca98e16ec6ccc486fa30afa4504f3f18c69f`.

## First 64-task validation and source grounding

The first further 64-task cohort has now been evaluated. Every case uses a
substantive cached category prompt. Original and optimized baselines were freshly
sampled for each model; neither model achieved a convincing decomposition gain.

| Model / strategy | Original | Optimized | Decomposed | Invalid decomposition outputs |
|---|---:|---:|---:|---:|
| gpt-5.4-mini, image-pair | 27/64 | 27/64 | 29/64 | 0 |
| gpt-4.1, image-pair | 44/64 | 43/64 | 43/64 | 2 |
| gpt-4.1, source grounding, development ablation | 44/64 reused | 43/64 reused | 46/64 | 1 |

The mini pipeline corrected nine optimized errors but introduced seven; the
gpt-4.1 pipeline corrected six and introduced six. After examining these results,
the first 64-task cohort is development data for subsequent revisions.

`DecompositionTwoWayGrounded` identifies targets, references, and initial states
from SOURCE alone, before comparing against EDITED. The source-grounding ablation
corrected seven optimized mistakes but introduced four regressions. Of its 18
unsuccessful cases, 17 disagreed with human labels and one failed instruction
source-coverage validation. This is a small development gain, not independent
evidence that grounding improves accuracy.

This cohort is highly imbalanced: 51 no, 11 partial, and two yes labels. A
constant-no baseline scores 51/64 (79.7%), above all measured methods on raw
accuracy. Grounding's per-label recalls are no 38/51, partial 6/11, and yes 2/2,
giving 76.4% balanced accuracy; the optimized baseline has 40/51, 2/11, and 1/2,
giving 48.9%. These diagnostics show improved minority-label recovery, not broad
success: the yes estimate is based on only two cases. The paired exact two-sided
McNemar test for seven corrections versus four regressions gives p=0.549. The
development accuracy gain is not statistically convincing and is not a holdout
estimate. Constant-no is a diagnostic baseline, not a selected solution.

Concrete traces expose different failure stages:

- N11, cyan object becomes shiny: the preservation check reports lost
  recognizability and a replaced scene, yet aggregation returns partial instead
  of the human no label. This is contradictory use of recorded findings.
- N45, add a leashed dog to a hydrant: a single combined condition is marked
  partial despite no visible leash. Combining object/attribute/relation checks
  can conceal a missing required attribute.
- N18, chalk drawing: weak stylization is treated as partial success when the
  human label is no; requested-style and preservation findings conflict.
- N37, black DVD to white DVD: the final no label matches the human label, but
  the checks still assert that the DVD was recolored. The final match does not
  establish that grounding solved object-color interpretation.

After this ablation, the grounded instruction template was changed to quote the
entire instruction on every generated condition, reducing accidental lexical
coverage failures. This guards traceability, not semantic correctness.

## Second untouched 64-task protocol

`fixtures/aurora_vision_grounded_holdout64.json` uses seed 260927 to select eight
tasks per category. It excludes all 124 prior task groups and every prior source
image's decoded pixel hash. All 128 source/edited images match the authors'
archive pixel for pixel. The same cached category prompt routing is fixed before
evaluation. There is no new prompt optimization, test-label feedback, or
selection by prediction.

The frozen comparison used gpt-4.1, temperature 0, one fresh decision per
arm/case, and separate Original, Optimized, and source-grounded decomposition
arms. The source and templates were snapshotted and verified unchanged during the
run. It completed in 190.67 seconds with the following results:

| Method | Correct | Invalid | No recall | Partial recall | Yes recall | Balanced accuracy |
|---|---:|---:|---:|---:|---:|---:|
| Original | 51/64 (79.7%) | 0 | 44/49 | 3/8 | 4/7 | 61.5% |
| Optimized | 50/64 (78.1%) | 0 | 46/49 | 1/8 | 3/7 | 49.7% |
| Source-grounded decomposition | 54/64 (84.4%) | 0 | 42/49 | 7/8 | 5/7 | 81.5% |

The cohort contains 49 no, eight partial, and seven yes labels. Constant-no
scores 49/64 (76.6%). Grounding corrects nine optimized errors and introduces
five regressions, a net four-case gain (6.25 percentage points). The paired exact
two-sided McNemar p-value is 0.424. This is encouraging fresh evidence, particularly
for minority-label recall, but does not establish a statistically reliable gain.
Only one draw per case was measured. The live quality assertion correctly fails:
ten ground-truth mismatches remain, even though schema/capability checks pass.

Remaining failures include false-positive style completion (G21), conflicting
requested/preservation facts (G28/G60), overly lenient treatment of wrong subjects
or unrelated changes (G29/G33/G64), and removal semantics confused with removing
an attribute (G35). Other cases over-penalize table-shape or movement effects
relative to human labels (G47/G62). G51's requested-change and preservation checks
both claim success while the human target is no. These traces do not justify
changing the targets or claiming that a correct schema is a correct judge.

## Executable aggregation experiment

`DecompositionTwoWayExecutable` is a further experimental subclass. It compiles
the optimized rubric alone into open-vocabulary boolean questions and ordered
label rules. Each question is independently checked against the frozen image
observations; the runtime executes all/any/not expressions deterministically.
There is no fixed hand-written mapping from fulfillment or preservation to labels.
Unknown predicates can block a decision rather than silently become false.
Source-unit coverage and citations guard traceability, not semantic equivalence
of the generated program.

The first ablation uses all 64 earlier source-grounded development cases, keeps
their direct predictions and image findings fixed, and preserves their missing
observation case in the denominator. It measures aggregation separately from
vision. No candidate or human labels enter the compiler or predicate checks.
This strategy is not selected as an improvement. The newly observed second
cohort is not untouched data for any subsequent revisions.

The first executable run scored 40/64 with 11 invalid outputs: one inherited
missing observation and ten compiler coverage failures. It corrected four
source-grounded errors and regressed ten cases, including otherwise correct
cases made invalid by missing citations. The compiler had repeatedly omitted
the task-definition unit. Diagnostics now name missing IDs and provide the
required IDs explicitly in the compilation payload; the coverage guard remains
unchanged. The repaired development run compiles each unique prompt once,
including failures, instead of resampling a failed compiler for every case.
Both run snapshots are retained. The initial test-wrapper setting lookup failed
before any model calls and was repaired; its wrapper now exposes temperature and
token limits for cache identity, verified by a checkpoint-invalidation unit test.

After the coverage repair, executable aggregation scored **45/64**, versus
source-grounded 46/64, original 44/64, and optimized 43/64 on these same frozen
development cases. All 63 available observation records produced valid decisions;
the sole invalid case is the original missing observation, retained in the 64-case
denominator. The program corrected N11/N18/N22/N25 but regressed
N16/N29/N35/N37/N46. Source hashes were unchanged throughout both runs.

N11 is a useful mechanistic correction: the compiled scene-failure predicate
uses the recorded replaced-scene evidence and returns no. Other examples reveal
the limit of deterministic execution: independent questions may assign inconsistent
truth values, generated definitions may miss preservation exceptions, and predicate
answers may contradict their own rationales (N37). The interpreter obeying a rule
is not evidence that either the rule or its inputs are correct. No efficacy gain
was measured, so executable aggregation remains opt-in and is not a replacement
for the source-grounded strategy.

## Instruction intent and permitted effects

`DecompositionTwoWayIntent` parses the instruction alone into operations with
separate target selectors, quantity, requested delta, permitted effects, and
linguistic ambiguities. No images, rubric or annotations enter that scope stage.
Conditions, image checks, preservation, and aggregation share the interpretation;
the original instruction remains authoritative. The variant still uses the
original verbatim-rubric model aggregator rather than executable aggregation.

The development ablation reuses all 64 second-cohort direct baselines and reruns
the decomposition stages. It scored **55/64**, with zero invalid outputs, versus
the frozen source-grounded 54/64. It corrected G29/G35/G47/G62/G64 but regressed
G20/G24/G25/G42. Per-label recall is no 43/49, partial 6/8, yes 6/7, giving 82.8%
balanced accuracy. Against optimized 50/64 it corrected nine and regressed four
(paired exact McNemar p=0.267). Against source grounding, five corrections versus
four regressions give p=1.0. This is not convincing evidence of a net improvement.

Visual inspection confirmed G35's whole-object/attribute distinction: all five
green hats remain, while feathers are removed. The new checker correctly records
that as absent hat removal. G62 now treats the requested mug movement as permitted,
instead of inventing a requirement to keep the mug on its old support surface.
The style and preservation regressions show why these mechanistic corrections
cannot alone establish better generalization. G51's edited image contains a long
remote-like object and colored rectangular material; both pipelines identify a
wallet and return yes despite the human no target. Instruction semantics do not
resolve this remaining object-recognition failure.

After the development run, the instruction template was clarified to allow
unselected objects to remain when only N are removed, and to avoid turning
permitted effects or possible intermediate consequences into mandatory conditions.
These changes are included in the next frozen validation version.

## Third untouched 64-task protocol

`fixtures/aurora_vision_intent_holdout64.json` freezes seed 260928, eight tasks per
category, one randomly selected editor output per task. It excludes all 188
previously observed task groups and source pixel hashes, and contains 64 unique
new sources. Its 128 image assets are verified pixel-exact against the authors'
public archive. Selection uses shuffled sorted task IDs and sorted editor names,
with no label or prediction selection. Cached category prompt routing is unchanged.

The four arms are Original, Optimized, Grounded, and Decomposed (intent scope).
All direct judgments and image comparisons are fresh within the run, using
gpt-4.1, temperature 0, maximum output 4096 tokens, and one decision per arm/case.
The algorithms share exact-input intermediate checkpoints within this run (for
example identical rubric compilation), but reuse no previous-run decisions.
The code/templates/fixtures were snapshotted and verified unchanged during the
307.21-second live run. Results:

| Method | Correct | Invalid | No recall | Partial recall | Yes recall | Balanced accuracy |
|---|---:|---:|---:|---:|---:|---:|
| Original | 45/64 (70.3%) | 0 | 35/39 | 7/20 | 3/5 | 61.6% |
| Optimized | 42/64 (65.6%) | 0 | 36/39 | 3/20 | 3/5 | 55.8% |
| Source grounded | 44/64 (68.8%) | 1 | 35/39 | 7/20 | 2/5 | 54.9% |
| Intent scope | 46/64 (71.9%) | 0 | 33/39 | 11/20 | 2/5 | 59.9% |

The set contains 39 no, 20 partial, and five yes labels; constant-no is 39/64.
Intent corrects 11 optimized mistakes and introduces seven regressions
(paired exact McNemar p=0.481). Against source grounding it corrects seven and
regresses five (p=0.774), with one correction being a grounded compilation error.
Grounded I41 was invalid because the rubric compiler returned an unsupported
unit kind after its schema repair. That failure remains in the denominator.
After the frozen run completed, the validator diagnostic was made specific:
it names the invalid calibration kind and the four allowed choices. A single
text-only live repair of the recorded invalid compiler response succeeded and
retained every original nonempty line of the exact cached rubric, including its
source hash. No images, labels or candidate judgments were supplied. This verifies
a schema repair mechanism; it does not revise I41's historical quality score.
Intent's raw gain over the original prompt is only one case, and its balanced
accuracy is below original. Neither raw nor per-label results establish a
reliable advantage. The live goal-quality assertion correctly fails because 18
human-label mismatches remain. Intent scope remains experimental.

The hardest residual distinction is not always instruction parsing. I40 adds too
many ramekins: the checker calls the exact-count requirement absent, whereas the
human target is partial. I07 adds plates on a table without putting down the plate
in the person's hand; the model vetoes missing derived conditions, while the human
target is partial. I18 adds fantasy/cartoon elements but does not globally stylize
the image; strict style checking yields no versus human partial. These are
calibration/granularity mismatches between literal component fulfillment and
overall edit success. I12 also shows aggregation softening a recorded replaced
scene to partial against human no. I32 and I56 have all-positive findings despite
human no, so an aggregation-only correction cannot recover missing visual facts.

## Instruction-blind object-recognition diagnostic

Two further descriptions of previously evaluated development images supplied
only the edited image and a generic object-inventory request, with no instruction,
rubric, predictions or human label. For G51, the model identified a black
rectangular case (possibly glasses/remote-control case) and a stack of cards,
rather than confidently calling it a wallet as the conditioned checker had done.
For G35 it identified five green hats, consistent with whole hats remaining.
These are diagnostic observations, not an accuracy experiment or an implemented
inventory strategy. The second description also gave uncertain container details;
blind captions must not be treated as ground truth. Their potential value is to
expose counterevidence and uncertainty before a task-conditioned vision check.
The complete input/output record is saved in
`.cache/calitree-tests/vision-blind-inventory-diagnostic-20260926/results.json`.

## Supervised observation-calibration probes

Two offline probes use the first 128 already evaluated N/G cases (127 valid
observation records and one inherited invalid case). Their source images and task
groups are disjoint. Four stratified folds use seed 260929; vocabulary and scaling
are fitted on training folds only. Human labels are used only for training-fold
fitting and subsequent scoring, never as observation features. Invalid observations
remain invalid in the full 128-case denominator.

Numeric features include requested fulfillment counts/fractions, preservation
statuses, unintended-change severity counts, and the model's own predicted label.
The text variant additionally uses before/after findings and preservation evidence.
No case ID, task category, editor ID, human annotation or rubric text is a feature.
An instruction-only model is an explicit shortcut diagnostic, not an eligible
solution. Existing model observations mix grounded N traces and intent G traces,
so these are exploratory calibration tests, not fresh pipeline validation.

| Development configuration | Correct out of 128 | Balanced accuracy |
|---|---:|---:|
| Original decomposition judgments | 101 | 77.7% |
| Best raw logistic calibration (C=0.1, numeric or numeric+findings) | 109 | 71.3% |
| Instruction-only diagnostic | 100 | 33.3% |
| Confidence override at 0.6 | 106 | 73.7% |
| Confidence override at 0.7 | 102 | 72.3% |
| Confidence override at 0.8 | 103 | 74.1% |
| Confidence override at 0.9 | 101 | 76.3% |
| Confidence override at 0.95 | 101 | 77.7% |

The first probe compares 13 predeclared regularization/feature/class-weight
configurations. The second fixes the best raw numeric model and explores five
confidence thresholds, preserving the original judgment below each threshold.
Selection requires a strict development accuracy gain without balanced-accuracy
regression. No candidate meets both criteria, so neither is integrated. Raw
calibration gains would sacrifice minority-label quality. These model-selection
scores are exploratory and cannot establish holdout efficacy. The third cohort
was loaded for a potential transfer probe, but no candidate qualified and no
transfer prediction was selected. All source snapshots and fold membership are
saved in the artifacts below; no additional model API calls were made.

## Instruction-blind inventory pipeline

`DecompositionTwoWayInventory` adds separate descriptions of each image without
the instruction, source/edited role, rubric, metadata or target annotations. Each
inventory records visible object names, features, quantities, locations, alternative
identifications and uncertainty. Captions are hypotheses to check against images,
not authoritative facts. SOURCE's inventory is available before source target
binding. EDITED's inventory is generated afterwards; it cannot affect source
binding. Both feed the condition/preservation checks and the original optimized-
rubric aggregator. Image-local object IDs do not imply correspondence.

This extends intent scope and preserves its instruction plans. Cache keys for
inventories depend on image contents and model/template settings, not instruction.
The current development run uses all 64 I cases and fixed direct baselines, with
matching valid instruction/rubric checkpoints reused. The only new inference
information is the blind inventories and corresponding evidence instructions.
The full pipeline was frozen during the 192.88-second run. Inventory scored
47/64 with zero invalid outputs, versus intent's 46/64 on the same cases. It
corrected I04, I12, I15, I18 and I61 but regressed I31, I39, I43 and I46
(paired exact McNemar p=1). No/partial/yes recalls were 35/39, 10/20 and 2/5;
balanced accuracy was 59.9%, still below original's 61.6%. This is development
ablation, not fresh validation. The quality assertion failed on 17 mismatches.

I56 remains a visual count failure: even the instruction-blind edited inventory
claims four coasters. A later inspection of the actual full file corrected an
earlier mistaken single-scene description: the archive image contains two
side-by-side panels, each showing three coasters. Historical model inputs
passed that entire composite as EDITED. Panel semantics require an input audit. I32 remains a target/correspondence
failure: the source inventory misses the wooden utensil, and the condition
checker treats introduction of an object near the pan as fulfillment of movement.
Independent captions alone do not establish correct visual facts or correspondence.

## Stronger vision diagnostic

Six fresh GPT-5.4 calls (temperature 0, 4096 output tokens, one draw) examined
known development failures I32 and I56. Four calls used the unchanged generic
inventory prompt, with one image and no instruction, rubric, image role or human
label. Two calls compared both images against the editing instruction and asked
for source evidence, edited evidence, correspondence and change status; no rubric
or human labels were supplied. This selected-failure probe is diagnostic only.

The paired I56 comparison correctly reported three coasters in both images and
an absent addition. The independent edited inventory identified a side-by-side
split and three groups with counts of two each. Full-file inspection confirms
that split is real, correcting an earlier mistaken interpretation of the response.
The paired check implicitly reasons about one panel while the blind inventory
counts both. Historical runs supplied the entire composite as EDITED; identifying
and consistently handling the output panel may be a data-boundary issue. I32's paired
comparison acknowledged uncertain correspondence but reported partial movement;
it does not establish agreement with human no. A stronger backend can correct
some paired observations while still producing contradictory independent facts.
The same-model, all-64 development comparison finished in 334.90 seconds:
Original 42/64, Optimized 40/64, Decomposed 45/64, with four invalid decomposition
outputs. Balanced accuracies were 59.8%, 50.7%, and 61.6%. The four invalids
(I09--I12) came from a rubric compiler interpreting lists as line-range endpoints
and omitting intermediate lines even after its one schema repair. All cases,
including invalids, remain in the denominator. This is a backend development
ablation on previously observed tasks, despite the old manifest's inherited
fresh-cohort wording. The harness now records development explicitly. The gain
over optimized is nine corrections versus four regressions (paired exact
McNemar p=0.267), and this backend did not improve raw agreement over GPT-4.1. Official GPT-5.4 documentation
confirms image input and Chat Completions support; the local native-OpenAI adapter
explicitly disables reasoning for temperature 0. No API adapter change was needed.

## AURORA comparison-panel normalization

Inspection of the full I56 archive image revealed two horizontal panels, each
with three coasters. An input-only audit of all 2,000 outputs found exactly 150
source-left/output-right composites: every Something-Something output from
InstructPix2Pix, AURORA and reproduced MagicBrush. The other 1,850 outputs do not
match this contract. For those 150, the left panel matches a resized or fitted
source with maximum thumbnail RGB MAE 1.195; no labels or predictions determine
routing. Official evaluation code also saves source-left/output-right comparison
visualizations, although it does not specify this human-ratings archive contract.

`critical/database/dl_aurora/assets.py` explicitly routes these release task/editor
combinations, verifies the left preview against SOURCE (MAE <= 2), and saves a
lossless RGB crop of the right panel. It preserves every original asset and
records raw/source/output hashes, crop coordinates and match distance. This is a
release adapter, not a heuristic that crops any wide image. Setup materializes
panels and metadata; the read-only loader rejects legacy comparison-composite
metadata with instructions to rerun setup. All 2,000 local rows retain their
human scores and task groups; 150 now point to normalized outputs.

The I-cohort ablation keeps all 64 tasks and original optimized prompts fixed.
Exactly I51, I53, I54, I55 and I56 receive cropped inputs. Both direct arms are
rerun for changed inputs; the other 59 reuse exact frozen predictions. Stage
checkpoints are reused only when exact request inputs and image hashes match.
All unaffected decomposition predictions are unchanged. The frozen pipeline
ran in 15.95 seconds with 23 new decomposition calls and ten direct calls:

| Method | Correct | Invalid | Balanced accuracy |
|---|---:|---:|---:|
| Original | 44/64 | 0 | 60.7% |
| Optimized | 41/64 | 0 | 54.9% |
| Intent decomposition | 47/64 | 0 | 60.7% |

I56 changes from yes to no in both original and decomposed judgments. Its new
condition check explicitly observes three coasters in both images and marks
addition absent. Decomposition gains one case against its prior 46/64; direct
original regresses on I51/I55 and corrects I56, optimized regresses on I51.
Normalization fixes input semantics, not a guaranteed accuracy gain in every arm.
The live goal-quality assertion still fails on 17 mismatches. Historical full-
composite results remain untouched and must not be presented as normalized-input
scores. Fresh validation has not yet been run on normalized inputs.

## Supervised semantic calibration probe

A text-only development probe keeps all 64 normalized I-cohort observation traces
and optimized rubrics fixed. It uses 119 earlier N/G reference traces (94 no,
17 partial, eight yes), excluding one invalid observation and eight historical
comparison-composite inputs by input contract, without selecting by prediction
quality. Training task IDs and source hashes are disjoint from the I cohort.
TF-IDF is fitted on reference instruction/condition/evidence text only. For each
query, two nearest references per class supply their actual human labels; no
current human label, model prediction, category/editor identity, sample ID or
image enters the grading call. Current-case labels are used only afterwards for
scoring. This is supervised calibration, unlike the earlier label-free pipeline.

The new grading prompt is also run without examples to separate prompting from
reference calibration. GPT-4.1, temperature 0, 4096 tokens, one fresh draw per
arm/case produced:

| Fixed-observation grader | Correct | Invalid | Balanced accuracy |
|---|---:|---:|---:|
| Frozen intent aggregator | 47/64 | 0 | 60.7% |
| New prompt, no references | 48/64 | 0 | 61.6% |
| New prompt, six labeled references | 48/64 | 0 | 62.4% |

Both new arms correct I12's scene-replacement aggregation error. References also
correct I04 but regress I34. The reference arm has no raw improvement over its
matching no-reference control, so no production calibration module is promoted.
Its I40 exact-count error remains no versus human partial. This is an exploratory
comparison on previously evaluated cases, not fresh validation.

A subsequent predeclared learned-rule probe uses four stratified folds of those
119 earlier traces, with unique source/task groups and seed 260930. One compact
rulebook is induced per training fold; each rule must cite at least two training
examples having its proposed label. The initial four rulebooks each failed that
support check: for example, a no rule cited two human-partial cases. All were
rejected before withheld-fold grading. The resulting 119 invalids are a rule-
learning capability failure, not a meaningful 0/119 quality estimate. Initial
responses remain preserved. A variant now allows exactly one training-only
consistency repair using the actual citation errors, before any fold grading.
Transfer calls are gated on zero invalid predictions, a strict OOF raw gain over
the existing 94/119 baseline, and no balanced-accuracy regression from 79.3%.
No I-cohort labels enter rule learning. After one training-only consistency
repair, only one of four fold policies passed. That policy scored 20/30 on its
withheld fold; the other 89 cases remain invalid because their policies still
cited incompatible labels. Full OOF accounting is 20/119 with 89 invalids; this
cannot establish efficacy, and the transfer gate rejected it without I-cohort
calls. The repaired variant is not promoted. A training-format variant now groups
examples explicitly by human label and includes a citation-label index to reduce
long-context support confusion. It retains the same folds and one-repair bound;
it produced two valid fold policies, 45/119 correct overall and 60 invalids.
On the 59 actually graded cases, learned rules scored 45/59 versus the original
48/59. The transfer gate again rejected it. This is a new development variant,
not a revision of the failed historical scores. No learned-rule module is promoted.

A deterministic tree probe uses numeric condition counts/fractions, preservation
statuses/severity counts and the model's own existing label, excluding all
metadata, instruction text and human annotations from inference features. Twelve
depth/leaf-size/class-weight configurations are selected using three inner folds
and assessed on four outer folds, seed 260930. An inner candidate must improve
raw agreement without balanced-accuracy regression; otherwise the existing
prediction is retained. All four outer folds selected that fallback. Outer OOF
remains 94/119 and 79.3% balanced accuracy, with no eligible transfer model. This
is nested evaluation rather than selecting the best score on the evaluation fold.

## Balanced additional calibration references

The earlier reference bank contains only eight full-success examples. The 128
already observed N/G source tasks have 512 other editor outputs: 354 no, 106
partial and 52 yes. A predeclared supervised training sample selects 30 outputs
per class, seed 260931, excluding the original 128 selected outputs and capping
new examples at two per source task. It includes 69 known source tasks. No
I-cohort task or any untouched task is selected. Training selection may use its
own human labels; observation/aggregation API calls do not receive those labels,
editor/category identity or case IDs.

All 180 selected source/raw-output image checks match the authors' pinned ZIP
in decoded RGB dimensions/pixels. Known comparison composites use the lossless
right-panel extraction. The unchanged intent pipeline, cached category optimized
rubrics and exact-input stage checkpoints produce new traces. Code/templates
are frozen, and all selected outputs remain in the reference collection report,
including any invalids. Collection completed with zero invalids and frozen code/
templates. Training agreement is 60/90: no 28/30, partial 14/30, yes 18/30. This
is a training resource, not a new validation score or a claimed decomposition
gain. The expanded bank has 209 examples (124 no, 47 partial, 38 yes). A grouped
nested tree probe now keeps every shared source pixel within one fold in both
inner selection and outer evaluation. All four outer folds selected the unchanged-prediction fallback: 154/209
correct (73.7%), with 68.1% balanced accuracy. No I-cohort labels were used
in training or configuration selection, and no transfer model was eligible.

## Richer progress evidence and continuous-score calibration

A frozen text-only prototype extracts atomic facets, exact completion, partial
progress, discrepancy type and cited counts from 209 training traces and all
64 normalized I-cohort development traces. GPT-4.1, temperature 0, 4096 tokens,
one draw and at most one schema repair are fixed. No images, rubric, grading
predictions, human labels or task/editor identity enter extraction calls. Each
fact must cite an exact substring in the supplied observation fields. Of 273
cases, 19 remain invalid after bounded repair: 13 training and six development
cases. Typical failures are uncited counts and incorrect quotations. Citation
validity establishes provenance, not visual or semantic truth.

The I40 trace now separates supported object identity/location from contradicted
quantity: the observed count changes from one to five although one addition was
requested. It recognizes some progress rather than collapsing everything into
an absent compound condition. However, I32 still inherits the original false
claim that the ladle moved; a text-only stage cannot recover missing image facts.

Adding these progress records to the same no-reference grading prompt, unchanged
optimized rubric and unchanged observations yields 48/64, exactly the matching
control's 48/64 (61.6% balanced accuracy). It corrects I04 and regresses I47.
The six invalid progress cases retain their exact control prediction and remain
in the denominator; the grader itself produces zero invalid outputs. This
prototype is distinct from the integrated intent pipeline's 47/64.

I07 and I40 explicitly illustrate a rubric/label mismatch: the grader recognizes
partial physical progress but applies the optimized rule that an unmet required
condition means no. Human ratings map both cases to partial. I47 illustrates the
opposite interpretation error: adding four helicopters is interpreted as meeting
an at-least-one requirement, yielding yes versus human partial. Richer evidence
alone does not determine the correct human label boundary.

Two offline nested calibration probes use 71 features describing original
findings, preservation and the new progress/facets/counts. Source-pixel groups
stay together in three inner folds and four outer folds, seed 260930. Invalid
progress cases retain their original prediction and remain in every denominator,
while being excluded only from calibrator fitting. A candidate must improve raw
agreement without reducing balanced accuracy on inner held-out predictions.
Twelve classification-tree configurations all select fallback, preserving
154/209 correct and 68.1% balanced accuracy. A second probe learns residuals
against the continuous human mean score using three ridge strengths and three
regression-tree depths; the original 0.5/1.5 label cutoffs remain fixed. It also
selects fallback in all four folds, with the same 154/209 result. Neither probe
qualifies for I-cohort transfer, and no production strategy is promoted.

Artifacts and frozen source snapshots are saved under:

- `.cache/calitree-tests/vision-progress-evidence-development-20260926/`
- `.cache/calitree-tests/vision-progress-aggregation-development64-20260926/`
- `.cache/calitree-tests/vision-nested-progress-calibration-development-20260926/`
- `.cache/calitree-tests/vision-nested-score-calibration-development-20260926/`

## Requested-operation hierarchy development probe

A label-blind text-only variant groups all existing condition checks beneath
independently requested operation roots. Each root distinguishes exact completion
from observed progress and cites exact observation substrings. The final grader
uses the unchanged optimized rubric with an explicit operation-level interpretation
of its required-condition rule. This changes aggregation semantics; it is not a
certified behavior-preserving decomposition. No images, human annotations or
reference examples enter its calls. GPT-4.1, temperature 0, 4096 tokens, one draw
and at most one grouping-schema repair are fixed. All 64 normalized I-cohort
cases are retained.

The hierarchy scores 47/64 with zero invalids, compared with its frozen flat
control's 48/64. Balanced accuracy is 62.4% versus 61.6%; partial recall improves
from 55% to 65%, while no recall falls from 89.7% to 82.1%. It corrects I10/I40
and regresses I34/I37/I49. The strict raw-improvement transfer gate is not met.
I40 now receives partial for excessive additions, but I37 applies the same
partial-progress interpretation to excessive removals where humans rated no.
I07 remains no: the model treats extra plates as unrelated to putting the
original held plate down. I49's hierarchy invents a peg identity from a cited
observation describing only a small rectangular object; exact citations alone
do not prevent semantic hallucination. I32 still inherits the incorrect ladle
movement observation. No production strategy is promoted.

Artifacts are preserved under
`.cache/calitree-tests/vision-operation-hierarchy-development64-20260926/`.

## Visual reference calibration and image-role diagnostic

A matched vision-grading probe uses the unchanged compiled optimized rubric and
instruction condition plan, but inspects the query images directly instead of
merging frozen text-only findings. One arm has no labeled examples; the other
has three actual source/edited reference image pairs, one nearest example per
human label with distinct source pixels. TF-IDF retrieval is fitted on the
209 training instruction/requirement texts only. Training labels and continuous
human means are supplied for references; query annotations and metadata are
withheld. All 295 unique uploaded image files are verified in decoded pixels
against the pinned public archive, including right-panel crops. Source-pixel and
task groups are disjoint from the 64 I-cohort development queries. GPT-4.1,
temperature 0, 4096 tokens, one draw and at most one schema repair are fixed.
This is an image-based aggregation variant, not the integrated isolated pipeline.

The no-reference arm scores 43/64 (52.4% balanced accuracy), versus 39/64 (48.2%)
with visual references. The reference arm has one invalid response, I43, which
omits required calibration citations after repair; it remains in the denominator.
References correct five labels and regress nine relative to the matched control.
However, I32's apparent correction to no describes wooden benches, whereas the
query source/edited images are visibly a kitchen scene. That label agreement
cannot be credited as correct visual reasoning. I56 regresses from correctly
observing three coasters in both images to falsely observing two then three.

The local engine adapter preserves input order and supports interleaved text
media. A six-call, selected-failure diagnostic on I32/I56/I43 repeats the exact
prompt, payload, references and image bytes, inserting explicit reference/query
and source/edited markers immediately before each image. It is not an accuracy
benchmark. The I32 reference response now describes the kitchen scene but still
mistakes a newly visible utensil for successful movement and returns yes. I56
now correctly observes three coasters in both images and returns no. I43 cites
a reference and returns partial. The no-reference labels remain yes/no/yes.
The full marked-image comparison is complete: no-reference scores 42/64
(57.4% balanced accuracy), and visual references score 48/64 (65.8%), both with
zero invalids. References correct I09/I43/I46/I49/I51/I53 and regress no cases
relative to the matched control. The descriptive exact paired McNemar p is
0.03125, but this is exploratory development after multiple variants, not
confirmatory unseen validation. The original unmarked results remain preserved.
Compared with the separately integrated intent pipeline's 47/64, the net raw
gain is only one case. Sixteen mismatches remain. This fixed method qualifies
for fresh source-disjoint validation; no production strategy is promoted.
That development run left all 148 previously untouched task IDs untouched;
the subsequent 32-case validation below changes the current reservation count.

Artifacts:

- `.cache/calitree-tests/vision-visual-reference-calibration-development64-20260926/`
- `.cache/calitree-tests/vision-interleaved-image-role-diagnostic-20260926/`
- `.cache/calitree-tests/vision-visual-reference-interleaved-development64-20260926/`

## Nested joint semantic/numeric calibration

A local supervised probe augments the 71 structured findings with TF-IDF text.
Twelve logistic configurations combine C = 0.1/1/10, ordinary/balanced class
weights and either instruction/requirement text or that text plus recorded
source/edited evidence. No task/category/editor metadata or human annotations
enter inference features. Vocabulary and numeric scaling are fitted within each
training split. The existing three-inner/four-outer source-pixel-grouped protocol
and fallback policy remain fixed, seed 260930. Invalid progress cases retain
original predictions and remain scored. No query labels enter fitting/selection.

No inner candidate beats its fold baseline without balanced-accuracy regression;
all four outer folds select fallback. Thus 154/209 (73.7%) and 68.1% balanced
accuracy describe the unchanged pipeline, not a new trained model's improvement.
No I-cohort transfer is eligible. The result is preserved under
`.cache/calitree-tests/vision-nested-semantic-feature-calibration-development-20260926/`.

## Frozen visual calibration validation and opt-in core implementation

The fixed marked-image method is now evaluated on 32 previously untouched tasks,
four per category with one randomly selected editor output, seed 260932. Scores
and predictions do not determine selection. The input audit excludes all 252
observed task IDs and source pixels: four of the 148 unused task IDs reuse known
pixels, leaving 144 eligible candidates. All 32 selected source pixels are
unique and unseen; all 396 possible query/reference upload files match the
public archive. Cached category rubrics, the grading template, retrieval settings
and role markers are fixed before calls. No current labels enter the five arms.

| Method | Correct | Invalid | Balanced accuracy |
|---|---:|---:|---:|
| Original | 26/32 | 0 | 70.9% |
| Cached optimized | 26/32 | 0 | 43.1% |
| Intent decomposition | 26/32 | 0 | 47.3% |
| Image-backed, no references | 28/32 | 0 | 54.2% |
| Image-backed, visual references | 28/32 | 0 | 86.2% |

There are 25 no, six partial and one yes label. References correct two and
regress two versus their matching no-reference control: no fresh raw accuracy
gain (exact paired p=1). They correct three and regress one versus intent
(p=0.625). The high yes recall has only one supporting case; neither a reliable
reference accuracy benefit nor complete ground-truth agreement is established.
The original development gain must not be pooled into a fresh validation claim.
Remaining reference-arm errors are J01 curtains (human no/model yes), J05 cylinder
color/identity (no/partial), J10 partial global cartoon styling (partial/no), and
J29 moved versus replaced bowl identity (partial/no).

The method is integrated as the experimental, opt-in
`DecompositionTwoWayCalibratedVision` in `decomposition_twoway_calibrated.py`,
with `visual_calibration.py` for typed training references, source-disjoint
retrieval, adjacent media roles and grading validation. Its versioned template
is copied exactly from the frozen prototype. It reuses image/label-blind intent
planning and lossless rubric compilation; condition findings and the decision
share a vision call, so observation independence is not claimed. Existing
defaults remain unchanged. References are optional, exposing both tested arms.

Offline replay matches all 192 recorded development/validation grading arms in
exact selected references, prompts, media blocks, decisions and repair sequences.
The full offline suite passes 901 tests, 23 live experiments skipped, 52 existing
warnings. These are implementation checks, not new quality evidence. All 325
fresh calls and frozen source files are preserved. The live run encountered a
report-only variable collision after saving all cases; a separate offline
finalizer repaired the summary without rerunning calls or changing decisions.

See `visual_calibration_holdout32_20260926.md` for the full protocol and failures.
Artifacts are under `.cache/calitree-tests/vision-visual-calibration-fresh32-20260926/`.
The new fixture is `fixtures/aurora_vision_calibrated_holdout32.json`. These tasks
are now observed: 116 unused task IDs remain, of which 112 still have unseen
source pixels. The goal is not complete.

## Source anchors and neutral observations on observed J32 cases

Follow-up diagnostics tested SOURCE-only identity anchors and independently
answered neutral questions. SOURCE crops did not correct three of four selected
failures and lost the text-only correction on the fourth. Full J32 development
runs scored 24/32 with free questions (five invalid) and 26/32 with typed property
probes (two invalid), below the frozen calibrated-vision control's 28/32.
Generated free questions could leak desired states; typed observation templates
removed that route but retained visual hallucination and partial-credit errors.
Neither variant is promoted. The original free-question helper lost raw failed
responses; the typed run fixes logging before validation and preserves every
attempt. See [neutral_observation_development32_20260926.md](neutral_observation_development32_20260926.md)
for the protocol, paired results, audit limitation and failure analysis.

## User-directed restart: individual-case accuracy

The user clarified that generalization is not the research criterion. The current
exploration restarts from each real J32 image pair and its cached optimized
prompt. Initial individual condition checking matched 27/32 human labels.
Explicit known-label fitting feedback raised this to 28/32; focused observable
criteria repair raised it to 30/32; independent neutral evidence resolved the
last two cases, giving **32/32 fitted matches**. Original and cached optimized
prompts each matched 26/32. All attempts and feedback use remain recorded.

See [casewise_decomposition32_20260926.md](casewise_decomposition32_20260926.md)
for all 32 individual comparisons, the algorithm and correction reasons. The
final audit independently reduces 74 condition responses and checks that human
feedback keys were absent from individual checker inputs. Known labels were
used to revise plans and choose the cases requiring further work. Core defaults
remain unchanged; the per-case fitter is currently an opt-in experiment runner,
with focused repair and neutral-evidence escalation preserved as snapshots.
Further work should integrate this demonstrated per-case workflow and investigate
additional named cases; untouched-source validation is not a current requirement.

## Artifacts

Complete manifests, draws, condition plans, image findings, decision traces and
model-call records are preserved in:

- `.cache/calitree-tests/vision-v1-20260926/`: first development capability failures.
- `.cache/calitree-tests/vision-v2-20260926/`: seven-case result and frozen fifty-task validation.
- `.cache/calitree-tests/vision-reviewed-20260926/`: exploratory review ablation.
- `.cache/calitree-tests/vision-resolved-20260926/`: controlled disagreement ablation.
- `.cache/calitree-tests/vision-gpt41-20260926/`: default-model comparison and frozen source snapshot.
- `.cache/calitree-tests/vision-gpt41-casefixed-20260926/`: case-only quote repair.
- `.cache/calitree-tests/vision-gpt41-references-20260926/`: connector/question-wrapper reference repair.
- `.cache/calitree-tests/vision-fresh64-mini-20260926/`: predeclared primary fresh validation.
- `.cache/calitree-tests/vision-fresh64-gpt41-20260926/`: predeclared default-model replication.
- `.cache/calitree-tests/vision-grounded-development64-20260926/`: source-grounding development ablation, with frozen direct baselines reused.
- `.cache/calitree-tests/vision-grounded-holdout64-20260926/`: second untouched 64-task experiment.
- `.cache/calitree-tests/vision-executable-development64-20260926/`: executable aggregation ablation on earlier frozen findings.
- `.cache/calitree-tests/vision-executable-covered-development64-20260926/`: compiler coverage repair on the same frozen development findings.
- `.cache/calitree-tests/vision-intent-development64-20260926/`: selector/change/scope development ablation.
- `.cache/calitree-tests/vision-intent-holdout64-20260926/`: third untouched four-arm validation.
- `.cache/calitree-tests/vision-blind-inventory-diagnostic-20260926/`: instruction-blind descriptions of two development failures.
- `.cache/calitree-tests/vision-rubric-kind-repair-20260926/`: one text-only live repair of the recorded I41 compiler failure.
- `.cache/calitree-tests/vision-observation-calibration-development-20260926/`: 13-configuration development OOF calibration probe and source snapshot.
- `.cache/calitree-tests/vision-observation-selective-development-20260926/`: confidence-override calibration probe and source snapshot.
- `.cache/calitree-tests/vision-inventory-development64-20260926/`: instruction-blind inventories on all third-cohort development cases.
- `.cache/calitree-tests/vision-gpt54-failure-probe-20260926/`: six selected-failure diagnostic calls, exact inputs and source snapshot.
- `.cache/calitree-tests/vision-gpt54-intent-development64-20260926/`: same-model capacity ablation on all third-cohort development cases.
- `.cache/calitree-tests/aurora-panel-layout-audit-20260926/`: label-independent panel audit of all 2,000 archive outputs and source snapshot.
- `.cache/calitree-tests/vision-output-panels-intent-development64-20260926/`: controlled development input correction with exact unchanged predictions reused.
- `.cache/calitree-tests/vision-semantic-calibration-development64-20260926/`: matched no-reference/six-reference aggregation comparison, reference bank and exact calls.
- `.cache/calitree-tests/vision-learned-rule-calibration-development-20260926/`: initial rulebook support failures with original model outputs.
- `.cache/calitree-tests/vision-learned-rule-calibration-repaired-development-20260926/`: bounded training-consistency repair and withheld-fold grading.
- `.cache/calitree-tests/vision-learned-rule-calibration-grouped-development-20260926/`: label-grouped induction and source index, with unchanged validation folds.
- `.cache/calitree-tests/vision-nested-tree-calibration-development-20260926/`: nested numeric tree calibration, candidate selection audits and source snapshot.
- `.cache/calitree-tests/vision-balanced-calibration-reference-collection-20260926/`: balanced additional editor outputs from known training tasks, frozen protocol, public pixel provenance and new observation traces.
- `.cache/calitree-tests/vision-nested-grouped-tree-calibration-development-20260926/`: expanded-bank calibration with inner/outer splits grouped by decoded source pixels.
- `.cache/calitree-tests/vision-expanded-semantic-calibration-development64-20260926/`: expanded reference bank with exact unchanged zero-shot controls and fresh six-reference judgments.

The goal is **not complete**. Text-only reference calibration, generated rules
and nested numeric/semantic classifiers have not established a reliable benefit.
Visual reference calibration with adjacent image-role markers has a promising
48/64 development result versus its matching 42/64 control, and 28/32 on newly validated sources (tied with its matching no-reference
control). It is integrated as an opt-in image-backed strategy, but 16 development
and four fresh-cohort mismatches remain. The balanced
209-example training bank is preserved for subsequent experiments, and 116 unused task IDs remain
(112 with unseen source pixels). Source grounding and intent scope have small
observed gains against cached optimized prompts on fresh source-disjoint datasets,
but their reliability and repeatability are unproven, and the latest intent run
still disagrees with 18 of 64 human labels (17 after the development panel input
correction). Executable aggregation did not improve
the development result. Neither parsing success, more detailed instruction scope,
nor deterministic rule execution establishes ground-truth agreement. The latest
offline suite passes 901 tests with 23 live experiments skipped; those tests prove
code contracts and isolation, not model quality.

The later user-directed per-case result above supersedes generalization as the
next research criterion. The historical validation records and limitations remain
unchanged. The demonstrated 32-case fitted result is complete; integrating its
full automatic escalation into the core decomposition workflow remains open.
