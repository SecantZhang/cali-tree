# Proposer model comparison: saved-data analysis

Three previously observed local fitting cases: jacket, paper/cup and frog. Only proposer model/configuration varies; no generalization claim.

**Both arms used Luna for all visual checks, feedback, discovery and semantic review. Only Sol-arm proposal requests used Sol 6.1 with medium reasoning.**

| Proposer | Transactions proposed | Semantically approved | Seed → selected reference matches / 15 | Selected resolved / 15 | Robust cases / 3 |
|---|---:|---:|---:|---:|---:|
| luna-proposer | 37 | 1 | 4 → 0 | 8 | 0 |
| sol-proposer | 11 | 9 | 5 → 1 | 6 | 0 |

A transaction approval is the label-blind reviewer’s opinion about meaning preservation, not proof of correctness. Reference matches count five fresh draws per case; repeats are not additional cases. Resolved means a usable answer, whether correct or wrong. Mandatory insertion remains an experimental restriction. A valid existing-check repair can remain an intermediate without qualifying.

| Case | Proposer | Seed → selected matches / 5 | Selected resolved / 5 | Lowest confidence / missing values | Checks | Result |
|---|---|---:|---:|---|---:|---|
| Make her close her jacket fully | luna-proposer | 0 → 0 | 4 | 0.91 / 1 | 3 | structural_failure |
| Make her close her jacket fully | sol-proposer | 0 → 0 | 0 | 0.94 / 0 | 4 | structural_failure |
| Stuffing the paper into the cup | luna-proposer | 4 → 0 | 0 | 0.96 / 0 | 4 | unconfirmed |
| Stuffing the paper into the cup | sol-proposer | 5 → 1 | 1 | 0.88 / 0 | 4 | unconfirmed |
| Put a frog in the toilet | luna-proposer | 0 → 0 | 4 | 0.99 / 1 | 3 | structural_failure |
| Put a frog in the toilet | sol-proposer | 0 → 0 | 5 | 0.99 / 0 | 4 | unconfirmed |

Self-reported confidence is not calibrated probability. Missing confidence fails the frozen gate. `structural_failure` here also covers an added check that was not reached in at least three final draws; it does not necessarily mean an invalid graph.

## Measured cost

{
  "gpt-6-luna": {
    "calls": 702,
    "reported_input_tokens": 2746696,
    "reported_completion_tokens": 102350,
    "reserved_failed_completion_tokens": 25600,
    "estimated_uncached_reported_usage_usd": 0.3258
  },
  "gpt-6.1-sol": {
    "calls": 37,
    "reported_input_tokens": 580590,
    "reported_completion_tokens": 20579,
    "reserved_failed_completion_tokens": 4096,
    "estimated_uncached_reported_usage_usd": 1.367
  }
}

These are uncached list-price estimates on reported tokens, excluding unknown failed-request input/output usage and cache discounts. All completion charges and reservations remain in budget.json. Returned identities: ["gpt-6-luna", "gpt-6.1-sol"].

## Per-case diagnostics

### Make her close her jacket fully / luna-proposer

Proposals: {"structural_or_transport_rejection": 2, "semantic_rejected": 8}.
Search rounds: {"round_batches": [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1], "rounds_started": 15, "rounds_completed": 15, "stop_on_confirmation": true, "repair_failed_candidate": true}. Stop: round_limit.
Final rejection reasons: ["unresolved", "target_mismatch", "confidence", "confirmation_missing_or_unqualified", "no_eligible_executed_nested_check"].
Direct final-call failures: {"CallFailure": 1}.
| Check | Question | Evidence dependencies | Final states |
|---|---|---|---|
| s1 | Is the woman's jacket visibly closed more than in the input image, with its front panels brought together at least in part? | [] | {"fail": 4, "unknown": 1} |
| s2 | Is the woman's jacket fully closed, with no visible opening remaining along its closure? | ['s1'] | {"fail": 4} |
| fulfillment | Is the woman's jacket fully closed? | ['s1', 's2'] | {"absent": 4} |

### Make her close her jacket fully / sol-proposer

Proposals: {"semantic_rejected": 1, "semantic_accepted": 2}.
Search rounds: {"round_batches": [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1], "rounds_started": 15, "rounds_completed": 15, "stop_on_confirmation": true, "repair_failed_candidate": true}. Stop: round_limit.
Final rejection reasons: ["unresolved", "target_mismatch", "requirement_instability", "node_instability:s1", "confirmation_missing_or_unqualified", "no_eligible_executed_nested_check"].
Direct final-call failures: {}.
| Check | Question | Evidence dependencies | Final states |
|---|---|---|---|
| s1 | Does comparison of the same woman's jacket front closure in the source and edited images establish progress toward closing it? | [] | {"unknown": 5} |
| s2 | Does direct inspection of the edited jacket establish that its front closure is fully closed? | ['s1'] | {} |
| s3_panel_attachment | Does the edited jacket's projecting or hanging panel provide identifiable evidence of an actual opening between its front closure edges, rather than merely a fold, overlap, or obscured view? | ['s1', 's2'] | {} |
| fulfillment | Is the woman's jacket fully closed? | ['s1', 's2', 's3_panel_attachment'] | {} |

### Stuffing the paper into the cup / luna-proposer

Proposals: {"semantic_rejected": 6, "structural_or_transport_rejection": 8, "semantic_accepted": 1}.
Search rounds: {"round_batches": [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1], "rounds_started": 15, "rounds_completed": 15, "stop_on_confirmation": true, "repair_failed_candidate": true}. Stop: round_limit.
Final rejection reasons: ["unresolved", "target_mismatch", "requirement_instability", "node_instability:s2", "node_instability:s3", "confirmation_missing_or_unqualified"].
Direct final-call failures: {}.
| Check | Question | Evidence dependencies | Final states |
|---|---|---|---|
| s1 | Is the paper visibly inside the cup, with evidence it has been stuffed into it rather than merely resting nearby or on the rim? | [] | {"fail": 5} |
| s2 | Does the image provide enough evidence to determine whether the paper has been stuffed into the cup? | ['s1'] | {"pass": 2, "fail": 3} |
| s3 | Comparing source and edited images, is there clear visible progress toward placing the source paper into the source cup, short of the paper being fully stuffed inside? | ['s1', 's2'] | {"unknown": 5} |
| fulfillment | Does the image show the paper stuffed inside the cup? | ['s1', 's2', 's3'] | {} |

### Stuffing the paper into the cup / sol-proposer

Proposals: {"semantic_accepted": 6, "semantic_rejected": 1}.
Search rounds: {"round_batches": [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1], "rounds_started": 7, "rounds_completed": 6, "stop_on_confirmation": true, "repair_failed_candidate": true}. Stop: budget_exhausted: Case sol-proposer/aurora-task-9a1ea55edac097679512::mgie search allowance exhausted.
Final rejection reasons: ["unresolved", "target_mismatch", "requirement_instability", "node_instability:s2", "insufficient_activation:fulfillment", "confirmation_missing_or_unqualified"].
Direct final-call failures: {}.
| Check | Question | Evidence dependencies | Final states |
|---|---|---|---|
| s1 | What paper and receiving objects are visibly present in the source and edited images, and does direct feature comparison establish whether an edited receiving object is a cup? | [] | {"pass": 5} |
| s4_opening_entry | Using s1's inventory, can direct inspection produce a grounded map of paper boundaries, receiver overlap, and hidden contact regions, separately identifying what that map establishes or leaves unresolved about cup entry? | ['s1'] | {"pass": 5} |
| s2 | Given the inventory and nested boundary map, does independent inspection establish completed stuffing, affirmative incompleteness, or unresolved completion, and what requested progress is actually established? | ['s1', 's4_opening_entry'] | {"unknown": 4, "fail": 1} |
| fulfillment | Does the image show the paper stuffed inside the cup? | ['s1', 's4_opening_entry', 's2'] | {"absent": 1} |

### Put a frog in the toilet / luna-proposer

Proposals: {"structural_or_transport_rejection": 2, "semantic_rejected": 10}.
Search rounds: {"round_batches": [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1], "rounds_started": 15, "rounds_completed": 15, "stop_on_confirmation": true, "repair_failed_candidate": true}. Stop: round_limit.
Final rejection reasons: ["semantic_audit", "unresolved", "target_mismatch", "confidence", "confirmation_missing_or_unqualified", "no_eligible_executed_nested_check"].
Direct final-call failures: {"CallFailure": 1}.
| Check | Question | Evidence dependencies | Final states |
|---|---|---|---|
| s1 | Is a frog visibly present inside the toilet bowl? | [] | {"pass": 5} |
| s2 | Does the image provide sufficient evidence to determine whether the requested frog-in-toilet edit was made? | ['s1'] | {"unknown": 1, "pass": 4} |
| fulfillment | Is a frog visibly placed inside the toilet bowl? | ['s1', 's2'] | {"complete": 4} |

### Put a frog in the toilet / sol-proposer

Proposals: {"semantic_accepted": 1}.
Search rounds: {"round_batches": [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1], "rounds_started": 15, "rounds_completed": 15, "stop_on_confirmation": true, "repair_failed_candidate": true}. Stop: round_limit.
Final rejection reasons: ["target_mismatch", "confirmation_missing_or_unqualified"].
Direct final-call failures: {}.
| Check | Question | Evidence dependencies | Final states |
|---|---|---|---|
| s1 | Is a recognizable frog visible in the toilet bowl opening or directly at its rim? | [] | {"pass": 5} |
| s2 | Does comparison with the source show an added frog placement that constitutes progress toward putting a frog inside this toilet bowl? | ['s1'] | {"pass": 5} |
| s3 | Does the candidate frog occupy the toilet bowl interior, rather than merely overlapping the opening or resting on an exterior toilet surface? | ['s1', 's2'] | {"pass": 5} |
| fulfillment | Is a frog visibly placed inside the toilet bowl? | ['s1', 's2', 's3'] | {"complete": 5} |
