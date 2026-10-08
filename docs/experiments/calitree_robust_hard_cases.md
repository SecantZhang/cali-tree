# Current CaliTree optimizer on harder cases

The live stress test completed on 2026-10-07 using the unchanged robust v3 optimizer and GPT-6 Luna. Some criterion repairs improved local reference-label agreement, but **all 38 candidate records still contained one broad fulfillment check**. None contained a supporting check or conditional branch. Harder inputs did not automatically produce decomposition, so this experiment does not test broad versus decomposed execution.

## Frozen selection and protocol

Selected the three cases with the lowest historical mean seed agreement below 0.8, excluding cases in the previous six-case robust pilot. Selection used saved custom/GEPA/TextGrad baseline results from the original twelve-case manifest, before new API calls. Case/image hashes, historical source hashes, source-pixel groups, code and dependencies are pinned in the new manifest.

| Case | Reference | Prior matching seed draws | Prior resolved draws |
|---|---|---:|---:|
| Background into a basketball court | yes | 7/9 | 9/9 |
| Image into a chalk drawing | partial | 3/9 | 9/9 |
| Frog in the toilet | partial | 0/9 | 7/9 |

These are previously observed local fitting cases, with distinct source groups. This subset intentionally emphasizes historical judge errors; it is not balanced (one yes, two partial, no no cases) or historically untouched. "Harder" refers to difficulty for saved baseline judges, not intrinsic difficulty or difficulty relative to every original pilot case. Historical draws across methods reused the cases/seeds and are not independent cases. Historical failed calls remain nonmatches in the frozen selection score; a separate breakdown distinguishes them from semantic mismatch.

Compared flat-greedy, flat-Pareto, tree-greedy and tree-Pareto with the original compiler, prompts, native TextGrad feedback, structural proposer, audit, runtime, search and acceptance policy. Only the common runner's reporting was generalized to the actual case count and scope; a separate entry point froze selection and the smaller budget. Exact equivalence is recorded in `optimizer_equivalence.json`.

Shared label-free compilation and audit, independent arm measurements, two rounds/six proposal opportunities, four-check/depth-four limits, five confirmation draws and five fresh final draws for each seed and selection. All 12 selections were frozen before final verification. Thresholds stayed fixed: at least 4/5 target agreement, 5/5 resolved coverage, consistency at least 0.8, sufficient activation and every queried confidence at least 0.8, with semantic-audit approval. Final outcomes never triggered repairs or candidate replacement.

## Interpretation

- The basketball-court candidate improved to 5/5 final matches for flat-greedy, flat-Pareto and tree-greedy. Tree-Pareto produced 1/5 final matches; its selected candidate had already failed confirmation (3/5 agreement, 4/5 coverage).
- The chalk candidate improved to 5/5 matches for tree-greedy. Flat-greedy and tree-Pareto each produced four matching draws and one failed transport call, so they correctly failed the full-coverage requirement. Flat-Pareto retained a consistently mismatched seed.
- No frog-case arm passed the robustness policy. Tree arms produced yes on every selected final draw, while the reference was partial. Both reported confidence 0.99 in every executed selected check. Flat methods also failed reference agreement, despite confidence 0.99. This demonstrates why confidence and repeat consistency do not establish reference correctness.
- The frog image visibly contains a frog inside the bowl plus extra frogs elsewhere. A label-blind audit rejected a proposed rule penalizing extra frogs as unsupported by the saved instruction/rubric. This is a possible reference/rubric conflict needing adjudication, not proof that the reference is wrong. The label and rubric were kept fixed. Independent visual inspection was for reporting only and was never fed into search.
- Proposed edits were 24 checker revisions and two binding repairs; four candidate audits rejected edits. There were no add/split/routing transactions. Selected artifacts still have one executable check and no supporting nodes.
- Flat-greedy's frog seed and selected program are identical despite 0/5 versus 2/5 final agreement. That difference comes from fresh observations, not an optimization change. Other unchanged-program pairs also vary. Aggregated seed/selected differences must not all be attributed to edits.

Tree-greedy passed the full policy on two of three cases; each flat method passed on one; tree-Pareto passed on none. The sample is too small and biased to rank methods generally. The tree arms' names do not establish any conditional-tree benefit. A subsequent broad/decomposed comparison needs explicit alternative decompositions and measured scoring fidelity; that was not added to this test of the current method.

## Usage, failures and verification

392 durable model calls: 272 shared preparation/search calls and 120 final checks, with 377 completed responses and 15 retained TLS transport failures (11 search, four final). The four final failures were one tree-greedy chalk **seed** draw, one tree-greedy frog **seed** draw, one flat-greedy chalk **selected** draw and one tree-Pareto chalk **selected** draw. No three consecutive transport failures occurred. Each durable slot had one HTTP attempt; failures were not retried or replaced.

Total measured input tokens: 771,885. Completion tokens plus conservative failed-call reservations: 49,178. These are token usage/accounting quantities, not dollar costs. Checker responses were capped at 1,024 tokens, other responses at 2,048. All returned model identities were `gpt-6-luna`; temperature 0, reasoning none, official OpenAI provider, no substitution.

| Arm | Search calls | Final calls | Input tokens | Completion tokens / conservative reservations |
|---|---:|---:|---:|---:|
| flat-greedy | 65 | 30 | 194,452 | 9,922 |
| flat-Pareto | 61 | 30 | 178,903 | 12,256 |
| tree-greedy | 69 | 30 | 195,382 | 13,150 |
| tree-Pareto | 71 | 30 | 196,984 | 12,945 |
| Shared compilation/audit | 6 | 0 | 6,164 | 905 |

The approved ceiling was 1,800 calls and 2,304,000 completion tokens, reserving 480 calls/491,520 tokens for final verification. The planned maximum was 1,794 calls. All per-scope limits were respected.

- Offline verification: 49 focused tests passed; full suite 1,191 passed and 23 skipped.
- Saved protocol audit passed: 392 jobs, 12 frozen selections, 120 final draws; label isolation, identities, output caps, budgets, artifact hashes and final-phase ordering verified.
- Temporary-copy replay with provider construction forbidden reproduced all 12 case-arm results and the exact ledger with zero additional calls.
- Earlier experiments and original staging were preserved. No commit or push.

## Reproduce from saved artifacts

Experiment directory: `logs/exps/261007-robust-hard-cases-v3`. It contains the frozen manifest, exact source snapshot, programs/leaves, observations, gradients, transactions/audits, frontiers, model histories, failures, usage, selection evidence and results. All commands below use saved data only:

```bash
PYTHONPATH=. .venv/bin/python logs/exps/261007-robust-hard-cases-v3/analyze.py
PYTHONPATH=. .venv/bin/python logs/exps/261007-robust-hard-cases-v3/detail.py
PYTHONPATH=. .venv/bin/python logs/exps/261007-robust-hard-cases-v3/verify.py
PYTHONPATH=. .venv/bin/python logs/exps/261007-robust-hard-cases-v3/replay.py
```

`run/calitree_robust_hard_cases.py --live --resume` reuses attempted slots under the exact frozen configuration. Completed-run replay above explicitly prohibits provider construction. Repetitions remain measurements within three cases; self-reported confidence is not calibrated, audit approval is evidence rather than proof, and local label agreement does not certify atomic reasoning or generalization.

## Saved result tables

### Aggregate final comparison

Three failure-selected, previously observed local fitting cases outside the prior six-case v3 pilot. Selected before new calls by lowest mean saved seed agreement across custom, GEPA and TextGrad. This intentionally difficult subset is not class-balanced or a held-out generalization evaluation. Repetitions measure behavior within cases, not independent cases.

Status: completed

| Arm | Seed → selected agreement | Seed → selected robust cases | Selected coverage | Selected label consistency | Selected conditional programs |
|---|---:|---:|---:|---:|---:|
| flat-greedy | 20.0% → 73.3% | 0 → 1 / 3 | 93.3% | 80.0% | 0 / 3 |
| flat-pareto | 13.3% → 40.0% | 0 → 1 / 3 | 100.0% | 93.3% | 0 / 3 |
| tree-greedy | 26.7% → 66.7% | 0 → 2 / 3 | 100.0% | 100.0% | 0 / 3 |
| tree-pareto | 13.3% → 33.3% | 0 → 0 / 3 | 93.3% | 86.7% | 0 / 3 |

| Instruction | Reference | Arm | Seed → selected agreement | Final status | Failure reasons |
|---|---|---|---:|---|---|
| Change the background into a basketball court | yes | flat-greedy | 60% → 100% | locally_robust | none |
| Change the background into a basketball court | yes | flat-pareto | 20% → 100% | locally_robust | none |
| Change the background into a basketball court | yes | tree-greedy | 60% → 100% | locally_robust | none |
| Change the background into a basketball court | yes | tree-pareto | 20% → 20% | unstable_and_mismatched | target_mismatch |
| Turn the image into a drawing made from chalk | partial | flat-greedy | 0% → 80% | unresolved | unresolved, confidence |
| Turn the image into a drawing made from chalk | partial | flat-pareto | 0% → 0% | stable_but_mismatched | target_mismatch |
| Turn the image into a drawing made from chalk | partial | tree-greedy | 0% → 100% | locally_robust | none |
| Turn the image into a drawing made from chalk | partial | tree-pareto | 20% → 80% | unresolved | unresolved, confidence |
| Put a frog in the toilet | partial | flat-greedy | 0% → 40% | unstable_and_mismatched | target_mismatch, requirement_instability, node_instability:n1 |
| Put a frog in the toilet | partial | flat-pareto | 20% → 20% | unstable_and_mismatched | target_mismatch |
| Put a frog in the toilet | partial | tree-greedy | 20% → 0% | stable_but_mismatched | target_mismatch |
| Put a frog in the toilet | partial | tree-pareto | 0% → 0% | stable_but_mismatched | target_mismatch |

Agreement uses fresh five-draw final executions. Repeats are not independent cases. Confidence is generated self-report, not calibrated correctness.
Unvisited branches remain untested; programs without conditional nodes do not experimentally distinguish flat versus tree routing.
No final verification outcome was used to retune a program. Semantic audits are evidence, not proof of atomic correctness.

Combined calls including prior failed attempt: 392
Combined completion tokens / conservative reservations: 49178
Input tokens in this run: 771885
Returned model identities: ["gpt-6-luna"]
Job outcomes: {"completed": 377, "transport_error": 15}

### Per-case confidence and topology

| Case | Arm | Seed → selected matching draws / 5 | Selected resolved / 5 | Lowest reported confidence | Selected label consistency | Stored checks | Changed program | Final status |
|---|---|---:|---:|---:|---:|---:|---|---|
| Change the background into a basketball court | flat-greedy | 3 → 5 | 5 | 0.99 | 1.00 | 1 | yes | locally_robust |
| Change the background into a basketball court | flat-pareto | 1 → 5 | 5 | 0.98 | 1.00 | 1 | yes | locally_robust |
| Change the background into a basketball court | tree-greedy | 3 → 5 | 5 | 0.99 | 1.00 | 1 | yes | locally_robust |
| Change the background into a basketball court | tree-pareto | 1 → 1 | 5 | 0.91 | 0.80 | 1 | yes | unstable_and_mismatched |
| Turn the image into a drawing made from chalk | flat-greedy | 0 → 4 | 4 | 0.94 | 0.80 | 1 | yes | unresolved |
| Turn the image into a drawing made from chalk | flat-pareto | 0 → 0 | 5 | 0.94 | 1.00 | 1 | no | stable_but_mismatched |
| Turn the image into a drawing made from chalk | tree-greedy | 0 → 5 | 5 | 0.94 | 1.00 | 1 | yes | locally_robust |
| Turn the image into a drawing made from chalk | tree-pareto | 1 → 4 | 4 | 0.91 | 0.80 | 1 | yes | unresolved |
| Put a frog in the toilet | flat-greedy | 0 → 2 | 5 | 0.99 | 0.60 | 1 | no | unstable_and_mismatched |
| Put a frog in the toilet | flat-pareto | 1 → 1 | 5 | 0.99 | 0.80 | 1 | no | unstable_and_mismatched |
| Put a frog in the toilet | tree-greedy | 1 → 0 | 5 | 0.99 | 1.00 | 1 | yes | stable_but_mismatched |
| Put a frog in the toilet | tree-pareto | 0 → 0 | 5 | 0.99 | 1.00 | 1 | no | stable_but_mismatched |

Candidate check-count histogram: {"1": 38}
Proposed operations: {"checker_revision": 24, "binding": 2}
Audit rejections: 4
Job outcomes: {"completed": 377, "transport_error": 15}

Confidence is reported by the model. Stable agreement does not certify the individual reasoning. If seed and selected programs are identical, any score difference comes from fresh observations, not an edit. Programs with one check cannot demonstrate the benefit of decomposition or conditional routing.
