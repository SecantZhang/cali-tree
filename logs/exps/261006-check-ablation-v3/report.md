# Combined versus separated visual checks

Previously observed cases; label-blind shared rule compilation. Execution-format ablation, no optimizer search.

Status: completed

| Arm | Cases | Agreement | Coverage | Pairwise inconsistency | Resolved-pair disagreement | Atomic inconsistency | Fully matching | Fully consistent | Calls |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| combined | 12 | 6.7% | 23.3% | 78.3% | 0.0% | 13.3% | 0 | 2 | 15 |
| separated | 12 | 6.7% | 23.3% | 84.2% | 30.0% | 20.0% | 0 | 1 | 45 |

| Instruction | Target | Preparation | Combined agreement / inconsistency | Separated agreement / inconsistency |
|---|---|---|---|---|
| transform the black DVD into a white DVD | no | audit_rejected | 0.0% / 100.0% | 0.0% / 100.0% |
| Make her close her jacket fully | yes | audit_rejected | 0.0% / 100.0% | 0.0% / 100.0% |
| Change the image into pencil drawing | partial | ready | 0.0% / 0.0% | 20.0% / 40.0% |
| Give the woman a helmet | yes | audit_rejected | 0.0% / 100.0% | 0.0% / 100.0% |
| Change the background into a basketball court | yes | ready | 80.0% / 40.0% | 60.0% / 70.0% |
| Move the mug to the right of the headphones | partial | audit_rejected | 0.0% / 100.0% | 0.0% / 100.0% |
| Move the book behind the flower | no | audit_rejected | 0.0% / 100.0% | 0.0% / 100.0% |
| Stuffing the paper into the cup | no | audit_rejected | 0.0% / 100.0% | 0.0% / 100.0% |
| Make this look like a comic book photo | no | audit_rejected | 0.0% / 100.0% | 0.0% / 100.0% |
| Turn the image into a drawing made from chalk | partial | ready | 0.0% / 0.0% | 0.0% / 0.0% |
| Put a frog in the toilet | partial | audit_rejected | 0.0% / 100.0% | 0.0% / 100.0% |
| the small gray rubber cylinder becomes brown | yes | audit_rejected | 0.0% / 100.0% | 0.0% / 100.0% |

Paired exact sign-flip diagnostic (case-level; separated minus combined): {"cases": 3, "mean_difference": 0.2333333333333333, "p_value": 0.5}

Unknown/failed predictions count as incorrect and as inconsistent with any paired draw. Resolved-only disagreement is diagnostic and omits missing observations.
Each case contributes equally; five draws do not create five independent cases. Atomic consistency is not correctness.
Combined returns all fact observations and outcome judgments in one image call. Separated executes each fact in an isolated image call, then applies the same decision criteria in a text-only fulfillment call.
Interpret any difference as an execution-format effect, including context isolation and extra calls, not a pure prompt-length effect. Criteria are identical; separate execution costs more.
Preparation failures remain unresolved in full-cohort metrics and are excluded from the paired execution-effect diagnostic.
No optimization or feedback uses these final results. Historical observation and small case count limit inference.

Error: none
