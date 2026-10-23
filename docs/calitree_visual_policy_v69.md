# Visual-semantic policy: updated accuracy goal

The updated **strictly over80%** target is met on the established source-held
development evaluation: **222/276 (80.4%)**, retaining **99/99 original examples
and all144 original training slots**. The source-held models exclude each held
decoded-pixel source and every sibling output. The final artifact is optional;
serving defaults are unchanged.

| Policy | Correct / 276 | Accuracy | Tree/policy coverage |
|---|---:|---:|---:|
| Regular judge | 183 | 66.3% | — |
| Prior boundary policy | 216 | 78.3% | 273/276 |
| Intent/explanation forest with gate .5 | 217 | 78.6% | 253/276 |
| Frozen visual-semantic policy | **222** | **80.4%** | **273/276** |

The evaluation contains84 source groups and uses the same five folds as earlier
experiments. Strictly over80% requires221 correct cases. Results include the
regular fallbacks and failures; accepted-only or fitting accuracy is not used.

This is a source-held **development estimate after model selection**, using
cached Luna frontend judgments. The separately reserved80-source evaluation has
not run. The result is not a claim of pristine final-set or universal unseen-case
accuracy.

## What changed

The policy adds fixed task-operation and regular-explanation cues to the existing
bound semantic predicates. A frozen local SigLIP2 encoder supplies comparative
image evidence: global/patch preservation, target correspondence, instruction
similarity changes, and desired-versus-alternative property margins. These scores
become fixed Boolean predicates. The new model uses357 selected predicates and
1200 shallow symmetric trees.

No raw embeddings, coordinates, object/color identity flags, editing-model IDs,
source/case identifiers or example lookups enter the classifier. Object text
only identifies the current input's target/property during visual preprocessing.
Language mentions and neural similarities are evidence cues, not factual or
calibrated confidence guarantees.

The frontend remains compiler-v3 → bound observer-v2 → interpreter-v5, with the
unchanged regular judgment providing a label and explanation. The visual policy
can propose a new grade rather than only voting over old expert labels. Missing
or mismatched bound evidence falls back to that regular judgment. Every visual
record is bound to the program, ordered image pair and frozen encoder recipe.

## Verification

- Independent audit rebuilds all915 visual comparisons from frozen encoder
  caches and refits all five source-held winning models plus the full fit.
  Each fit retains99/99 originals; the actual48 local slots per bank total144.
- Every source-held prediction is reproduced:222/276. Every held source's
  additional editor outputs are excluded from fitting.
- The saved JSON classifier matches native CatBoost predictions and class
  supports on all915 raw-bound inputs. The full fitting replay is906/915 with
  coverage903/915; these fitting numbers are not generalization results.
- A separate process re-encodes all915 image pairs through the reusable encoder
  and high-level judge, without human references. All visual predicates and
  frozen predictions match, including99/99 original predictions/coverage.
- 32 focused offline tests pass, including image-pair binding, closed feature
  validation, retained failed-slot fallback, numeric objectives and projections.
- No additional paid model requests or image uploads were made.

## Artifacts

- `logs/exps/261021-visual-goal-audit-v69/verification.json`: independent updated
  goal audit, including five held-source refits and144-slot retention.
- `logs/exps/261021-frozen-visual-policy-v69/policy.json`: portable inference
  artifact. It contains model parameters and encoder contracts, not examples.
- `logs/exps/261021-frozen-visual-policy-v69/verification.json`: native/JSON and
  bound-evidence replay of all915 cases.
- `logs/exps/261021-visual-runtime-replay-v69/verification.json`: actual915-case
  fresh local-encoding and high-level API replay.
- `logs/exps/261021-visual-policy-v64`: fixed vision-policy comparison.
- `logs/exps/261021-paired-vision-v63`: label-free local-encoder inputs,
  measurements and frozen preprocessing caches.

## Reusable inference

`VisualSemanticPolicy` is in
`critical/core/calibration/visual_semantic_policy_v69.py`.
`PairedVisionEncoder` is in `critical/vision/paired_encoder_v69.py`.
`VisualSemanticJudge` is in
`critical/core/optimization/prompt/calitree/visual_semantic_judge_v69.py`.

```python
policy = VisualSemanticPolicy(artifact)
encoder = PairedVisionEncoder(snapshot_path, policy.artifact['encoder_spec'])
judge = VisualSemanticJudge(calls, policy, encoder)
result = judge.judge(instruction, {
    'source_image': source_path,
    'edited_image': edited_path,
})
```

`calls` is the existing authorized, single-attempt API interface. No model calls
occur per tree/check node. Cached program/observations/interpretation/regular
judgment may be supplied; explicit `None` retains a failed slot without retry.
The tested local encoder uses Torch2.9.0, Transformers4.57.6, Pillow11.3.0 and
the Metal backend. It requires the pinned local safetensors/tokenizer assets and
performs no downloads or uploads during inference. CatBoost1.2.10 is needed for
fitting/replay of native models, not for portable JSON inference.

The exact encoder revision is
`google/siglip2-base-patch16-224@75de2d55ec2d0b4efc50b3e9ad70dba96a7b2fa2`.
Its model/processor hashes and feature contracts are embedded in the artifact.
The [official model card](https://huggingface.co/google/siglip2-base-patch16-224)
describes the pretrained encoder; it was not fine-tuned on the915 cases.

## Other completed investigations

Nested source-held mixtures reached at most214/276. Ordinal/relative-score
objectives did not beat the multiclass control; the relative-mean models lost
original accuracy and were ineligible. Continuous-score/coarse spatial variants
reached at most219/276, so they are not part of this artifact. The first numeric
run caught an invalid control-equality assumption: adaptive original weight1
need not reproduce the historical fixed-weight5 forest. The corrected experiment
keeps adaptive controls explicit and still reproduces the matching CatBoost
control. A detector smoke test was not developed further after the goal changed
from85% to80%.
