# Supplementary robust leaf analysis

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
