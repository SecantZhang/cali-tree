# V4 uncertainty handling and adaptive proposer experiment

Twelve previously observed local fitting cases, four per class. Repeats are within-case measurements. No held-out generalization or atomic correctness claim.

Status: completed

Agreement means reference matches; coverage means a resolved answer, including wrong answers. Each case has five fresh final draws. Missing or unresolved draws count as nonmatches; repeated draws are not additional cases. Both arms use the corrected runtime and strict gates.

| Arm | Seed → selected matches | Selected resolved | Locally robust cases | Escalated cases |
|---|---:|---:|---:|---:|
| luna_only | 27 → 29 / 60 | 58 / 60 | 2 / 12 | 0 / 12 |
| luna_then_sol | 29 → 35 / 60 | 59 / 60 | 5 / 12 | 8 / 12 |

| Instruction / reference | Arm | Seed → selected matches / 5 | Resolved / 5 | Mean executed checks | Confidence gate | Status / failure reason |
|---|---|---:|---:|---:|---|---|
| transform the black DVD into a white DVD / no | luna_only | 0 → 0 | 5 | 3.0 | passed | stable_but_mismatched; target_mismatch, confirmation_missing_or_unqualified |
| transform the black DVD into a white DVD / no | luna_then_sol | 0 → 0 | 5 | 3.0 | passed | stable_but_mismatched; target_mismatch, confirmation_missing_or_unqualified |
| Make her close her jacket fully / yes | luna_only | 0 → 0 | 5 | 3.0 | passed | stable_but_mismatched; target_mismatch, confirmation_missing_or_unqualified |
| Make her close her jacket fully / yes | luna_then_sol | 0 → 0 | 5 | 3.0 | passed | stable_but_mismatched; target_mismatch, confirmation_missing_or_unqualified |
| Change the image into pencil drawing / partial | luna_only | 0 → 0 | 4 | 2.2 | failed/unavailable | unresolved; semantic_audit, unresolved, target_mismatch, insufficient_activation:s2, confidence, confirmation_missing_or_unqualified |
| Change the image into pencil drawing / partial | luna_then_sol | 0 → 5 | 5 | 3.0 | passed | locally_robust;  |
| Give the woman a helmet / yes | luna_only | 5 → 5 | 5 | 3.0 | passed | unresolved; semantic_audit, confirmation_missing_or_unqualified |
| Give the woman a helmet / yes | luna_then_sol | 5 → 4 | 4 | 3.0 | failed/unavailable | unresolved; semantic_audit, unresolved, confidence, confirmation_missing_or_unqualified |
| Change the background into a basketball court / yes | luna_only | 5 → 5 | 5 | 3.0 | passed | unresolved; semantic_audit, confirmation_missing_or_unqualified |
| Change the background into a basketball court / yes | luna_then_sol | 5 → 5 | 5 | 2.0 | passed | locally_robust;  |
| Move the mug to the right of the headphones / partial | luna_only | 0 → 0 | 5 | 3.0 | failed/unavailable | unresolved; semantic_audit, target_mismatch, confidence, confirmation_missing_or_unqualified |
| Move the mug to the right of the headphones / partial | luna_then_sol | 0 → 0 | 5 | 3.0 | passed | unresolved; semantic_audit, target_mismatch, confirmation_missing_or_unqualified |
| Move the book behind the flower / no | luna_only | 2 → 4 | 4 | 3.0 | passed | unresolved; unresolved |
| Move the book behind the flower / no | luna_then_sol | 4 → 2 | 5 | 3.0 | passed | unstable_and_mismatched; target_mismatch, requirement_instability, node_instability:s2, node_instability:fulfillment |
| Stuffing the paper into the cup / no | luna_only | 5 → 5 | 5 | 3.0 | passed | unresolved; semantic_audit, confirmation_missing_or_unqualified |
| Stuffing the paper into the cup / no | luna_then_sol | 5 → 4 | 5 | 3.0 | passed | unresolved; semantic_audit, confirmation_missing_or_unqualified |
| Make this look like a comic book photo / no | luna_only | 5 → 5 | 5 | 3.0 | passed | locally_robust;  |
| Make this look like a comic book photo / no | luna_then_sol | 5 → 5 | 5 | 3.0 | passed | locally_robust;  |
| Turn the image into a drawing made from chalk / partial | luna_only | 0 → 0 | 5 | 2.0 | passed | unresolved; semantic_audit, target_mismatch, confirmation_missing_or_unqualified |
| Turn the image into a drawing made from chalk / partial | luna_then_sol | 0 → 5 | 5 | 3.0 | passed | locally_robust;  |
| Put a frog in the toilet / partial | luna_only | 0 → 0 | 5 | 3.0 | passed | unresolved; semantic_audit, target_mismatch, confirmation_missing_or_unqualified |
| Put a frog in the toilet / partial | luna_then_sol | 0 → 0 | 5 | 3.0 | failed/unavailable | unresolved; semantic_audit, target_mismatch, confidence, confirmation_missing_or_unqualified |
| the small gray rubber cylinder becomes brown / yes | luna_only | 5 → 5 | 5 | 3.0 | passed | locally_robust;  |
| the small gray rubber cylinder becomes brown / yes | luna_then_sol | 5 → 5 | 5 | 3.0 | passed | locally_robust;  |

## Per-case execution details

Consistency is measured separately from reference agreement. An uncertain answer can repeat consistently yet fail the known-answer stability gate. Skipped checks remain untested. The observation counts below count checks across five runs, not independent cases.

### transform the black DVD into a white DVD — luna_only

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 0.00 | 0.00 |
| Resolved draws / 5 | 5.00 | 5.00 |
| Final-label consistency | 1.00 | 1.00 |
| Minimum requirement consistency | 1.00 | 1.00 |
| Mean executed checks | 3.00 | 3.00 |
| Mean charged completion tokens | 136.80 | 137.20 |

Seed labels: {"yes": 5}. Observation events: {"observed": 15}.
Confidence per check: {"s1": [0.99, 0.99, 0.98, 0.98, 0.99], "s2": [0.98, 0.98, 0.98, 0.98, 0.98], "fulfillment": [0.99, 0.98, 0.98, 0.98, 0.99]}.
Known-answer consistency per check: {"s1": 1.0, "s2": 1.0, "fulfillment": 1.0}.

Selected labels: {"yes": 5}. Observation events: {"observed": 15}.
Confidence per check: {"s1": [0.99, 0.99, 0.98, 0.98, 0.98], "s2": [0.98, 0.98, 0.98, 0.98, 0.98], "fulfillment": [0.98, 0.99, 0.98, 0.98, 0.98]}.
Known-answer consistency per check: {"s1": 1.0, "s2": 1.0, "fulfillment": 1.0}.

Search schedule: {"rounds_started": 15, "rounds_completed": 15, "max_rounds": 15}. Stop: round_limit.
Escalated: False. Usage: {"search": 96, "final": 30, "completion_tokens_or_reserved": 27320, "input_tokens": 530148}.

### transform the black DVD into a white DVD — luna_then_sol

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 0.00 | 0.00 |
| Resolved draws / 5 | 5.00 | 5.00 |
| Final-label consistency | 1.00 | 1.00 |
| Minimum requirement consistency | 1.00 | 1.00 |
| Mean executed checks | 3.00 | 3.00 |
| Mean charged completion tokens | 139.60 | 140.00 |

Seed labels: {"yes": 5}. Observation events: {"observed": 15}.
Confidence per check: {"s1": [0.99, 0.98, 0.99, 0.98, 0.98], "s2": [0.98, 0.98, 0.98, 0.98, 0.98], "fulfillment": [0.99, 0.98, 0.98, 0.98, 0.98]}.
Known-answer consistency per check: {"s1": 1.0, "s2": 1.0, "fulfillment": 1.0}.

Selected labels: {"yes": 5}. Observation events: {"observed": 15}.
Confidence per check: {"s1": [0.99, 0.99, 0.99, 0.99, 0.98], "s2": [0.98, 0.98, 0.98, 0.98, 0.98], "fulfillment": [0.99, 0.99, 0.99, 0.99, 0.98]}.
Known-answer consistency per check: {"s1": 1.0, "s2": 1.0, "fulfillment": 1.0}.

Search schedule: {"rounds_started": 15, "rounds_completed": 14, "max_rounds": 15}. Stop: budget_exhausted: Case luna_then_sol/aurora-task-49616ac011dcfc46a053::magic_reproduce_epoch=47-step=12999 search allowance exhausted.
Escalated: True. Usage: {"search": 109, "final": 30, "completion_tokens_or_reserved": 34364, "input_tokens": 540375}.

### Make her close her jacket fully — luna_only

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 0.00 | 0.00 |
| Resolved draws / 5 | 5.00 | 5.00 |
| Final-label consistency | 1.00 | 1.00 |
| Minimum requirement consistency | 1.00 | 1.00 |
| Mean executed checks | 3.00 | 3.00 |
| Mean charged completion tokens | 174.20 | 172.40 |

Seed labels: {"no": 5}. Observation events: {"observed": 15}.
Confidence per check: {"s1": [0.99, 0.99, 0.99, 0.99, 0.99], "s2": [0.96, 0.96, 0.98, 0.91, 0.96], "fulfillment": [0.97, 0.98, 0.99, 0.95, 0.97]}.
Known-answer consistency per check: {"s1": 1.0, "s2": 1.0, "fulfillment": 1.0}.

Selected labels: {"no": 5}. Observation events: {"observed": 15}.
Confidence per check: {"s1": [0.99, 0.99, 0.99, 0.99, 0.99], "s2": [0.96, 0.94, 0.96, 0.98, 0.98], "fulfillment": [0.96, 0.97, 0.96, 0.98, 0.98]}.
Known-answer consistency per check: {"s1": 1.0, "s2": 1.0, "fulfillment": 1.0}.

Search schedule: {"rounds_started": 15, "rounds_completed": 14, "max_rounds": 15}. Stop: round_limit.
Escalated: False. Usage: {"search": 109, "final": 30, "completion_tokens_or_reserved": 19414, "input_tokens": 432440}.

### Make her close her jacket fully — luna_then_sol

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 0.00 | 0.00 |
| Resolved draws / 5 | 5.00 | 5.00 |
| Final-label consistency | 1.00 | 1.00 |
| Minimum requirement consistency | 1.00 | 1.00 |
| Mean executed checks | 3.00 | 3.00 |
| Mean charged completion tokens | 170.60 | 169.20 |

Seed labels: {"no": 5}. Observation events: {"observed": 15}.
Confidence per check: {"s1": [0.99, 0.99, 0.99, 0.99, 0.99], "s2": [0.96, 0.96, 0.98, 0.96, 0.98], "fulfillment": [0.98, 0.98, 0.98, 0.97, 0.98]}.
Known-answer consistency per check: {"s1": 1.0, "s2": 1.0, "fulfillment": 1.0}.

Selected labels: {"no": 5}. Observation events: {"observed": 15}.
Confidence per check: {"s1": [0.99, 0.99, 0.99, 0.99, 0.99], "s2": [0.98, 0.94, 0.98, 0.96, 0.98], "fulfillment": [0.98, 0.97, 0.98, 0.97, 0.98]}.
Known-answer consistency per check: {"s1": 1.0, "s2": 1.0, "fulfillment": 1.0}.

Search schedule: {"rounds_started": 15, "rounds_completed": 15, "max_rounds": 15}. Stop: round_limit.
Escalated: True. Usage: {"search": 101, "final": 30, "completion_tokens_or_reserved": 20135, "input_tokens": 492436}.

### Change the image into pencil drawing — luna_only

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 0.00 | 0.00 |
| Resolved draws / 5 | 4.00 | 4.00 |
| Final-label consistency | 0.80 | 0.80 |
| Minimum requirement consistency | 0.80 | 0.80 |
| Mean executed checks | 2.20 | 2.20 |
| Mean charged completion tokens | 329.60 | 328.40 |

Seed labels: {"yes": 4, "unresolved": 1}. Observation events: {"observed": 9, "conditional_skip": 4, "transport_failure": 1, "valid_uncertainty": 1}.
Confidence per check: {"s1": [0.96, null, 0.96, 0.97, 0.96], "s2": [0.91], "fulfillment": [0.96, 0.91, 0.96, 0.97, 0.96]}.
Known-answer consistency per check: {"s1": 0.8, "s2": 1.0, "fulfillment": 0.8}.

Selected labels: {"yes": 4, "unresolved": 1}. Observation events: {"observed": 9, "conditional_skip": 4, "transport_failure": 1, "valid_uncertainty": 1}.
Confidence per check: {"s1": [0.96, null, 0.94, 0.98, 0.97], "s2": [0.91], "fulfillment": [0.96, 0.91, 0.94, 0.98, 0.97]}.
Known-answer consistency per check: {"s1": 0.8, "s2": 1.0, "fulfillment": 0.8}.

Search schedule: {"rounds_started": 15, "rounds_completed": 15, "max_rounds": 15}. Stop: round_limit.
Escalated: False. Usage: {"search": 73, "final": 22, "completion_tokens_or_reserved": 19312, "input_tokens": 325565}.

### Change the image into pencil drawing — luna_then_sol

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 0.00 | 5.00 |
| Resolved draws / 5 | 5.00 | 5.00 |
| Final-label consistency | 1.00 | 1.00 |
| Minimum requirement consistency | 1.00 | 1.00 |
| Mean executed checks | 2.00 | 3.00 |
| Mean charged completion tokens | 119.40 | 193.40 |

Seed labels: {"yes": 5}. Observation events: {"observed": 10, "conditional_skip": 5}.
Confidence per check: {"s1": [0.96, 0.96, 0.97, 0.96, 0.98], "s2": [], "fulfillment": [0.96, 0.96, 0.97, 0.96, 0.98]}.
Known-answer consistency per check: {"s1": 1.0, "s2": null, "fulfillment": 1.0}.

Selected labels: {"partial": 5}. Observation events: {"observed": 15}.
Confidence per check: {"s1": [0.98, 0.97, 0.97, 0.94, 0.97], "s2": [0.96, 0.94, 0.94, 0.96, 0.94], "fulfillment": [0.97, 0.95, 0.95, 0.95, 0.95]}.
Known-answer consistency per check: {"s1": 1.0, "s2": 1.0, "fulfillment": 1.0}.

Search schedule: {"rounds_started": 4, "rounds_completed": 3, "max_rounds": 15}. Stop: confirmation_qualified.
Escalated: False. Usage: {"search": 57, "final": 25, "completion_tokens_or_reserved": 9272, "input_tokens": 136312}.

### Give the woman a helmet — luna_only

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 5.00 | 5.00 |
| Resolved draws / 5 | 5.00 | 5.00 |
| Final-label consistency | 1.00 | 1.00 |
| Minimum requirement consistency | 1.00 | 1.00 |
| Mean executed checks | 3.00 | 3.00 |
| Mean charged completion tokens | 153.80 | 151.00 |

Seed labels: {"yes": 5}. Observation events: {"observed": 15}.
Confidence per check: {"s1": [0.99, 0.99, 0.99, 0.99, 0.99], "s2": [0.99, 0.99, 0.99, 0.99, 0.99], "fulfillment": [0.99, 0.99, 0.99, 0.99, 0.99]}.
Known-answer consistency per check: {"s1": 1.0, "s2": 1.0, "fulfillment": 1.0}.

Selected labels: {"yes": 5}. Observation events: {"observed": 15}.
Confidence per check: {"s1": [0.99, 0.99, 0.99, 0.99, 0.99], "s2": [0.99, 0.99, 0.99, 0.99, 0.99], "fulfillment": [0.99, 0.99, 0.99, 0.99, 0.99]}.
Known-answer consistency per check: {"s1": 1.0, "s2": 1.0, "fulfillment": 1.0}.

Search schedule: {"rounds_started": 15, "rounds_completed": 12, "max_rounds": 15}. Stop: round_limit.
Escalated: False. Usage: {"search": 77, "final": 30, "completion_tokens_or_reserved": 14905, "input_tokens": 327541}.

### Give the woman a helmet — luna_then_sol

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 5.00 | 4.00 |
| Resolved draws / 5 | 5.00 | 4.00 |
| Final-label consistency | 1.00 | 0.80 |
| Minimum requirement consistency | 1.00 | 0.80 |
| Mean executed checks | 3.00 | 3.00 |
| Mean charged completion tokens | 151.00 | 354.00 |

Seed labels: {"yes": 5}. Observation events: {"observed": 15}.
Confidence per check: {"s1": [0.99, 0.99, 0.99, 0.99, 0.99], "s2": [0.99, 0.99, 0.99, 0.99, 0.99], "fulfillment": [0.99, 0.99, 0.99, 0.99, 0.99]}.
Known-answer consistency per check: {"s1": 1.0, "s2": 1.0, "fulfillment": 1.0}.

Selected labels: {"yes": 4, "unresolved": 1}. Observation events: {"observed": 13, "transport_failure": 1, "valid_uncertainty": 1}.
Confidence per check: {"s1": [0.99, null, 0.99, 0.99, 0.99], "s2": [0.99, 0.99, 0.99, 0.99, 0.99], "fulfillment": [0.99, 0.99, 0.99, 0.99, 0.99]}.
Known-answer consistency per check: {"s1": 0.8, "s2": 1.0, "fulfillment": 0.8}.

Search schedule: {"rounds_started": 15, "rounds_completed": 13, "max_rounds": 15}. Stop: round_limit.
Escalated: True. Usage: {"search": 78, "final": 30, "completion_tokens_or_reserved": 14565, "input_tokens": 330798}.

### Change the background into a basketball court — luna_only

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 5.00 | 5.00 |
| Resolved draws / 5 | 5.00 | 5.00 |
| Final-label consistency | 1.00 | 1.00 |
| Minimum requirement consistency | 1.00 | 1.00 |
| Mean executed checks | 3.00 | 3.00 |
| Mean charged completion tokens | 373.20 | 182.20 |

Seed labels: {"yes": 5}. Observation events: {"observed": 14, "transport_failure": 1}.
Confidence per check: {"s1": [0.99, 0.99, 0.99, 0.99, 0.99], "s2": [null, 0.99, 0.99, 0.99, 0.99], "fulfillment": [0.99, 0.99, 0.99, 0.99, 0.99]}.
Known-answer consistency per check: {"s1": 1.0, "s2": 0.8, "fulfillment": 1.0}.

Selected labels: {"yes": 5}. Observation events: {"observed": 15}.
Confidence per check: {"s1": [0.99, 0.99, 0.99, 0.99, 0.99], "s2": [0.99, 0.99, 0.99, 0.99, 0.98], "fulfillment": [0.99, 0.99, 0.99, 0.99, 0.99]}.
Known-answer consistency per check: {"s1": 1.0, "s2": 1.0, "fulfillment": 1.0}.

Search schedule: {"rounds_started": 14, "rounds_completed": 13, "max_rounds": 15}. Stop: budget_exhausted: Case luna_only/aurora-task-65581617ad341fa398cb::magic_reproduce_epoch=47-step=12999 search allowance exhausted.
Escalated: False. Usage: {"search": 109, "final": 30, "completion_tokens_or_reserved": 18806, "input_tokens": 361930}.

### Change the background into a basketball court — luna_then_sol

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 5.00 | 5.00 |
| Resolved draws / 5 | 5.00 | 5.00 |
| Final-label consistency | 1.00 | 1.00 |
| Minimum requirement consistency | 1.00 | 1.00 |
| Mean executed checks | 3.00 | 2.00 |
| Mean charged completion tokens | 177.20 | 116.00 |

Seed labels: {"yes": 5}. Observation events: {"observed": 15}.
Confidence per check: {"s1": [0.99, 0.99, 0.99, 0.99, 0.99], "s2": [0.99, 0.99, 0.99, 0.99, 0.99], "fulfillment": [0.99, 0.99, 0.99, 0.99, 0.99]}.
Known-answer consistency per check: {"s1": 1.0, "s2": 0.8, "fulfillment": 1.0}.

Selected labels: {"yes": 5}. Observation events: {"observed": 10, "conditional_skip": 5}.
Confidence per check: {"s1": [0.99, 0.99, 0.99, 0.99, 0.99], "s2": [], "fulfillment": [0.99, 0.99, 0.99, 0.99, 0.99]}.
Known-answer consistency per check: {"s1": 1.0, "s2": null, "fulfillment": 1.0}.

Search schedule: {"rounds_started": 4, "rounds_completed": 4, "max_rounds": 15}. Stop: confirmation_qualified.
Escalated: True. Usage: {"search": 36, "final": 25, "completion_tokens_or_reserved": 5192, "input_tokens": 103950}.

### Move the mug to the right of the headphones — luna_only

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 0.00 | 0.00 |
| Resolved draws / 5 | 5.00 | 5.00 |
| Final-label consistency | 1.00 | 1.00 |
| Minimum requirement consistency | 1.00 | 1.00 |
| Mean executed checks | 3.00 | 3.00 |
| Mean charged completion tokens | 171.40 | 361.60 |

Seed labels: {"yes": 5}. Observation events: {"observed": 15}.
Confidence per check: {"s1": [0.99, 0.99, 0.99, 0.99, 0.99], "s2": [0.99, 0.99, 0.99, 0.98, 0.99], "fulfillment": [0.99, 0.99, 0.99, 0.98, 0.99]}.
Known-answer consistency per check: {"s1": 1.0, "s2": 1.0, "fulfillment": 1.0}.

Selected labels: {"yes": 5}. Observation events: {"observed": 14, "transport_failure": 1}.
Confidence per check: {"s1": [0.99, 0.99, 0.99, 0.99, 0.99], "s2": [0.98, 0.99, 0.98, 0.99, null], "fulfillment": [0.99, 0.99, 0.98, 0.99, 0.99]}.
Known-answer consistency per check: {"s1": 1.0, "s2": 0.8, "fulfillment": 1.0}.

Search schedule: {"rounds_started": 15, "rounds_completed": 14, "max_rounds": 15}. Stop: round_limit.
Escalated: False. Usage: {"search": 83, "final": 30, "completion_tokens_or_reserved": 27431, "input_tokens": 469676}.

### Move the mug to the right of the headphones — luna_then_sol

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 0.00 | 0.00 |
| Resolved draws / 5 | 5.00 | 5.00 |
| Final-label consistency | 1.00 | 1.00 |
| Minimum requirement consistency | 1.00 | 1.00 |
| Mean executed checks | 3.00 | 3.00 |
| Mean charged completion tokens | 163.00 | 167.80 |

Seed labels: {"yes": 5}. Observation events: {"observed": 15}.
Confidence per check: {"s1": [0.99, 0.99, 0.99, 0.99, 0.99], "s2": [0.98, 0.98, 0.99, 0.99, 0.99], "fulfillment": [0.99, 0.99, 0.99, 0.99, 0.99]}.
Known-answer consistency per check: {"s1": 1.0, "s2": 1.0, "fulfillment": 1.0}.

Selected labels: {"yes": 5}. Observation events: {"observed": 15}.
Confidence per check: {"s1": [0.99, 0.99, 0.99, 0.99, 0.99], "s2": [0.98, 0.99, 0.99, 0.98, 0.99], "fulfillment": [0.99, 0.99, 0.99, 0.99, 0.99]}.
Known-answer consistency per check: {"s1": 1.0, "s2": 1.0, "fulfillment": 1.0}.

Search schedule: {"rounds_started": 15, "rounds_completed": 14, "max_rounds": 15}. Stop: round_limit.
Escalated: True. Usage: {"search": 85, "final": 30, "completion_tokens_or_reserved": 22269, "input_tokens": 423289}.

### Move the book behind the flower — luna_only

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 2.00 | 4.00 |
| Resolved draws / 5 | 5.00 | 4.00 |
| Final-label consistency | 0.60 | 0.80 |
| Minimum requirement consistency | 0.60 | 0.80 |
| Mean executed checks | 3.00 | 3.00 |
| Mean charged completion tokens | 187.60 | 224.60 |

Seed labels: {"no": 2, "partial": 3}. Observation events: {"observed": 15}.
Confidence per check: {"s1": [0.99, 0.98, 0.99, 0.98, 0.99], "s2": [0.97, 0.94, 0.98, 0.98, 0.98], "fulfillment": [0.98, 0.94, 0.98, 0.98, 0.98]}.
Known-answer consistency per check: {"s1": 1.0, "s2": 0.6, "fulfillment": 0.6}.

Selected labels: {"unresolved": 1, "no": 4}. Observation events: {"observed": 14, "valid_uncertainty": 1}.
Confidence per check: {"s1": [0.98, 0.98, 0.98, 0.98, 0.99], "s2": [0.98, 0.94, 0.94, 0.94, 0.98], "fulfillment": [0.98, 0.96, 0.96, 0.96, 0.98]}.
Known-answer consistency per check: {"s1": 1.0, "s2": 1.0, "fulfillment": 0.8}.

Search schedule: {"rounds_started": 1, "rounds_completed": 1, "max_rounds": 15}. Stop: confirmation_qualified.
Escalated: False. Usage: {"search": 42, "final": 30, "completion_tokens_or_reserved": 5970, "input_tokens": 154401}.

### Move the book behind the flower — luna_then_sol

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 4.00 | 2.00 |
| Resolved draws / 5 | 4.00 | 5.00 |
| Final-label consistency | 0.80 | 0.60 |
| Minimum requirement consistency | 0.80 | 0.60 |
| Mean executed checks | 3.00 | 3.00 |
| Mean charged completion tokens | 190.60 | 183.60 |

Seed labels: {"no": 4, "unresolved": 1}. Observation events: {"observed": 14, "valid_uncertainty": 1}.
Confidence per check: {"s1": [0.99, 0.99, 0.99, 0.98, 0.98], "s2": [0.98, 0.94, 0.96, 0.96, 0.94], "fulfillment": [0.98, 0.94, 0.96, 0.96, 0.96]}.
Known-answer consistency per check: {"s1": 1.0, "s2": 1.0, "fulfillment": 0.8}.

Selected labels: {"no": 2, "partial": 3}. Observation events: {"observed": 15}.
Confidence per check: {"s1": [0.99, 0.98, 0.98, 0.99, 0.98], "s2": [0.94, 0.98, 0.97, 0.98, 0.98], "fulfillment": [0.94, 0.98, 0.97, 0.97, 0.98]}.
Known-answer consistency per check: {"s1": 1.0, "s2": 0.6, "fulfillment": 0.6}.

Search schedule: {"rounds_started": 0, "rounds_completed": 0, "max_rounds": 15}. Stop: confirmation_qualified.
Escalated: False. Usage: {"search": 18, "final": 30, "completion_tokens_or_reserved": 3032, "input_tokens": 87035}.

### Stuffing the paper into the cup — luna_only

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 5.00 | 5.00 |
| Resolved draws / 5 | 5.00 | 5.00 |
| Final-label consistency | 1.00 | 1.00 |
| Minimum requirement consistency | 1.00 | 1.00 |
| Mean executed checks | 3.00 | 3.00 |
| Mean charged completion tokens | 180.80 | 177.00 |

Seed labels: {"no": 5}. Observation events: {"observed": 15}.
Confidence per check: {"s1": [0.99, 0.99, 0.99, 0.99, 0.99], "s2": [0.91, 0.94, 0.91, 0.94, 0.94], "fulfillment": [0.98, 0.97, 0.96, 0.97, 0.97]}.
Known-answer consistency per check: {"s1": 1.0, "s2": 1.0, "fulfillment": 1.0}.

Selected labels: {"no": 5}. Observation events: {"observed": 15}.
Confidence per check: {"s1": [0.99, 0.99, 0.99, 0.99, 0.99], "s2": [0.91, 0.94, 0.91, 0.94, 0.91], "fulfillment": [0.95, 0.97, 0.98, 0.97, 0.98]}.
Known-answer consistency per check: {"s1": 1.0, "s2": 1.0, "fulfillment": 1.0}.

Search schedule: {"rounds_started": 15, "rounds_completed": 15, "max_rounds": 15}. Stop: round_limit.
Escalated: False. Usage: {"search": 94, "final": 30, "completion_tokens_or_reserved": 22229, "input_tokens": 310195}.

### Stuffing the paper into the cup — luna_then_sol

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 5.00 | 4.00 |
| Resolved draws / 5 | 5.00 | 5.00 |
| Final-label consistency | 1.00 | 0.80 |
| Minimum requirement consistency | 1.00 | 0.80 |
| Mean executed checks | 3.00 | 3.00 |
| Mean charged completion tokens | 181.40 | 180.00 |

Seed labels: {"no": 5}. Observation events: {"observed": 15}.
Confidence per check: {"s1": [0.99, 0.99, 0.99, 0.99, 0.99], "s2": [0.94, 0.94, 0.96, 0.94, 0.94], "fulfillment": [0.97, 0.97, 0.98, 0.97, 0.97]}.
Known-answer consistency per check: {"s1": 1.0, "s2": 1.0, "fulfillment": 1.0}.

Selected labels: {"no": 4, "partial": 1}. Observation events: {"observed": 15}.
Confidence per check: {"s1": [0.99, 0.99, 0.99, 0.99, 0.99], "s2": [0.91, 0.91, 0.94, 0.94, 0.94], "fulfillment": [0.95, 0.96, 0.94, 0.97, 0.97]}.
Known-answer consistency per check: {"s1": 1.0, "s2": 0.8, "fulfillment": 0.8}.

Search schedule: {"rounds_started": 15, "rounds_completed": 15, "max_rounds": 15}. Stop: round_limit.
Escalated: True. Usage: {"search": 85, "final": 30, "completion_tokens_or_reserved": 19351, "input_tokens": 319768}.

### Make this look like a comic book photo — luna_only

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 5.00 | 5.00 |
| Resolved draws / 5 | 5.00 | 5.00 |
| Final-label consistency | 1.00 | 1.00 |
| Minimum requirement consistency | 1.00 | 1.00 |
| Mean executed checks | 3.00 | 3.00 |
| Mean charged completion tokens | 204.20 | 194.60 |

Seed labels: {"no": 5}. Observation events: {"observed": 15}.
Confidence per check: {"s1": [0.98, 0.96, 0.96, 0.96, 0.98], "s2": [0.91, 0.91, 0.91, 0.91, 0.91], "fulfillment": [0.95, 0.94, 0.94, 0.94, 0.96]}.
Known-answer consistency per check: {"s1": 1.0, "s2": 1.0, "fulfillment": 1.0}.

Selected labels: {"no": 5}. Observation events: {"observed": 15}.
Confidence per check: {"s1": [0.96, 0.94, 0.96, 0.96, 0.96], "s2": [0.91, 0.91, 0.91, 0.91, 0.91], "fulfillment": [0.94, 0.93, 0.91, 0.94, 0.94]}.
Known-answer consistency per check: {"s1": 1.0, "s2": 1.0, "fulfillment": 1.0}.

Search schedule: {"rounds_started": 0, "rounds_completed": 0, "max_rounds": 15}. Stop: confirmation_qualified.
Escalated: False. Usage: {"search": 18, "final": 30, "completion_tokens_or_reserved": 3170, "input_tokens": 52811}.

### Make this look like a comic book photo — luna_then_sol

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 5.00 | 5.00 |
| Resolved draws / 5 | 5.00 | 5.00 |
| Final-label consistency | 1.00 | 1.00 |
| Minimum requirement consistency | 1.00 | 1.00 |
| Mean executed checks | 3.00 | 3.00 |
| Mean charged completion tokens | 188.00 | 203.20 |

Seed labels: {"no": 5}. Observation events: {"observed": 15}.
Confidence per check: {"s1": [0.94, 0.94, 0.96, 0.96, 0.94], "s2": [0.94, 0.94, 0.91, 0.94, 0.91], "fulfillment": [0.94, 0.94, 0.95, 0.95, 0.93]}.
Known-answer consistency per check: {"s1": 1.0, "s2": 1.0, "fulfillment": 1.0}.

Selected labels: {"no": 5}. Observation events: {"observed": 15}.
Confidence per check: {"s1": [0.98, 0.96, 0.96, 0.96, 0.97], "s2": [0.94, 0.94, 0.91, 0.91, 0.91], "fulfillment": [0.96, 0.95, 0.94, 0.94, 0.95]}.
Known-answer consistency per check: {"s1": 1.0, "s2": 1.0, "fulfillment": 1.0}.

Search schedule: {"rounds_started": 0, "rounds_completed": 0, "max_rounds": 15}. Stop: confirmation_qualified.
Escalated: False. Usage: {"search": 18, "final": 30, "completion_tokens_or_reserved": 3089, "input_tokens": 52711}.

### Turn the image into a drawing made from chalk — luna_only

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 0.00 | 0.00 |
| Resolved draws / 5 | 5.00 | 5.00 |
| Final-label consistency | 1.00 | 1.00 |
| Minimum requirement consistency | 1.00 | 1.00 |
| Mean executed checks | 2.00 | 2.00 |
| Mean charged completion tokens | 136.60 | 134.80 |

Seed labels: {"yes": 5}. Observation events: {"observed": 10, "conditional_skip": 5}.
Confidence per check: {"s1": [0.94, 0.94, 0.94, 0.94, 0.94], "s2": [], "fulfillment": [0.94, 0.94, 0.94, 0.94, 0.94]}.
Known-answer consistency per check: {"s1": 1.0, "s2": null, "fulfillment": 1.0}.

Selected labels: {"yes": 5}. Observation events: {"observed": 10, "conditional_skip": 5}.
Confidence per check: {"s1": [0.94, 0.94, 0.94, 0.94, 0.94], "s2": [], "fulfillment": [0.94, 0.94, 0.94, 0.94, 0.94]}.
Known-answer consistency per check: {"s1": 1.0, "s2": null, "fulfillment": 1.0}.

Search schedule: {"rounds_started": 15, "rounds_completed": 15, "max_rounds": 15}. Stop: round_limit.
Escalated: False. Usage: {"search": 65, "final": 20, "completion_tokens_or_reserved": 21804, "input_tokens": 310598}.

### Turn the image into a drawing made from chalk — luna_then_sol

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 0.00 | 5.00 |
| Resolved draws / 5 | 4.00 | 5.00 |
| Final-label consistency | 0.80 | 1.00 |
| Minimum requirement consistency | 0.80 | 1.00 |
| Mean executed checks | 2.20 | 3.00 |
| Mean charged completion tokens | 341.60 | 210.20 |

Seed labels: {"yes": 4, "unresolved": 1}. Observation events: {"observed": 9, "conditional_skip": 4, "transport_failure": 1, "valid_uncertainty": 1}.
Confidence per check: {"s1": [0.94, 0.97, 0.94, 0.94, null], "s2": [0.99], "fulfillment": [0.94, 0.97, 0.94, 0.94, 0.99]}.
Known-answer consistency per check: {"s1": 0.8, "s2": 1.0, "fulfillment": 0.8}.

Selected labels: {"partial": 5}. Observation events: {"observed": 15}.
Confidence per check: {"s1": [0.91, 0.91, 0.91, 0.91, 0.91], "s2": [0.88, 0.94, 0.88, 0.88, 0.9], "fulfillment": [0.9, 0.91, 0.9, 0.9, 0.9]}.
Known-answer consistency per check: {"s1": 1.0, "s2": 1.0, "fulfillment": 1.0}.

Search schedule: {"rounds_started": 12, "rounds_completed": 12, "max_rounds": 15}. Stop: confirmation_qualified.
Escalated: True. Usage: {"search": 73, "final": 26, "completion_tokens_or_reserved": 21103, "input_tokens": 264567}.

### Put a frog in the toilet — luna_only

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 0.00 | 0.00 |
| Resolved draws / 5 | 5.00 | 5.00 |
| Final-label consistency | 1.00 | 1.00 |
| Minimum requirement consistency | 1.00 | 1.00 |
| Mean executed checks | 3.00 | 3.00 |
| Mean charged completion tokens | 145.60 | 151.00 |

Seed labels: {"yes": 5}. Observation events: {"observed": 15}.
Confidence per check: {"s1": [0.99, 0.99, 0.99, 0.99, 0.99], "s2": [0.99, 0.99, 0.99, 0.99, 0.99], "fulfillment": [0.99, 0.99, 0.99, 0.99, 0.99]}.
Known-answer consistency per check: {"s1": 1.0, "s2": 1.0, "fulfillment": 1.0}.

Selected labels: {"yes": 5}. Observation events: {"observed": 15}.
Confidence per check: {"s1": [0.99, 0.99, 0.99, 0.99, 0.99], "s2": [0.99, 0.99, 0.99, 0.99, 0.99], "fulfillment": [0.99, 0.99, 0.99, 0.99, 0.99]}.
Known-answer consistency per check: {"s1": 1.0, "s2": 1.0, "fulfillment": 1.0}.

Search schedule: {"rounds_started": 15, "rounds_completed": 14, "max_rounds": 15}. Stop: round_limit.
Escalated: False. Usage: {"search": 84, "final": 30, "completion_tokens_or_reserved": 23587, "input_tokens": 484878}.

### Put a frog in the toilet — luna_then_sol

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 0.00 | 0.00 |
| Resolved draws / 5 | 5.00 | 5.00 |
| Final-label consistency | 1.00 | 1.00 |
| Minimum requirement consistency | 1.00 | 1.00 |
| Mean executed checks | 3.00 | 3.00 |
| Mean charged completion tokens | 150.00 | 343.40 |

Seed labels: {"yes": 5}. Observation events: {"observed": 15}.
Confidence per check: {"s1": [0.99, 0.99, 0.99, 0.99, 0.99], "s2": [0.99, 1, 0.99, 0.99, 0.99], "fulfillment": [0.99, 0.99, 0.99, 0.99, 0.99]}.
Known-answer consistency per check: {"s1": 1.0, "s2": 1.0, "fulfillment": 1.0}.

Selected labels: {"yes": 5}. Observation events: {"observed": 14, "transport_failure": 1}.
Confidence per check: {"s1": [0.99, null, 0.99, 0.99, 0.99], "s2": [0.99, 0.99, 0.99, 0.99, 0.99], "fulfillment": [0.99, 0.99, 0.99, 0.99, 0.99]}.
Known-answer consistency per check: {"s1": 0.8, "s2": 1.0, "fulfillment": 1.0}.

Search schedule: {"rounds_started": 15, "rounds_completed": 15, "max_rounds": 15}. Stop: round_limit.
Escalated: True. Usage: {"search": 83, "final": 30, "completion_tokens_or_reserved": 16028, "input_tokens": 436001}.

### the small gray rubber cylinder becomes brown — luna_only

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 5.00 | 5.00 |
| Resolved draws / 5 | 5.00 | 5.00 |
| Final-label consistency | 1.00 | 1.00 |
| Minimum requirement consistency | 1.00 | 1.00 |
| Mean executed checks | 3.00 | 3.00 |
| Mean charged completion tokens | 148.80 | 151.20 |

Seed labels: {"yes": 5}. Observation events: {"observed": 15}.
Confidence per check: {"s1": [0.99, 0.98, 0.98, 0.99, 0.98], "s2": [0.98, 0.98, 0.98, 0.98, 0.98], "fulfillment": [0.98, 0.98, 0.98, 0.98, 0.98]}.
Known-answer consistency per check: {"s1": 1.0, "s2": 1.0, "fulfillment": 1.0}.

Selected labels: {"yes": 5}. Observation events: {"observed": 15}.
Confidence per check: {"s1": [0.99, 0.99, 0.99, 0.99, 0.99], "s2": [0.98, 0.98, 0.98, 0.98, 0.98], "fulfillment": [0.98, 0.98, 0.98, 0.99, 0.98]}.
Known-answer consistency per check: {"s1": 0.8, "s2": 1.0, "fulfillment": 1.0}.

Search schedule: {"rounds_started": 0, "rounds_completed": 0, "max_rounds": 15}. Stop: confirmation_qualified.
Escalated: False. Usage: {"search": 18, "final": 30, "completion_tokens_or_reserved": 2377, "input_tokens": 46843}.

### the small gray rubber cylinder becomes brown — luna_then_sol

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 5.00 | 5.00 |
| Resolved draws / 5 | 5.00 | 5.00 |
| Final-label consistency | 1.00 | 1.00 |
| Minimum requirement consistency | 1.00 | 1.00 |
| Mean executed checks | 3.00 | 3.00 |
| Mean charged completion tokens | 149.00 | 147.00 |

Seed labels: {"yes": 5}. Observation events: {"observed": 15}.
Confidence per check: {"s1": [0.99, 0.99, 0.99, 0.99, 0.99], "s2": [0.98, 0.99, 0.98, 0.97, 0.98], "fulfillment": [0.98, 0.99, 0.99, 0.98, 0.98]}.
Known-answer consistency per check: {"s1": 1.0, "s2": 1.0, "fulfillment": 1.0}.

Selected labels: {"yes": 5}. Observation events: {"observed": 15}.
Confidence per check: {"s1": [0.99, 0.99, 0.99, 0.99, 0.99], "s2": [0.98, 0.98, 0.98, 0.98, 0.98], "fulfillment": [0.98, 0.98, 0.98, 0.98, 0.98]}.
Known-answer consistency per check: {"s1": 1.0, "s2": 1.0, "fulfillment": 1.0}.

Search schedule: {"rounds_started": 0, "rounds_completed": 0, "max_rounds": 15}. Stop: confirmation_qualified.
Escalated: False. Usage: {"search": 18, "final": 30, "completion_tokens_or_reserved": 2325, "input_tokens": 46844}.

## Accounting

{
  "calls": 2341,
  "completion_tokens_or_reserved": 383754,
  "input_tokens": 7067439,
  "consecutive_errors": 0,
  "stopped": null,
  "final_calls": 688,
  "final_tokens": 46189
}

Returned models: gpt-6-luna, gpt-6.1-sol
Error: none

Historical results are descriptive. This comparison isolates proposer escalation under the same new runtime. Confidence is self-report, semantic audit is fallible, and unvisited alternatives remain untested. A reference-conflict flag requests review; it does not certify that the saved label is wrong.
