# Completed five-repeat experiment

Same 50 cases and frozen 112 conditions; original two draws plus three fresh draws. Unresolved/missing results remain in the denominator and do not count as matching resolved predictions.

| Measure | At least 60% (3/5) | At least 80% (4/5) | 100% (5/5) |
|---|---|---|---|
| final_prediction | 39/50 (78.0%) | 36/50 (72.0%) | 23/50 (46.0%) |
| exact_condition_vector | 35/50 (70.0%) | 30/50 (60.0%) | 17/50 (34.0%) |
| every_condition_individually | 40/50 (80.0%) | 32/50 (64.0%) | 17/50 (34.0%) |
| individual_conditions | 102/112 (91.1%) | 89/112 (79.5%) | 65/112 (58.0%) |

Final-prediction exact-frequency counts: {"4": 13, "5": 23, "0": 4, "2": 6, "3": 3, "1": 1}.

Coverage: {"planned_case_draws": 250, "resolved_case_draws": 199, "model_unknown_case_draws": 40, "incomplete_case_draws": 11, "known_observations": 504, "unknown_observations": 41, "planned_observations": 560, "all_five_unresolved_cases": ["J03", "J17", "N04", "N57"]}.

New calls: 336; outcomes: {"completed": 327, "transport_error": 8, "interrupted_or_pending": 1}.

Successful new usage: 417,789 input and 46,949 output tokens. Failed calls retain full token reservations; usage is not an invoice.

High repeatability does not establish correctness. Previously found scope/interpretation errors can remain stable. No human labels were used to define agreement, and no raw-prompt comparison arm was run.

[All cases and conditions](case_table.md); [audit](audit.json); [observations](observations.csv).
