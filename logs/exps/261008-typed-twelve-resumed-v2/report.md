# Twelve-case typed evidence optimizer comparison

Twelve previously observed local fitting cases. Four per reference class. No cross-case feedback, atomic correctness or held-out generalization claim.

Status: completed

| Method | Mean seed → selected matches / 5 | Selected usable / 5 | Locally robust cases |
|---|---:|---:|---:|
| criterion-only | 1.42 → 2.58 | 3.92 | 4/12 |
| nested-required | 1.33 → 2.00 | 3.25 | 0/12 |

Missing/unattempted/invalid draws are nonmatches in the full twelve-case denominator. Usable means resolved, including wrong labels. Repeats are within cases, not independent cases.

| Case / reference | Method | Seed → selected matches / 5 | Usable / 5 | Rounds completed | Nested checks | Status / reasons |
|---|---|---:|---:|---:|---|---|
| transform the black DVD into a white DVD / no | criterion-only | 0 → 0 | 0 | unavailable | none | unresolved; ValueError: Evidence questions must be distinct from each other and fulfillment |
| transform the black DVD into a white DVD / no | nested-required | 0 → 0 | 0 | unavailable | none | unresolved; ValueError: Evidence questions must be distinct from each other and fulfillment |
| Make her close her jacket fully / yes | criterion-only | 0 → 0 | 5 | 7 | none | unconfirmed; target_mismatch, confirmation_missing_or_unqualified |
| Make her close her jacket fully / yes | nested-required | 0 → 0 | 5 | 15 | none | structural_failure; target_mismatch, confirmation_missing_or_unqualified, no_eligible_executed_nested_check |
| Change the image into pencil drawing / partial | criterion-only | 0 → 5 | 5 | 2 | none | locally_robust; none |
| Change the image into pencil drawing / partial | nested-required | 0 → 1 | 4 | 10 | s3 | unconfirmed; unresolved, target_mismatch, requirement_instability, node_instability:s3, node_instability:fulfillment, confidence, confirmation_missing_or_unqualified |
| Give the woman a helmet / yes | criterion-only | 5 → 4 | 4 | 4 | none | unresolved; unresolved, confidence |
| Give the woman a helmet / yes | nested-required | 5 → 4 | 4 | 15 | none | structural_failure; semantic_audit, unresolved, confidence, confirmation_missing_or_unqualified, no_eligible_executed_nested_check |
| Change the background into a basketball court / yes | criterion-only | 5 → 4 | 5 | 6 | none | unconfirmed; confidence, confirmation_missing_or_unqualified |
| Change the background into a basketball court / yes | nested-required | 3 → 0 | 2 | 12 | s3 | unconfirmed; unresolved, target_mismatch, requirement_instability, node_instability:s1, node_instability:s3, insufficient_activation:fulfillment, confidence, confirmation_missing_or_unqualified |
| Move the mug to the right of the headphones / partial | criterion-only | 0 → 0 | 5 | 12 | none | unconfirmed; target_mismatch, confirmation_missing_or_unqualified |
| Move the mug to the right of the headphones / partial | nested-required | 0 → 0 | 0 | 12 | s3 | unconfirmed; unresolved, target_mismatch, requirement_instability, node_instability:s3, confidence, confirmation_missing_or_unqualified |
| Move the book behind the flower / no | criterion-only | 5 → 3 | 3 | 6 | none | unconfirmed; unresolved, target_mismatch, requirement_instability, node_instability:fulfillment, confirmation_missing_or_unqualified |
| Move the book behind the flower / no | nested-required | 5 → 5 | 5 | 15 | none | structural_failure; confirmation_missing_or_unqualified, no_eligible_executed_nested_check |
| Stuffing the paper into the cup / no | criterion-only | 2 → 5 | 5 | 2 | none | locally_robust; none |
| Stuffing the paper into the cup / no | nested-required | 3 → 4 | 5 | 15 | none | structural_failure; semantic_audit, node_instability:s2, confidence, confirmation_missing_or_unqualified, no_eligible_executed_nested_check |
| Make this look like a comic book photo / no | criterion-only | 0 → 5 | 5 | 1 | none | locally_robust; none |
| Make this look like a comic book photo / no | nested-required | 0 → 5 | 5 | 14 | s3 | unconfirmed; confirmation_missing_or_unqualified |
| Turn the image into a drawing made from chalk / partial | criterion-only | 0 → 5 | 5 | 1 | none | locally_robust; none |
| Turn the image into a drawing made from chalk / partial | nested-required | 0 → 5 | 5 | 15 | s3 | unconfirmed; confirmation_missing_or_unqualified |
| Put a frog in the toilet / partial | criterion-only | 0 → 0 | 5 | 15 | none | unconfirmed; target_mismatch, confirmation_missing_or_unqualified |
| Put a frog in the toilet / partial | nested-required | 0 → 0 | 4 | 15 | none | structural_failure; semantic_audit, unresolved, target_mismatch, confidence, confirmation_missing_or_unqualified, no_eligible_executed_nested_check |
| the small gray rubber cylinder becomes brown / yes | criterion-only | 0 → 0 | 0 | unavailable | none | unresolved; GraphValidationError: s2 may reference only earlier support indices |
| the small gray rubber cylinder becomes brown / yes | nested-required | 0 → 0 | 0 | unavailable | none | unresolved; GraphValidationError: s2 may reference only earlier support indices |

Confirmation success is provisional; final verification remains frozen and independent. Negative support is usable evidence. Confidence is self-report; consistency is not atomic correctness.

Returned models: ["gpt-6-luna"]
Usage: {"limits": {"max_calls": 3600, "max_completion_tokens": 4608000, "reserve_calls": 960, "reserve_tokens": 983040, "identity": {"model": "gpt-6-luna", "provider": "openai", "temperature": 0, "reasoning_effort": "none"}, "scope_limits": {"search": 109, "final": 40}}, "calls": 2364, "completion_tokens_or_reserved": 420200, "input_tokens": 7288931, "consecutive_errors": 0, "stopped": null, "authorized_resumes": [{"source": "/Users/zzhang/Documents/Projects/Adobe/calitree-mlsys/logs/exps/261008-typed-twelve-v2", "stop": "Three consecutive transport failures", "calls": 684, "consecutive_errors": 0, "completion_tokens_or_reserved": 133385}, {"source": "/Users/zzhang/Documents/Projects/Adobe/calitree-mlsys/logs/exps/261008-typed-twelve-resumed-v1", "stop": "Three consecutive transport failures", "calls": 1413, "consecutive_errors": 0, "completion_tokens_or_reserved": 293366}], "final_calls": 607, "final_tokens": 46675}
Error: none
