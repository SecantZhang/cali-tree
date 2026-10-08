# GEPA and TextGrad structural leaf comparison — 2026-10-06

GEPA produced the strongest local result in this pilot: **75.0% final agreement and 9/12 fully fitted leaves**, compared with **63.9% and 7/12** for custom search, and **61.1% and 5/12** for TextGrad. This supports trying GEPA for casewise optimization, but does not establish a general method ranking. The sample is small, previously observed, and transport failures were uneven.

## Results

Each method used the same twelve saved label-free seeds and images, with four cases per target class. Each selected program received three fresh final draws after freezing. Unresolved draws count as misses; repetitions are not additional cases. A fully fitted leaf requires an accepted semantic audit and three matching, resolved final draws.

| Method | Seed agreement | Selected agreement | Fully fitted | Resolved draws | Agreement on resolved draws | Search calls | Total calls |
|---|---:|---:|---:|---:|---:|---:|---:|
| custom | 52.8% | 63.9% | 7/12 | 36/36 | 63.9% | 120 | 204 |
| gepa | 50.0% | 75.0% | 9/12 | 36/36 | 75.0% | 163 | 247 |
| textgrad | 47.2% | 61.1% | 5/12 | 34/36 | 64.7% | 183 | 267 |

Seed agreement differs because each arm received separate fresh draws of the identical seed program. Every arm used 84 final checker calls; the custom comparator is a fresh rerun, not the earlier pilot result. Conditional agreement excludes unresolved draws and is diagnostic, not a replacement for the full-coverage metric.

| Method | Label repeat disagreement | Atomic unstable or unknown rate | Measured input tokens | Measured completion tokens | Charged completion tokens | Transport failures |
|---|---:|---:|---:|---:|---:|---:|
| custom | 2.8% | 8.3% | 300,543 | 14,848 | 18,944 | 4 |
| gepa | 0.0% | 0.0% | 393,499 | 21,725 | 24,797 | 3 |
| textgrad | 11.1% | 33.3% | 503,600 | 29,868 | 39,084 | 9 |

Label disagreement is the mean fraction of draws differing from the most common label, including unresolved labels. Atomic instability is reported separately and does not establish atomic correctness. Failed calls retain their full output-token reservation; dollar cost is not estimated.

## Per-case final behavior

| Case | Target | Custom | GEPA | TextGrad |
|---|---|---|---|---|
| 1. transform the black DVD into a white DVD | no | 3/3, locally_fitted | 3/3, locally_fitted | 2/3, unresolved |
| 2. Make her close her jacket fully | yes | 0/3, unmatched | 0/3, unmatched | 0/3, unmatched |
| 3. Change the image into pencil drawing | partial | 3/3, locally_fitted | 3/3, locally_fitted | 2/3, unresolved |
| 4. Give the woman a helmet | yes | 3/3, locally_fitted | 3/3, locally_fitted | 3/3, locally_fitted |
| 5. Change the background into a basketball court | yes | 2/3, unstable | 3/3, locally_fitted | 2/3, unstable |
| 6. Move the mug to the right of the headphones | partial | 0/3, unmatched | 0/3, unmatched | 0/3, unmatched |
| 7. Move the book behind the flower | no | 3/3, locally_fitted | 3/3, locally_fitted | 3/3, locally_fitted |
| 8. Stuffing the paper into the cup | no | 3/3, locally_fitted | 3/3, locally_fitted | 3/3, locally_fitted |
| 9. Make this look like a comic book photo | no | 3/3, locally_fitted | 3/3, locally_fitted | 3/3, locally_fitted |
| 10. Turn the image into a drawing made from chalk | partial | 0/3, unmatched | 3/3, locally_fitted | 0/3, unmatched |
| 11. Put a frog in the toilet | partial | 0/3, unmatched | 0/3, unmatched | 1/3, unstable |
| 12. the small gray rubber cylinder becomes brown | yes | 3/3, locally_fitted | 3/3, locally_fitted | 3/3, locally_fitted |

GEPA’s additional fully fitted cases relative to custom were the basketball background and chalk drawing. All three methods failed to fit the jacket and mug cases; none fit the frog case reliably. TextGrad had two unresolved selected draws caused by transport errors (DVD and pencil drawing). Its other final transport failures affected seed draws. All failures remain recorded and were not retried.

The [per-case CSV](../../logs/exps/261006-optimizer-comparison-v1/per_case.csv) contains each arm’s seed/selected agreement, coverage, label stability, atomic stability, executed checks, token charges, search stop reason, and final status. Budget-limited search is separate from final fitting status: GEPA’s DVD candidate exhausted search but passed all fresh final draws.

## What changed structurally

Custom selected three changed programs; GEPA and TextGrad selected five each. **None of the selected programs changed the outcome count, check count, or dependency structure.** Improvements in this pilot therefore came from criterion/binding revisions, not demonstrated gains from adding rules. The actual library integration tests separately verify that both adapters can add a supporting check, link it as a dependency, and execute it.

## Controlled protocol and limits

- GPT-6 Luna for all model roles, temperature zero, reasoning `none`; every successful response reported `gpt-6-luna`. No substitutions.
- Native GEPA 0.1.4: Pareto selection, strict improvement, no merging, up to six proposals. The train and validation entries are the same local case; they are not holdout evidence.
- Native TextGrad 0.1.8: one trainable serialized graph, `StringBasedFunction.backward`, then `TGD.step`, up to six updates. Backpropagation is graph-level rather than separately through checker nodes.
- Existing custom typed-transaction search: two rounds, beam width two, two transactions per parent.
- Shared four-check cap, requirement preservation, label-blind semantic audit, one screening draw, three fresh confirmations for matching candidates, seed retention, and three additional final draws.
- Each case-method had a 26-call search allowance plus 24 reserved final calls. Overall ceilings were 1,800 calls and 2,304,000 completion tokens. Actual use: **718 calls and 82,825 charged completion tokens**, including 16 transport failures.
- Each durable slot made one HTTP attempt. Failed/interrupted work cannot be resampled on resume. The three-consecutive-transport-error stop threshold was never reached.
- Case order and images were frozen; method order rotated. All three methods’ candidates were frozen before final evaluation for each case. Cases and observation caches were independent.

These are constrained integrations of the official libraries. GEPA/TextGrad replace a whole JSON graph; custom applies typed transactions. Equal call allowances do not equalize proposal count or token cost, and this pilot does not isolate search strategy from the proposal interface. Semantic audits are evidence, not proof. Matching these locally supplied labels establishes neither generalization nor correct atomic reasoning.

## Verification and reproduction

- Before live execution: 1,106 offline unit tests passed, 23 skipped; the original ten integration tests exercised the actual pinned libraries with fake model replies.
- All 36 selected leaves reloaded and replayed exactly from their saved final observation slots without model calls. Every final metric was recomputed, image/source hashes verified, per-case budgets checked, and label isolation checked for compiler/checker/audit payloads.
- Completed-run resume under the frozen implementation produced identical results, unchanged budget accounting, and zero provider calls.
- Final verification after hardening: **1,112 passed, 23 skipped** in the full offline unit suite; **54 passed** in the focused runtime/adapter suite (16 adapter tests plus 38 runtime tests).
- After the pilot, an offline malformed-genome test exposed missing nested type validation. The adapter parser was hardened; all 106 saved candidate records pass the stricter validation. No frozen programs, outcomes, or model slots were changed.

The post-run parser hardening changes the implementation hash, so live resume from the current checkout intentionally rejects this old manifest. The exact pre-hardening implementation remains in `source_snapshot/`; read-only reporting and leaf replay work in the current checkout. New experiments must use a new output directory.

```sh
.venv/bin/python -m run.calitree_optimizer_comparison --report --output-dir logs/exps/261006-optimizer-comparison-v1
.venv/bin/python -m logs.exps.261006-optimizer-comparison-v1.verify_run
```

Artifacts: [manifest](../../logs/exps/261006-optimizer-comparison-v1/manifest.json), [verified audit](../../logs/exps/261006-optimizer-comparison-v1/audit.json), [results](../../logs/exps/261006-optimizer-comparison-v1/results.json), [saved leaves](../../logs/exps/261006-optimizer-comparison-v1/leaves.json), [per-case CSV](../../logs/exps/261006-optimizer-comparison-v1/per_case.csv). Exact programs, candidate histories, audits, model requests/responses, native textual gradients/reflections, and durable jobs remain in the run directory. See the [adapter guide](../calitree_optimizer_comparison.md) for usage.
