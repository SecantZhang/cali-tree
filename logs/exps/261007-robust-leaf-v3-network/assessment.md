# Supplementary robust leaf analysis

Six previously observed cases, independently fitted in four arms. Repetitions are measurements within cases, not independent cases. No held-out generalization claim.

Status: completed

| Arm | Seed → selected agreement | Seed → selected robust cases | Selected coverage | Selected label consistency | Selected conditional programs |
|---|---:|---:|---:|---:|---:|
| flat-greedy | 43.3% → 46.7% | 3 → 3 / 6 | 100.0% | 96.7% | 0 / 6 |
| flat-pareto | 36.7% → 66.7% | 2 → 4 / 6 | 100.0% | 100.0% | 0 / 6 |
| tree-greedy | 43.3% → 80.0% | 2 → 4 / 6 | 96.7% | 96.7% | 0 / 6 |
| tree-pareto | 46.7% → 66.7% | 3 → 4 / 6 | 100.0% | 100.0% | 0 / 6 |

| Instruction | Reference | Arm | Seed → selected agreement | Final status | Failure reasons |
|---|---|---|---:|---|---|
| transform the black DVD into a white DVD | no | flat-greedy | 0% → 0% | stable_but_mismatched | target_mismatch |
| transform the black DVD into a white DVD | no | flat-pareto | 0% → 100% | locally_robust | none |
| transform the black DVD into a white DVD | no | tree-greedy | 0% → 100% | locally_robust | none |
| transform the black DVD into a white DVD | no | tree-pareto | 0% → 100% | locally_robust | none |
| Make her close her jacket fully | yes | flat-greedy | 0% → 0% | stable_but_mismatched | target_mismatch |
| Make her close her jacket fully | yes | flat-pareto | 0% → 0% | stable_but_mismatched | target_mismatch |
| Make her close her jacket fully | yes | tree-greedy | 0% → 0% | stable_but_mismatched | target_mismatch |
| Make her close her jacket fully | yes | tree-pareto | 0% → 0% | stable_but_mismatched | target_mismatch |
| Change the image into pencil drawing | partial | flat-greedy | 80% → 100% | locally_robust | none |
| Change the image into pencil drawing | partial | flat-pareto | 40% → 100% | locally_robust | none |
| Change the image into pencil drawing | partial | tree-greedy | 60% → 100% | locally_robust | none |
| Change the image into pencil drawing | partial | tree-pareto | 80% → 100% | locally_robust | none |
| Give the woman a helmet | yes | flat-greedy | 100% → 100% | locally_robust | none |
| Give the woman a helmet | yes | flat-pareto | 100% → 100% | locally_robust | none |
| Give the woman a helmet | yes | tree-greedy | 100% → 80% | unresolved | unresolved, confidence |
| Give the woman a helmet | yes | tree-pareto | 100% → 100% | locally_robust | none |
| Move the mug to the right of the headphones | partial | flat-greedy | 0% → 0% | stable_but_mismatched | target_mismatch |
| Move the mug to the right of the headphones | partial | flat-pareto | 0% → 0% | stable_but_mismatched | target_mismatch |
| Move the mug to the right of the headphones | partial | tree-greedy | 0% → 100% | locally_robust | none |
| Move the mug to the right of the headphones | partial | tree-pareto | 0% → 0% | stable_but_mismatched | target_mismatch |
| Move the book behind the flower | no | flat-greedy | 80% → 80% | locally_robust | none |
| Move the book behind the flower | no | flat-pareto | 80% → 100% | locally_robust | none |
| Move the book behind the flower | no | tree-greedy | 100% → 100% | locally_robust | none |
| Move the book behind the flower | no | tree-pareto | 100% → 100% | locally_robust | none |

Agreement uses fresh five-draw final executions. Repeats are not independent cases. Confidence is generated self-report, not calibrated correctness.
Unvisited branches remain untested; programs without conditional nodes do not experimentally distinguish flat versus tree routing.
No final verification outcome was used to retune a program. Semantic audits are evidence, not proof of atomic correctness.

Combined calls including prior failed attempt: 791
Combined completion tokens / conservative reservations: 80310
Input tokens in this run: 1517184
Returned model identities: ["gpt-6-luna"]
Job outcomes: {"completed": 781, "transport_error": 7}
