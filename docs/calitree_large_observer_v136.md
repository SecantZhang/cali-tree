# Larger-observer calibration and interpretable-policy controls

The verified policy remains **227/276 (82.2%)**, using the60-term semantic rubric. The strict over85% target is235/276. Original99/144 decisions and273/276 coverage remain retained. No new policy below has been promoted.

## 32B profile and bounded evidence

The pinned Qwen3-VL32B4-bit model loads at about18.27GiB. Its initial diagnostic keeps the original12 balanced training cases and original seven-state prompt/schema. One of four attempted cases is valid; three consecutive responses continue the evidence string until the512-token limit. Collection stops as specified, retaining all four outputs and1,691 tokens. This is an incomplete diagnostic, not an accuracy result.

A separate profile changes only the evidence-string schema to1–360 characters. It completes12/12 valid records using1,737 tokens. The independent v130 audit replays all native prompts/input shapes, checks raw content, model/program/image bindings, history and budgets. Peak observed MLX allocation is20,911,499,852 bytes, below the24GiB experiment guideline/observed-peak abort.

The simple grading-warrant mapping remains weak: three correct warrants out of12, versus five for the old8B observer. This is a balanced original-training diagnostic, not pipeline accuracy. The larger model does correctly report an absent endpoint/no progress in the can-dropping example, but its uncertain target identity prevents the old hard warrant from issuing No. These separate factual signals may still help a learned calibration policy; that hypothesis needs the full comparison below.

## Fixed review collection and comparison

V132 collects exactly the old224-input actual/OOS review union. It keeps the source/program/image order, instruction, per-fold masks and .8 support cue. Exact compatible diagnostic requests are reused with origin hashes. Every other slot receives one local attempt; failures remain unavailable and count in the full276-case denominator. The limits are224 fresh attempts/114,688 emitted tokens, one GPU observer, and no retries, API calls, uploads or reserved inputs.

V134 checks the new model/profile/raw records, exact diagnostic reuse, native CPU processor replay and accounting. It reuses the unchanged36-model teacher/source-mask audit by checking every pinned hash. A partial snapshot passes27 completed records and does not permit fitting.

After complete collection/audit, v135 compares eight fixed native residual fits: local/contextual vocabularies, depths2/3 and original-review anchors on/off. Three predefined decision modes use the same model weights: score-only, the old positive-warrant/independent-review guard, and an explicit absent/opposite-endpoint plus no/incidental-progress No alternative. The latter still requires one requirement, consistent bound claims, and does not use target uncertainty alone as failure.

Strength0–2 is selected using fitting-only accuracy/MSE after the actual guard, with a hard veto on all actual original decisions. Every fit checks all99 originals/144 slots, all276 scoring cases and unchanged outside-review behavior. Held-source siblings never enter fitting. The v136 one-shot supervisor waits for completion, audits the cache and runs this frozen comparison. It never starts/restarts an observer, promotes a policy or changes the goal status. Any improvement still needs independent native re-induction and bound runtime verification.

## Completed CPU controls

V133 replays36 existing residual models while choosing wider strengths after their real guards. Its18 arms score217–226/276. The matching v135 legacy-data control refits all eight configurations and24 arms; its best remains226. Original99/144 and273 coverage remain retained, but neither beats227. The strength limit alone is not the measured bottleneck in these controls.

A separate[InterpretML additive learner](https://interpret.ml/docs/ebm.html) tests a different accuracy/interpretability tradeoff over the existing cached inputs. It compares128 Boolean features with64 semantic features plus continuous SigLIP comparisons, main effects versus32 pair interactions, .5/1 blends with the old teacher, and prior/current-rule priority. Features are ranked from each fitting teacher only; original weight1/5/25 is selected by actual local retention, not held labels.

Every native main/pair table is exported, including multiclass pairs omitted by the library's global visualizer. Portable lookup-table probabilities match native predictions on all915 cases before scoring. All16 arms retain originals, but score191–213/276. They are not substitutes for the current policy. An initial missing feature-description export failure is retained separately; the corrected run uses a fresh experiment root.

Eighty focused tests pass. They cover exact additive-table cells/cut boundaries, named model/endpoint restrictions, binding, bounded evidence, incomplete-cache rejection, actual guarded strength selection and all existing expert/routing behavior. Tests make no neural/API calls.

## Evidence

- [Unbounded32B terminal audit](../logs/exps/261023-large-unbounded-terminal-audit-v130-r1/verification.json).
- [Bounded12-case audit](../logs/exps/261023-bounded-large-probe-audit-v130-r2/verification.json).
- [224-case collection protocol](../logs/exps/261023-large-review-cache-v132-r1/protocol.json),[source masks](../logs/exps/261023-large-review-cache-v132-r1/memberships.json).
- [Partial cache audit](../logs/exps/261023-large-cache-partial-audit-v134-r1/verification.json).
- [Wider-strength replay](../logs/exps/261023-decision-flow-strength-v133-r1/results.json),[matching refit control](../logs/exps/261023-decision-flow-refit-control-v135-r1/results.json).
- [Additive-policy comparison](../logs/exps/261023-additive-semantic-policy-v140-r2/results.json).
- [Live supervisor state](../logs/exps/261023-large-policy-pipeline-v136-r1/state.json).

These are repeatedly reviewed development data. The reserved80 sources remain excluded. The incumbent's exact8B checkpoint has been restored; the larger32B checkpoint is also present locally. The goal remains active and unmet.
