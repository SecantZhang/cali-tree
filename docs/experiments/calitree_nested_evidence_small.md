# Small live test of missing/nested evidence repair

Completed 2026-10-08 on **one previously observed chalk case**, using GPT-6 Luna at the official OpenAI API, temperature zero and reasoning `none`. Compilation, checks, audits and visual discovery excluded the reference label; native TextGrad feedback and proposals could use it. The experiment used one reviewer from the primary model family, so it does not test benefits from different families.

Instruction: “Turn the image into a drawing made from chalk.” Saved reference: `partial`. Case: `aurora-task-ce641cb29939011016cc::mgie`. Source hash: `76a06e20f42156268378372428ce173605b34af5db9f80e995c08ead17c4099a`; edited hash: `4595aa2c3cabf3bdd81bb18de8a4e937c50c39e5d9ec798cbbb3be647c734be0`.

## Final results of the controlled saved-seed test

Each seed and selected program received five fresh final draws. These are repeats within one case, not additional cases. Selection was frozen before final verification.

| Method | Seed → selected reference matches / 5 | Selected usable answers / 5 | Lowest reported confidence | Selected checks | Passed robustness gates? |
|---|---:|---:|---:|---:|---|
| Broad–greedy | 0 → 4 | 5 | 0.94 | 1 | Yes |
| Decomposed–greedy with visual discovery | 0 → 2 | 5 | 0.91 | 3 | No |

“Reference matches” counts predictions equal to `partial`; unavailable or invalid draws count as nonmatches. “Usable” means a resolved label, including incorrect answers. Confidence is model self-report. Robust acceptance also requires semantic-audit approval, at least 4/5 matches, 5/5 coverage, and requirement/check consistency of at least 0.8. High confidence alone cannot satisfy those gates.

The revised decomposition improved reference agreement, but **did not become locally robust**. It returned `partial` twice and `yes` three times. Its drawing-form check switched between fail (2/5) and pass (3/5), producing consistency 0.6. The fulfillment readout had the same consistency. Both fall below the 0.8 threshold, and target agreement falls below 4/5.

Search reached its reserved-budget boundary while confirming the selected candidate. A full confirmation report was therefore unavailable; the search status is `budget_exhausted`. The candidate was retained on its valid screening evidence and then evaluated with the frozen final schedule. Final observations did not cause replacement or further optimization.

## What the repair mechanism actually did

The explicitly promoted historical seed contained:

1. `n1`: inspect chalk-like medium or surface treatment.
2. `n2`: inspect whether the content appears drawn rather than remaining an unchanged photograph.
3. `n3`: judge the original requested transformation using those two saved observations, without images.

Its fresh semantic audit rejected the assumption that two coarse passes establish whole-image conversion. Unlike the earlier optimizer, the new path executed it once for diagnostic-only feedback, and native backward calls and label-blind visual reviewers inspected the resulting observations. That diagnostic score never entered the candidate frontiers or acceptance.

Discovery identified the intended finer question: does drawing conversion extend across the full image, including the background, or does substantial photographic appearance remain? The proposer attempted to add an `n4` support under `n2`, with `n2` as evidence context. **Both nested insertions were rejected** because they added `n4` to the readout dependencies but left `n3.parent = n2`. This made `n4` a sibling of the readout rather than its ancestor, violating the executable dependency contract. The validator did not silently repair or execute either proposal.

One criterion revision passed its label-blind semantic audit. It tightened `n2` to ask:

> Are the depicted forms visibly rendered as a drawing, rather than retaining photographic structure with only chalk-like texture, blur, or softened outlines?

The original chalk-treatment support and evidence-only readout remained. The selected program's hash changed, but its check count remained three; **no additional or nested check was executed**. The observed improvement therefore comes from criterion repair, not demonstrated nested-tree optimization.

This result supports the availability of visual diagnosis and evidence-gap discovery. It exposes a remaining limitation in generated tree transactions. A useful next engineering step is a typed insertion operation that constructs valid ancestry and updates the readout's parent/dependencies together, while leaving proposed semantics subject to audit. More reviewer families cannot by themselves fix invalid wiring.

## Preserved first attempt

The first attempt used fresh label-free compilation. It completed 38 calls, but the compiler generated separate root supports and a root readout that referenced them, plus nonempty outcome IDs on supports. Those definitions violate the ancestor-only evidence and support-role contracts. Preparation was recorded as invalid; there was no decomposed optimizer run or fabricated visual feedback. The broad arm completed separately, matching the reference in 5/5 selected final draws.

That attempt remains at `logs/exps/261008-nested-evidence-small-v1`. Compiler guidance was clarified to distinguish independent evidence from independent roots and to require empty support outcome IDs. The clarification was tested offline; it was not measured through a second compilation call.

The controlled corrective attempt instead promoted the **original label-free seed** from the historical saved leaf, obtained a new semantic audit, and used fresh slots. Historical labels, optimization traces, gradients, selected candidates and audit approval were excluded from its preparation. The prior preparation failure was preserved and was not resampled.

## Budget, failure accounting and verification

The whole small test was capped at **150 calls and 192,000 completion tokens**, including both attempts. The first attempt used 38 calls; the saved-seed attempt inherited a remaining ceiling of 112 calls. Each attempt reserved all possible final comparison calls before search: 10 for the broad arm and at most 40 for decomposition.

- Total calls: **139** = 38 + 101.
- Reported completion tokens: **13,103** = 3,210 + 9,893.
- Charged completion tokens: **14,127**, including a 1,024-token reservation for one failed call.
- Input tokens: **216,451**.
- One transport failure occurred in the decomposed seed's fourth final draw at `n2`. It remained unresolved and was not retried. Selected final draws all resolved.
- Returned model identity: `gpt-6-luna` throughout. No model substitution or automatic schema repair.
- Focused suites before the controlled test: **40 passed**. Full offline suite: **1,237 passed, 23 skipped**.
- Frozen-source analysis and complete-result replay passed for both attempts with **zero new model calls**. Checks verified image/program/source hashes, label isolation, readout media isolation, dependency acknowledgments, budgets and final-verification isolation.

This is a negative local robustness result for the decomposed method. Matching a case label does not certify component correctness, and this one previously observed case cannot establish generalization.

## Reproduction and artifacts

First attempt: `logs/exps/261008-nested-evidence-small-v1`. Controlled attempt: `logs/exps/261008-nested-evidence-small-seeded-v1`. Each retains a manifest, exact source snapshot, jobs and usage, preparation, frozen programs, observations, predictions, audits, edit history, reports and verification. The controlled attempt pins the prior manifest/budget and historical seed hashes.

Recompute analysis and replay saved observations under the frozen runtime, without API calls:

```bash
PYTHONPATH=. .venv/bin/python logs/exps/261008-nested-evidence-small-v1/replay_frozen_analysis.py
PYTHONPATH=. .venv/bin/python logs/exps/261008-nested-evidence-small-seeded-v1/replay_frozen_analysis.py
```

The controlled attempt's `analysis.md`, `component_analysis.json`, `usage_summary.json` and `protocol_verification.json` contain the full node distributions, proposal diagnostics, confidence and usage. Its completed configuration can be resumed with the existing runner and saved flags; completed slots are replayed, not resampled. No additional experiment is started automatically.
