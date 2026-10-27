# Shared semantic terms with unchanged accuracy

**Selected for AURORA inference on 2026-10-25.** Use the default `CaliTreeJudge`
API or `python -m run.calitree_current --describe`. The selector is
`critical/core/calibration/artifacts/calitree_current.json`; the default-path
replay reproduces all915 cached outputs and routes. See the
[selected-version usage](../examples/calitree_weighted_semantic_v112/README.md)
and [selection verification](../logs/exps/261025-selected-v112-r1/verification.json).

The verified rubric now uses **60 shared terms instead of100 branches**, a40% reduction, with the same **227/276 (82.2%)** source-held development accuracy. All99 original inputs,144 original slots and273 covered cases remain unchanged. The strict235/276 target is still unmet.

The full artifact uses28 named concepts,33 individual conditions and27 two-condition interactions. The operational grading guard is unchanged: a different grade needs either an affirmative local single-requirement warrant or selection of the existing regular judge with a positive review reason. Uncertainty alone cannot establish failure, and unrelated collateral does not automatically cap success.

## How sharing works

A depth-two tree with Boolean tests`x` and`y` can be written as:

```text
v00 + (v10-v00)*x + (v01-v00)*y + (v11-v10-v01+v00)*x*y
```

Each`v` is a vector of adjustments to the No, Partial and Yes scores. The constant goes into a shared intercept. Equal individual conditions and equal interactions share one term across all128 trees. Repeated numeric lower bounds reduce to the strictest bound; native float32 threshold behavior is preserved. No fitting, weight pruning or human-label-based rule deletion occurs during this algebraic compression.

The policy begins with the teacher's class supports, adds the weighted semantic terms, floors and normalizes the masses, and chooses the largest class. A term describes a conditional statistical adjustment, not a standalone grading command. All matching terms combine, so one weight does not imply that its condition alone determines the grade. The explicit positive-warrant/review guard remains the semantic limit on overrides.

The shorter form makes individual effects and interactions easier to inspect. Its generalization behavior is unchanged because it represents the same function. Further simplification that changes the function must earn its accuracy separately.

## Verification and smaller alternatives

The v112 audit re-induces all six selected models, compares5,490 native residuals with the shared-term expression and replays915 cached inputs through the actual bound inference adapter. Maximum score difference is5.56e-16; predictions, coverage and routing match exactly. The five source-held models retain227/276, while the exported full-data model reproduces the uncompressed full-data artifact on915 inputs. The latter is an inference-equivalence check, not another held-out accuracy result. Fifty-two focused tests pass, including exhaustive two-test branches, repeated thresholds, constant models and existing bound-observer/expert behavior.

Four12/24-term regularized interaction fits yield215–224/276 across score/guarded arms. Four rationale-word-free semantic fits yield224–226. They retain original local decisions but do not match227, so they are not substituted for the60-term artifact.

## New evidence work

The separate v108 higher-resolution collection completed224 responses/219 accepted. The complete native/cache audit passes; the frozen comparison scores219–225/276 and is not promoted. An independent processor audit compares actual token IDs, masks, image grids and pixel tensors for all224 planned inputs. **187/224 have identical processor outputs** under both pixel budgets; only37 receive different image inputs. Most native images already fit inside the original cap. A label-free partial observation snapshot also found54/55 accepted pairs with identical seven-field claims. See[the completed observer report](calitree_observer_diagnostics_v126.md) for the accuracy comparison and subsequent training-only diagnostics.

A separate public[Qwen3.5-9B4-bit checkpoint](https://huggingface.co/mlx-community/Qwen3.5-9B-4bit), derived from[Qwen's published model](https://huggingface.co/Qwen/Qwen3.5-9B), was tested as another observation source. Its native records are valid, but direct, evidence-first and sampled instruct profiles do not improve the12-case training-only warrant diagnostic. Its bounded reasoning profile stopped after three unfinished cases. The[MLX-VLM runtime](https://github.com/Blaizzy/mlx-vlm) is isolated and pinned; no benchmark images, prompts or labels are uploaded. These profiles are not part of the verified accuracy claim. A32B candidate is now being downloaded after completed jobs released resources; see the newer report for the exact evidence and cache-restoration status.

## Artifacts

- [Compression verification](../logs/exps/261023-verified-semantic-compression-v112-r2/verification.json),[per-fold counts](../logs/exps/261023-verified-semantic-compression-v112-r2/compression.json).
- [Opt-in policy](../examples/calitree_weighted_semantic_v112/policy.json),[executable rubric text](../examples/calitree_weighted_semantic_v112/rubric.txt),[usage](../examples/calitree_weighted_semantic_v112/README.md).
- [Original accuracy/routing audit](../logs/exps/261023-verified-semantic-residual-v105-r1/verification.json).
- [Sparse interaction comparison](../logs/exps/261023-sparse-interaction-rubric-v113-r1/results.json),[rationale-free comparison](../logs/exps/261023-semantic-abstraction-v114-r1/results.json).
- [Actual image-input audit](../logs/exps/261023-effective-image-inputs-v117-r1/verification.json),[label-free snapshot](../logs/exps/261023-resolution-agreement-v115-partial-r1/results.json).
- [New public checkpoint identity](../logs/exps/261023-local-mlx-download-v116-r1/identity.json).

All276 scored cases remain repeatedly reviewed development data. The original
compression audit left serving defaults unchanged; v112 was subsequently
selected for inference on2026-10-25 with its weights and predictions unchanged.
The broader accuracy target remains unmet.
