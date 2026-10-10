# Typed evidence edits: fresh chalk comparison

Completed 2026-10-08 after checkpoint `a3b80472e88be94bb4f3be4597c16cb3b67b2be1` was committed and verified on `origin/codex/decision-program-optimizer`. The new implementation and experiment remain uncommitted for review.

The test uses one previously observed case: “Turn the image into a drawing made from chalk,” case `aurora-task-ce641cb29939011016cc::mgie`, reference `partial`. Both greedy arms start from the exact original three-check seed saved in the previous controlled pilot's manifest. Images and seed hashes are verified. Historical final predictions, optimization feedback and audit approval were excluded; a fresh common seed audit was obtained.

## Results

| Method | Seed → selected reference matches / 5 | Selected usable / 5 | Selected checks | Added nested check executed? | Locally robust? |
|---|---:|---:|---:|---|---|
| Criterion-only | 0 → 2 | 2 | 3 | No; this arm forbids insertion | No |
| Nested-required | 0 → 0 | 5 | 4 | Yes, `n4` in all five draws | No |

Each seed and selected program had five fresh final draws. Matches mean equality with the saved `partial` label. Usable means a resolved answer, including wrong answers. Repeats remain measurements within one case. Both selections were frozen before any final query.

**The graph-construction fix worked:** the nested-required arm produced an audited program containing the new evidence-context check, and executed it as `n1 → n2 → n4 → n3`. Its readout consumed all three supports in order. There was no sibling-dependency wiring rejection. **The resulting judge did not match the reference:** all five final predictions were `yes`.

The criterion-only arm produced `partial` twice and remained unresolved three times. Its chalk-medium support was unknown in three draws, preventing the evidence-only readout from executing. It did not meet full coverage, consistency or minimum eligible-observation thresholds.

## Actual nested component

The selected `n4` question was:

> Does drawing-like rendering extend across the whole image, including the giraffes and background, rather than leaving substantial areas photographic or applying only a localized chalk-like treatment?

Code constructed these executable fields from the typed insertion request:

```text
n4.parent = n2
n4.dependencies = [n2]
n3.parent = n4
n3.dependencies = [n1, n2, n4]
saved order = [n1, n2, n4, n3]
```

All four checks were queried in every selected final draw. `n1`, `n2` and `n4` each returned pass in 5/5 draws; `n3` returned complete in 5/5. Their repeat consistency was 1.0. Minimum reported confidence was 0.91 across the program, and 0.96 for the added extent check. These high, consistent self-reports do not establish correctness: agreement with the `partial` reference was 0/5.

The selected nested candidate also had a complete five-draw confirmation report: 0/5 matches, 5/5 resolved coverage. It was retained as the best available audited structural candidate, not declared successful. The final status is `unconfirmed`, meaning confirmation did not qualify; its acceptance reasons include target mismatch. The stable disagreement is flagged as a suspected reference conflict, not proof that the annotation is wrong or permission to weaken requirements.

## Criterion-only component

This arm revised both support criteria and the readout. Its chalk-medium check distinguished affirmative chalk evidence from grain, blur or smudging alone. Its drawing-form check distinguished drawn content from a photographic scene with effects.

- Chalk-medium support: pass 2/5, unknown 3/5; consistency 0.4.
- Drawing-form support: fail 5/5; consistency 1.0.
- Fulfillment readout: queried twice, returning partial twice; three required-unknown draws remained unresolved.
- Minimum selected reported confidence: 0.88. Confidence passed the final confidence gate, while coverage and stability failed.

Complete confirmation existed but did not qualify: 1/5 reference matches, 1/5 resolved coverage. A transport failure in that confirmation schedule was retained rather than resampled. Both arms therefore failed confirmation and fresh final robustness, without budget exhaustion.

## Proposal and compilation outcomes

The first nested transaction supplied an insertion with empty `readout_criteria`, followed by a separate `revise_readout` action. The declared insertion contract requires explicit criteria on the insertion itself, so it was rejected. The next typed transaction constructed a valid graph but failed its semantic audit. The final insertion constructed a valid graph, passed its audit, and was executed and confirmed. These distinct rejection stages are recorded in lineage; no invalid proposal was silently rewritten.

The independent ordered-compilation probe returned one broad support specification, despite the two-or-three-support requirement. It was rejected by count validation and was not retried or used as a seed. Thus this test demonstrates typed insertion and execution, but does not demonstrate a successful live ordered-compilation result. Offline compiler tests verify deterministic roles, IDs, ancestry and evidence context for valid specifications.

The fresh seed audit rejected the original composition's evidence sufficiency. Diagnostic-only execution still enabled native TextGrad feedback and visual discovery. Those diagnostic scores were excluded from screening/confirmation frontiers and acceptance. Every accepted candidate had its own label-blind semantic audit.

## Protocol and usage

- GPT-6 Luna at the official OpenAI API, temperature zero, reasoning `none`, random seed `20261008`; returned identity `gpt-6-luna` throughout.
- Two rounds with one then two batches; two proposal opportunities per batch, at most six candidate opportunities per arm.
- 109 search calls per arm, two shared preparation calls, and 80 reserved final calls. Ceiling: 300 calls / 384,000 completion tokens.
- Checker outputs capped at 1,024 tokens; compilation, feedback, discovery, proposals and audits at 2,048.
- Total calls: **140/300**. Reported completion tokens: **13,649**. Charged completion tokens: **15,697**, including two retained 1,024-token failure reservations. Input tokens: **246,155**.
- Two transport failures occurred during search: one candidate-screen support call and one criterion-only confirmation support call. No final call failed, no slot was retried, and no model was substituted.
- Full offline suite before live execution: **1,260 passed, 23 skipped**. Typed suite: **23 passed**; broader focused compatibility suite: **109 passed** before the final diagnostic-message assertion update.

After the run, a failure-classification regression test was added: invalid optional seed compilation must remain unresolved, rather than being classified as absence of an eligible nested candidate. Delivery checks pass **1,261 tests, 23 skipped**, with **24 typed tests**. This does not modify the measured programs or predictions; their recorded source snapshot is used for replay.

This is a successful mechanical repair and a negative accuracy/robustness result on one local fitting case. Different model families, calibrated confidence, atomic ground truth and generalization are not evaluated here.

## Saved artifacts and reproduction

Measured run: `logs/exps/261008-typed-evidence-chalk-v2`. The earlier `...-v1` directory is an unattempted preflight snapshot; it made no model calls. Both are retained.

The measured directory contains manifests and exact source snapshots, compilation failure and fresh audit, frozen seed/selected programs, typed transactions and expanded graph changes, provenance, per-check observations, gradients/discovery, predictions, confidence, usage and acceptance reasons. `component_analysis.json` contains all candidate construction and rejection detail; `analysis.md` presents distributions and confirmation results.

Recompute saved-data analysis and complete-result replay with the frozen runtime, without API calls:

```bash
PYTHONPATH=. .venv/bin/python logs/exps/261008-typed-evidence-chalk-v2/replay_frozen_analysis.py
```

Protocol verification passed: image/program/source hashes, typed-construction replay, label and media isolation, ordered dependency acknowledgments, budget ceilings, final-stage isolation and **zero-call complete-result replay**. Final outcomes were not used to retune or replace either selected program.
