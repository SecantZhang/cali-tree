# Observer diagnostics and the remaining accuracy gap

The verified policy remains **227/276 (82.2%)**, using the60-term semantic rubric. The strict target is235/276. All99 original decisions,144 original slots and273 upstream covered cases remain retained. None of the observer variants below is promoted.

The newer[32B calibration report](calitree_large_observer_v136.md) records the bounded12-case diagnostic, the active224-case review collection, and completed wider-strength/additive-policy controls. The verified score remains unchanged.

## Completed higher-resolution comparison

The v108 cache completed224 fresh attempts,219 accepted observations and27,164 output tokens. Five failures remain unavailable. The v109 audit passes36 native teachers, source/fold masks, exact request/response bindings and accounting. All276 primary cases remain in scoring.

The frozen four residual fits with score/guarded variants score219–225/276. The best guarded arm is225, with two gains/two losses versus the prior225 base; it does not beat the verified227 policy. Original99/144 decisions and273 coverage are retained. No policy export/promotion follows this negative comparison.

The input audit previously showed187/224 identical processor outputs under both pixel budgets. Raising the cap supplied different image tensors to37 inputs and did not improve this particular comparison. This does not establish that resolution can never help.

## Compact MLX observer

The separate Qwen3.5-9B4-bit runtime produces12/12 valid records on the original balanced training diagnostic. The v120 audit replays all native rendered prompts/input shapes and checks raw records, history and budget. Peak observed MLX allocation is about7.16GiB; the model-only allocation is about5.54GiB. The8GiB setting is an MLX allocation guideline with an observed-peak abort, not an operating-system memory isolation mechanism.

The model's structured states often fail to support the human grade. In one can-dropping example, its evidence says the can did not fall while its endpoint field says achieved. This is a genuine inconsistency between its own outputs. Valid JSON and familiar predicate names do not make a visual claim correct.

The following are **warrant-only results on12 balanced original training cases**, not pipeline or population accuracy. Failed/unwarranted inputs stay in the12-case denominator. The existing pipeline already retains all these original decisions; no new observer is allowed to degrade them.

| Observation profile | Valid records | Warrants supplied | Correct warrants /12 |
|---|---:|---:|---:|
| Original Qwen3-VL8B |12|11|5|
| Qwen3.5-9B, greedy direct |12|12|4|
| Evidence first, reordered original prompt |12|10|4|
| Evidence first, extra consistency/anchor/progress guidance |12|6|3|
| Published sampled instruct settings |12|11|4|

Evidence-first decoding enforces native JSON field order and a360-character evidence limit. It does not repair earlier outputs. Both arms preserve all raw text and exact request/profile bindings. The v123 audit passes24 native processor replays. Ordering and added guidance did not improve the diagnostic, so these views are not expanded into a new controller.

The[model's published settings](https://huggingface.co/Qwen/Qwen3.5-9B) also provide a reasoning mode. A separate seeded diagnostic bounds each case to2,048 reasoning tokens plus512 final tokens. It accepts a final observation only after the model emits its native closing-think token. All three attempted reasoning cases exhausted their reasoning allowance without a final channel; collection stopped under the frozen three-failure rule. The remaining nine cases were not attempted. No correctness rate is inferred from this incomplete arm, and no thought text is treated as an observation.

The v126 terminal audit independently decodes all generated token IDs, checks native thought/final boundaries, per-channel counts, seeds, full native histories and final JSON. The audit passes; the planned reasoning diagnostic remains incomplete. The sampled instruct arm used1,375 tokens, the three truncated reasoning cases used6,144, and neither arm fitted or changed a policy.

## Runtime provenance and next evidence source

The image-only diagnostic needed native Torch/torchvision processor helpers in its isolated MLX environment. Earlier setup failures are retained: two failed model/tokenizer preflights and three processor-format failures, with zero decoded tokens. Later frozen profiles fix the compatibility issues; failed outputs are not replaced or repaired. Core enforcer integration supports the installed Transformers5 tokenizer API, and both recognized model/text and chat terminal IDs are handled explicitly. Seventy focused tests pass, including token masking, input/endpoint restrictions, native field order, channel separation, truncation and separate token budgets.

A larger[Qwen3-VL32B4-bit checkpoint](https://huggingface.co/mlx-community/Qwen3-VL-32B-Instruct-4bit) is downloaded and hashed as the next local candidate. Its revision and19,620,448,683 weight bytes were pinned before download; no task data or credentials were sent. It has not yet been tested, and its size alone does not establish better task accuracy.

Temporary8B/9B weight caches were evicted after their owning jobs ended. Metadata, processor files and cached records remain. Available disk space rose after job termination; the incumbent8B checkpoint is restored to its original path, with its entire file-hash map matching the original identity. About48GiB remains free with the incumbent and larger checkpoint present. The negative9B checkpoint can be restored from its pinned download metadata if needed again. No dataset image, fitted classifier or policy artifact was removed.

## Evidence

- [Current60-term policy verification](../logs/exps/261023-verified-semantic-compression-v112-r2/verification.json).
- [Complete resolution cache audit](../logs/exps/261023-high-resolution-cache-audit-v109-r1/verification.json),[all comparison results](../logs/exps/261023-high-resolution-semantic-residual-v103-r1/results.json),[completed supervisor](../logs/exps/261023-high-resolution-pipeline-v110-r1/state.json).
- [Greedy MLX diagnostic audit](../logs/exps/261023-verified-mlx-probe-v120-r1/verification.json).
- [Evidence-first paired audit](../logs/exps/261023-verified-evidence-first-v123-r1/verification.json).
- [Native sampled-channel terminal audit](../logs/exps/261023-native-channel-terminal-audit-v126-r2/verification.json).
- [Larger checkpoint download](../logs/exps/261023-large-mlx-download-v127-r1/identity.json),[incumbent restoration](../logs/exps/261023-incumbent-checkpoint-restoration-v94-r1/identity.json).

All new observation calls are local. There are zero additional paid API calls, uploads or reserved-source uses. The >85% objective remains active and unmet.
