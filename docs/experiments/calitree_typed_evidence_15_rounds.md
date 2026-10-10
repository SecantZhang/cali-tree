# Fifteen-round loop: repeat on the saved chalk case

Completed 2026-10-08 using the **same case, source/edited image hashes, original three-check seed and two methods** as the previous typed-evidence pilot. The case was previously observed and is a local fitting problem, not a held-out generalization test.

Instruction: “Turn the image into a drawing made from chalk.” Reference label: `partial`. Case: `aurora-task-ce641cb29939011016cc::mgie`. Model: GPT-6 Luna at the official OpenAI API, temperature zero, reasoning `none`; returned identity `gpt-6-luna` throughout.

## Results

Both seed and selected programs received five fresh final draws after both selections were frozen.

| Method | Seed → selected reference matches / 5 | Selected usable / 5 | Repair rounds completed | Search stopped because | Selected checks | Locally robust? |
|---|---:|---:|---:|---|---:|---|
| Criterion-only | 0 → 0 | 3 | 11; round 12 started | Per-arm 109 search calls exhausted | 3 | No |
| Nested-required | 0 → 5 | 5 | 4 | Complete confirmation qualified | 4 | Yes |

Reference matches count labels equal to `partial`; unresolved draws are nonmatches. Usable answers include incorrect labels. Fifteen rounds is the maximum, with early confirmation success and enforced budgets taking precedence. The criterion-only arm did not complete fifteen rounds, and the nested arm did not need to.

The nested candidate had **5/5 matching confirmation draws and 5/5 matching fresh final draws**, full resolved coverage, requirement/check consistency 1.0, semantic-audit approval and minimum reported confidence 0.94. Its inserted `n4` check was queried in every final draw and consumed its ancestor `n1` observation. Its routing parent was `n2`; routing and evidence context are distinct. It met the frozen local acceptance gates.

Criterion-only final predictions were `yes` three times and unresolved twice. Two final support calls failed in transport and were retained. Confirmation already failed before final execution: 2/5 matches with full coverage. Search used those failures as repair feedback, but no candidate reached all confirmation gates within its allowance.

## The useful added check

The selected `n4` question was:

> Does the chalk-like treatment visibly render the scene's major content and background as a drawing, rather than mainly adding chalky texture or outlines to photographic content?

Its criteria distinguish broad rendering as drawn forms from substantial photographic content remaining under a chalk-like or sketch-like treatment. This focuses on genuine conversion of depicted forms, rather than simply whether a treatment is present across the image.

Actual first final draw:

| Node | Result | Reported confidence | Saved evidence |
|---|---|---:|---|
| `n1`: chalk-like treatment | pass | 0.94 | Grainy, smudged surface treatment, softened sketchy outlines and dusty texture were visible. |
| `n2`: drawing-like appearance | pass | 0.98 | Sketch-like outlines and shading were reported on the giraffes and surroundings. |
| `n4`: broad conversion versus treatment over a photograph | **fail** | 0.94 | “The chalk-like grain and softened outlines are visible, but the giraffes and much of the background retain photographic detail and shading rather than being broadly rendered as drawn forms.” |
| `n3`: fulfillment | **partial** | 0.96 | Chalk/drawing cues provide progress, while photographic detail establishes incomplete conversion. |

The same pass/pass/fail/partial combination occurred in all five final draws. The readout explicitly treats the original supports as coarse evidence of chalk/drawing cues and uses `n4` to investigate completeness. A known negative supporting observation is usable evidence; it does not automatically make the program unresolved.

Code constructed `n1 → n2 → n4 → n3`, `n4.dependencies = [n1]`, and `n3.dependencies = [n1, n2, n4]`. Supporting checks earned no completion credit. The requested outcome, original provenance and fixed aggregation remained unchanged.

## What the longer loop demonstrated

The criterion-only arm had a candidate fail five-draw confirmation. Rounds **7–12** explicitly chose that failed candidate as the repair parent and forwarded its confirmation rejection and repeated traces, demonstrating the new follow-up behavior. It completed round 11 and exhausted its search quota during round 12.

The nested arm found its first qualifying candidate in round **4**, outside the previous two-round schedule. It therefore stopped before round 15. There was **no failed-confirmation nested parent in this particular rerun**: this demonstrates additional opportunity to find a useful inserted check, not a measured rescue of the exact previously failed `n4` program. Historical final observations and optimization feedback were excluded from the new search.

Previous two-round final results versus this rerun:

| Method | Previous selected matches / 5 | Current selected matches / 5 | Previous → current usable / 5 |
|---|---:|---:|---:|
| Criterion-only | 2 | 0 | 2 → 3 |
| Nested-required | 0 | 5 | 5 → 5 |

These are separate fresh local experiments, with model-output variation and a changed search schedule/follow-up policy. They do not isolate a causal effect of round count or establish generalization. Confidence is generated self-report, and reference agreement does not certify each atomic observation.

## Failures and accounting

- Global ceiling: **300 calls / 384,000 completion tokens**. Per-arm search limit: **109** calls. Reserved final allowance: **80 calls / 81,920 tokens**.
- Used **224 calls**: two shared preparation calls, 109 criterion-only search calls, 50 nested-required search calls, and 63 final calls. The remaining global allowance cannot override the frozen per-arm search cap.
- Reported completion tokens: **26,610**. Conservatively charged completion tokens: **35,826**. Input tokens: **490,425**.
- **Six transport failures**: four search calls and two criterion-only final support calls. All failed slots were retained; none was retried. No global provider stop or model substitution occurred.
- The separate ordered-compilation probe returned an invalid support count and was rejected, not retried or used as a seed. Both arms used the same verified saved seed and a fresh shared audit.
- Latest full offline checks before live: **1,266 passed, 23 skipped**. Focused typed suite after adding explicit round reporting: **29 passed**.
- Frozen-source analysis and complete-result replay passed with **zero new provider calls**. Verification covers source/image/program hashes, constructed transactions, schedule counters, actual failed-confirmation parent selection, label/media isolation, dependency acknowledgments, budgets and final-stage isolation.

No final result triggered another repair, candidate replacement or budget increase. No commit or push was performed for this rerun.

## Reproduction

Artifacts: `logs/exps/261008-typed-evidence-15-round-v1`. The manifest pins the same original case/seed plus the fifteen-round schedule, source snapshots, thresholds and budgets. Frozen leaves retain exact programs, typed/expanded edits, audits, discovery/backward feedback, confirmation reports and final observations.

Recompute analysis and replay completed work without contacting a provider:

```bash
PYTHONPATH=. .venv/bin/python logs/exps/261008-typed-evidence-15-round-v1/replay_frozen_analysis.py
```

`component_analysis.json`, `analysis.md`, `usage_summary.json`, `protocol_verification.json` and `results.json` contain the detailed distributions, costs, failure reasons and executed rounds. The earlier two-round artifacts remain unchanged.
