# Frozen visual calibration validation on 32 unseen AURORA tasks

The image-backed calibrated strategy agrees with 28/32 human labels, versus
26/32 for the original prompt, cached optimized prompt and existing intent
pipeline. Its matched image-backed no-reference arm also scores 28/32. Thus the
reference accuracy gain from development did not replicate on this fresh cohort.

## Protocol and data boundary

- GPT-4.1, temperature 0, maximum 4096 output tokens, one draw; at most one schema repair and no quality retries.
- Four source tasks per category and one random editor output per task, seed 260932. Selection does not use scores, labels or predictions.
- Exclude all 252 previously observed task IDs and source pixels. Of 148 unused task IDs, four reuse known source pixels; the stricter eligible pool is 144.
- All 32 selected source pixel groups are distinct and previously unseen. Five fresh arms share identical normalized image inputs and cached category rubric assignments.
- The rubric is compiled losslessly and instruction conditions are generated without images or labels. Both image-backed arms reuse the intent pipeline's resulting rubric and plan, not its findings or prediction.
- The calibrated arm retrieves one example per human class from the fixed 209-example prior bank, using training-only TF-IDF on instructions/requirements. References use three distinct source pixel groups, disjoint from the query.
- The grading prompt, retrieval settings and adjacent image role markers are unchanged from the successful development variant. No query annotation, sample ID, category or editor identity enters API inputs. Human annotations are supplied only for training references.
- All 396 potential upload files match the pinned public archive in decoded pixels, including normalized right output panels. Code/templates were frozen throughout all 325 fresh model calls.

The authors evaluate semantic editing success with none/partial/full human
ratings, considering adherence to the instruction and source image. Their
released means are the authoritative labels here; this project bins them at
0.5/1.5. [AURORA paper, evaluation and annotation sections](https://arxiv.org/html/2407.03471v3).

## Results

The cohort has 25 no, six partial and one yes label. Constant no gives 25/32.
All model arms produce zero invalid outputs.

| Arm | Correct | No recall | Partial recall | Yes recall | Balanced accuracy |
|---|---:|---:|---:|---:|---:|
| Original prompt | 26/32 | 24/25 | 1/6 | 1/1 | 70.9% |
| Cached optimized prompt | 26/32 | 24/25 | 2/6 | 0/1 | 43.1% |
| Intent decomposition | 26/32 | 23/25 | 3/6 | 0/1 | 47.3% |
| Image-backed, no references | 28/32 | 24/25 | 4/6 | 0/1 | 54.2% |
| Image-backed, visual references | 28/32 | 23/25 | 4/6 | 1/1 | 86.2% |

Visual references correct J11/J13 and regress J05/J29 versus their matched
control (exact paired McNemar p=1). Versus intent, they correct J09/J13/J16 and
regress J29 (p=0.625). These small paired samples do not establish a reliable
accuracy benefit from references or superiority over the existing pipeline.
The yes-recall estimate is based on just one case. The raw development scores
48/64 versus 42/64 remain separate and are not pooled into this fresh estimate.

## Remaining failures

| Case | Instruction | Human | Prediction | Recorded mechanism |
|---|---|---|---|---|
| J01 | Make them close the curtains | no | yes | The grader reports closed curtains and full completion; the image/action interpretation disagrees with the human rating. |
| J05 | the tiny yellow cylinder turns brown | no | partial | The grader credits a brown replacement despite changed shape/object identity. |
| J10 | Make the image look like a cartoon | partial | no | It recognizes a cartoon-like framed picture but treats lack of global stylization as absent progress. Human mean is 0.5833, just above this project's partial cutoff. |
| J29 | Move the bowl to the left of the flower | partial | no | It observes two smaller bowls on the requested side but treats replacement of the original bowl as absence of the requested move. |

Richer observations and reference examples do not yet reliably distinguish zero
accomplishment from partial accomplishment, or preserve target correspondence.
Human labels are not changed to match model explanations. The goal remains
unachieved: four fresh-cohort mismatches remain.

## Implementation and verification

`DecompositionTwoWayCalibratedVision` is an opt-in core strategy in
`decomposition_twoway_calibrated.py`, with reference retrieval/media validation in
`visual_calibration.py` and a versioned frozen grading template. Original defaults
are unchanged. Findings and the final decision are produced jointly from images,
unlike the independent observation stage of the intent strategy. Its callbacks
can be injected into CaliTree through the existing decomposition abstraction.

Offline replay verifies exact prompts, selected references, adjacent media
blocks, decisions and bounded-repair sequences for all 192 recorded image-backed
arms across the 64 development and 32 validation cases. This is implementation
parity, not additional model-quality evidence. Focused unit tests check withheld
query annotations, source-pixel leakage, cache/resume correctness, changed query
images, immutable training references, schema failures and the frozen fixture.

The full offline suite passes **901 tests**, with 23 live experiments skipped
and 52 existing warnings. `git diff --check` passes. These checks establish code
contracts, not perfect agreement with human labels.

The live script completed and checkpointed all 32 cases before a report-only
TypeError: its thread-pool variable shadowed the candidate-pool variable. A
separate offline finalizer reads the frozen manifest candidate count; it repeats
no calls and changes no decisions. Both sources are preserved.

Artifacts: `.cache/calitree-tests/vision-visual-calibration-fresh32-20260926/`
contains protocol/selection manifests, pixel provenance, source snapshots,
per-stage calls, checkpoints, results, the offline report finalizer and exact
core replay verification. Its `log_directory.json` identifies the corresponding
`logs/exps/...-exps/` full request/response history and run log. The repository
fixture is `tests/unit/calitree/fixtures/aurora_vision_calibrated_holdout32.json`.
These cases are now observed and must never be called fresh validation again.
There are 116 unused task IDs remaining, including four with already seen source
pixels: 112 remain eligible under the stricter source-pixel boundary.
