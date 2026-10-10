# Proposer-only GPT-6.1 Sol comparison

## Result

Completed `logs/exps/261008-sol-proposer-v1` on the saved jacket, paper/cup and frog cases. These are previously observed local fitting problems, one per reference class. Saved label-free common seeds and original images/bindings were retained. All observations, feedback and audits were fresh; no previous optimizer feedback or final traces were reused.

| Proposer | Transactions proposed | Approved by the same Luna semantic reviewer | Seed → selected final reference matches / 15 | Selected resolved draws / 15 | Robust leaves / 3 |
|---|---:|---:|---:|---:|---:|
| Luna | 37 | 1 | 4 → 0 | 8 | 0 |
| Sol 6.1 | 11 | 9 | 5 → 1 | 6 | 0 |

An approved transaction is the model reviewer's assessment of meaning preservation, not proof of correctness. Each case had five fresh final executions per program and arm; repeats are not independent cases. The two arms' starting-program scores differ because they used independent draws. This comparison retained the forced-added-check restriction; it is not a comparison against the successful criterion-only optimizer.

Sol improved proposal acceptance substantially in this small sample, but that did not produce reliable case decisions. Selected programs regressed relative to their seeds. No seed or selected candidate met every audit, confirmation, activation, coverage, consistency and confidence gate.

## Configuration and accounting

- All visual judging, native TextGrad backward feedback, visual discovery and semantic review used GPT-6 Luna with temperature zero and reasoning `none`.
- Only the Sol arm's proposer used GPT-6.1 Sol with `medium` reasoning and temperature omitted. This is a comparison of two supported model/configuration packages, not model size alone.
- Both proposers had a 4,096-completion-token cap. Other non-checker calls were capped at 2,048 and checkers at 1,024.
- Up to fifteen rounds and two transactions per round; 109 search / 40 final calls per case-arm. Search can exhaust its call allowance before completing fifteen rounds.
- Ceilings: 900 calls / 1,152,000 completion tokens, with 240 final calls / 245,760 tokens reserved. All six selections froze before any final draw. Final results never reopened search.
- One HTTP attempt per durable slot; failures preserved, no schema repair, no model substitution. No global transport stop occurred.

Actual usage: **739 calls**, including **37 Sol proposal calls** and **173 fresh final calls**. Charged completion tokens: **152,625**. Reported input tokens: **3,327,286**. Fourteen transport failures were retained; 725 requests completed. Returned identities were `gpt-6-luna` and `gpt-6.1-sol`.

At the recorded uncached list prices, reported tokens estimate $1.367 for Sol and $0.3258 for Luna, about **$1.69 combined**. This excludes unknown usage on failed requests and cached-input discounts; it is not an invoice. See `usage_by_model.json` for the exact assumptions and recorded pricing source.

## Actual failure mechanisms

### Jacket: uncertainty blocked independent follow-up checks

Sol's selected four-check program began by comparing source-to-edit closing progress. That check returned unknown in all five final draws. The direct completion check depended on it, and the added panel-attachment check depended on both. The runtime consequently queried neither later check. No final decision was produced.

The graph passed structural and semantic review, but evidence supplied as context became a mandatory known prerequisite. A later independent image check could not attempt to resolve the uncertainty. `structural_failure` in the final report includes insufficient execution of an added check; this case was not a malformed graph.

### Paper/cup: precise-looking questions still left the decision unknown

The Sol program produced a receiver inventory and nested boundary/overlap map. Both returned pass in 5/5 final draws. Its next question combined completed stuffing, affirmative incompleteness, unresolved completion and established progress. That check returned unknown four times and fail once. The final rule executed once and matched the `no` reference.

The Luna selected program similarly added a comparative-progress check that returned unknown 5/5. Both selected programs lost resolved coverage relative to their seeds. More semantically approved questions therefore did not guarantee decisive evidence.

### Frog: stable disagreement with the reference

Sol's program asked about a recognizable frog at the bowl, added placement progress, and actual bowl-interior occupancy rather than exterior overlap. All three checks passed in 5/5 final draws. The readout returned complete every time, while the reference was partial. This was a resolved disagreement, with no direct final-call transport failures.

The result cannot establish whether the visual judge is wrong or the stored rubric/reference interpretation is misaligned. An independent review of the actual images and reference rationale is needed. Requirements must not be weakened or invented solely to force the partial label.

## Proposed next repairs

These proposals are not implemented in this controlled model comparison:

1. Separate advisory ancestor context from factual prerequisites. Allow a follow-up check to run when its context answer is uncertain; permit completion from sufficient approved evidence without requiring an irrelevant progress comparison. Required unresolved facts still block decisions where they are needed.
2. Require one observable proposition per evidence check. Keep identity/inventory, progress, completion and ambiguity explicit, with clear positive and negative meanings. A check that can produce a map is not itself evidence that an edit progressed.
3. Accept safe revisions/removals and added checks under the same production policy. Keep forced insertion as an ablation. Preserve an audited qualifying incumbent rather than making program growth a prerequisite.
4. Use a frozen instruction-grounded semantic contract and structured review diagnostics. Require citations to the original clause and a concrete unsupported conclusion/counterexample. Distinguish meaning preservation, decision coverage and runtime sufficiency rather than conflating them.
5. Spend confirmation calls on resolved, target-matching screens; retain other valid candidates as repair intermediates. This should be tested separately because it changes search allocation.
6. Diagnose persistent rubric/reference disagreements explicitly. Use bounded independent visual review or better target-region evidence where appropriate; do not silently relabel or add unsupported requirements.
7. Keep transport/schema failures out of visual-error feedback and report infrastructure-incomplete verification separately. Preserve every attempted slot and end-to-end coverage; a revised confirmation procedure needs its own version and experiment.

## Verification and reproduction

Before live execution: 29 focused tests passed; full offline unit suite **1,281 passed, 23 skipped**. Verified supported Sol wire parameters, unchanged legacy defaults, same-ledger/same-case routing, label isolation, reserved budgets, all-selections-before-finals ordering and zero-call resume.

Saved-data analysis verified source/runtime/image hashes, original requirement preservation, deterministic edit replay, Sol routing only on proposer calls, output caps, model-call limits and full zero-call replay:

```bash
PYTHONPATH=. .venv/bin/python logs/exps/261008-sol-proposer-v1/analyze_saved_run.py
```

Exact programs, transactions, audits, observations, predictions and durable jobs remain in the experiment directory. `analysis.md`, `summary.json`, `component_analysis.json`, `usage_by_model.json` and `protocol_verification.json` contain the detailed results. No commit or push was made.
