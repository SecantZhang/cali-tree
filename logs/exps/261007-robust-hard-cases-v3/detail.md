# Harder-case confidence and topology

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
