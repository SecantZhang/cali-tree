# Counting-only leaf experiment

Twelve previously observed local fitting cases, four per class. Repeats are within-case measurements. No held-out generalization or atomic correctness claim.

Status: completed

Semantic auditing is disabled. All independent required conditions pass → yes; all fail → no; mixed → partial; any unknown → unresolved. No model readout runs. The confidence/repeat gates still govern empirical robust status.
Agreement means reference matches; coverage means a resolved answer, including wrong answers. Each case has five fresh final draws. Missing or unresolved draws count as nonmatches; repeated draws are not additional cases. Both arms use the corrected runtime and strict gates.

| Arm | Seed → selected matches | Selected resolved | Locally robust cases | Escalated cases |
|---|---:|---:|---:|---:|
| luna_only | 28 → 44 / 60 | 59 / 60 | 8 / 12 | 0 / 12 |
| luna_then_sol | 28 → 36 / 60 | 60 / 60 | 6 / 12 | 6 / 12 |

| Instruction / reference | Arm | Seed → selected matches / 5 | Resolved / 5 | Mean executed checks | Confidence gate | Status / failure reason |
|---|---|---:|---:|---:|---|---|
| transform the black DVD into a white DVD / no | luna_only | 0 → 5 | 5 | 1.0 | passed | locally_robust;  |
| transform the black DVD into a white DVD / no | luna_then_sol | 0 → 0 | 5 | 2.0 | passed | stable_but_mismatched; target_mismatch, confirmation_missing_or_unqualified |
| Make her close her jacket fully / yes | luna_only | 0 → 0 | 5 | 1.0 | passed | stable_but_mismatched; target_mismatch, confirmation_missing_or_unqualified |
| Make her close her jacket fully / yes | luna_then_sol | 0 → 0 | 5 | 1.0 | passed | stable_but_mismatched; target_mismatch, confirmation_missing_or_unqualified |
| Change the image into pencil drawing / partial | luna_only | 0 → 0 | 5 | 1.0 | passed | stable_but_mismatched; target_mismatch, confirmation_missing_or_unqualified |
| Change the image into pencil drawing / partial | luna_then_sol | 0 → 5 | 5 | 2.0 | passed | unconfirmed; confirmation_missing_or_unqualified |
| Give the woman a helmet / yes | luna_only | 5 → 5 | 5 | 1.0 | passed | locally_robust;  |
| Give the woman a helmet / yes | luna_then_sol | 5 → 5 | 5 | 1.0 | passed | locally_robust;  |
| Change the background into a basketball court / yes | luna_only | 5 → 5 | 5 | 1.0 | passed | locally_robust;  |
| Change the background into a basketball court / yes | luna_then_sol | 5 → 5 | 5 | 1.0 | passed | locally_robust;  |
| Move the mug to the right of the headphones / partial | luna_only | 0 → 0 | 5 | 1.0 | passed | stable_but_mismatched; target_mismatch, confirmation_missing_or_unqualified |
| Move the mug to the right of the headphones / partial | luna_then_sol | 0 → 0 | 5 | 1.0 | passed | stable_but_mismatched; target_mismatch, confirmation_missing_or_unqualified |
| Move the book behind the flower / no | luna_only | 5 → 5 | 5 | 1.0 | passed | locally_robust;  |
| Move the book behind the flower / no | luna_then_sol | 5 → 5 | 5 | 1.0 | passed | locally_robust;  |
| Stuffing the paper into the cup / no | luna_only | 5 → 5 | 5 | 1.0 | passed | locally_robust;  |
| Stuffing the paper into the cup / no | luna_then_sol | 5 → 5 | 5 | 1.0 | passed | locally_robust;  |
| Make this look like a comic book photo / no | luna_only | 5 → 5 | 5 | 1.0 | passed | locally_robust;  |
| Make this look like a comic book photo / no | luna_then_sol | 5 → 5 | 5 | 1.0 | passed | locally_robust;  |
| Turn the image into a drawing made from chalk / partial | luna_only | 0 → 5 | 5 | 2.0 | passed | locally_robust;  |
| Turn the image into a drawing made from chalk / partial | luna_then_sol | 0 → 1 | 5 | 2.0 | passed | unstable_and_mismatched; target_mismatch, confirmation_missing_or_unqualified |
| Put a frog in the toilet / partial | luna_only | 0 → 4 | 4 | 2.0 | failed/unavailable | unresolved; unresolved, confidence |
| Put a frog in the toilet / partial | luna_then_sol | 0 → 0 | 5 | 1.0 | passed | stable_but_mismatched; target_mismatch, confirmation_missing_or_unqualified |
| the small gray rubber cylinder becomes brown / yes | luna_only | 3 → 5 | 5 | 1.0 | passed | locally_robust;  |
| the small gray rubber cylinder becomes brown / yes | luna_then_sol | 3 → 5 | 5 | 2.0 | passed | locally_robust;  |

## Per-case execution details

Consistency is measured separately from reference agreement. An uncertain answer can repeat consistently yet fail the known-answer stability gate. Skipped checks remain untested. The observation counts below count checks across five runs, not independent cases.

### transform the black DVD into a white DVD — luna_only

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 0.00 | 5.00 |
| Resolved draws / 5 | 5.00 | 5.00 |
| Final-label consistency | 1.00 | 1.00 |
| Minimum requirement consistency | 1.00 | 1.00 |
| Mean executed checks | 2.00 | 1.00 |
| Mean charged completion tokens | 102.60 | 86.60 |

Seed labels: {"yes": 5}. Observation events: {"observed": 10}.
Confidence per check: {"d1": [0.98, 0.98, 0.98, 0.98, 0.98], "d2": [0.91, 0.91, 0.91, 0.98, 0.94]}.
Known-answer consistency per check: {"d1": 1.0, "d2": 1.0}.

Selected labels: {"no": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.98, 0.97, 0.97, 0.96, 0.96]}.
Known-answer consistency per check: {"d1": 1.0}.

Search schedule: {"rounds_started": 2, "rounds_completed": 2, "max_rounds": 15}. Stop: confirmation_qualified.
Escalated: False. Usage: {"search": 28, "final": 15, "completion_tokens_or_reserved": 3996, "input_tokens": 60222}.

### transform the black DVD into a white DVD — luna_then_sol

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 0.00 | 0.00 |
| Resolved draws / 5 | 5.00 | 5.00 |
| Final-label consistency | 1.00 | 1.00 |
| Minimum requirement consistency | 1.00 | 1.00 |
| Mean executed checks | 2.00 | 2.00 |
| Mean charged completion tokens | 108.80 | 110.60 |

Seed labels: {"yes": 5}. Observation events: {"observed": 10}.
Confidence per check: {"d1": [0.98, 0.98, 0.98, 0.98, 0.98], "d2": [0.94, 0.91, 0.94, 0.91, 0.91]}.
Known-answer consistency per check: {"d1": 1.0, "d2": 1.0}.

Selected labels: {"yes": 5}. Observation events: {"observed": 10}.
Confidence per check: {"d1": [0.98, 0.96, 0.98, 0.98, 0.91], "d2": [0.91, 0.91, 0.91, 0.91, 0.91]}.
Known-answer consistency per check: {"d1": 1.0, "d2": 1.0}.

Search schedule: {"rounds_started": 15, "rounds_completed": 13, "max_rounds": 15}. Stop: round_limit.
Escalated: True. Usage: {"search": 85, "final": 20, "completion_tokens_or_reserved": 23754, "input_tokens": 204322}.

### Make her close her jacket fully — luna_only

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 0.00 | 0.00 |
| Resolved draws / 5 | 5.00 | 5.00 |
| Final-label consistency | 1.00 | 1.00 |
| Minimum requirement consistency | 1.00 | 1.00 |
| Mean executed checks | 1.00 | 1.00 |
| Mean charged completion tokens | 50.40 | 50.00 |

Seed labels: {"no": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.98, 0.99, 0.99, 0.98, 0.99]}.
Known-answer consistency per check: {"d1": 1.0}.

Selected labels: {"no": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.99, 0.98, 0.98, 0.99, 0.99]}.
Known-answer consistency per check: {"d1": 1.0}.

Search schedule: {"rounds_started": 15, "rounds_completed": 15, "max_rounds": 15}. Stop: round_limit.
Escalated: False. Usage: {"search": 71, "final": 10, "completion_tokens_or_reserved": 10327, "input_tokens": 141777}.

### Make her close her jacket fully — luna_then_sol

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 0.00 | 0.00 |
| Resolved draws / 5 | 5.00 | 5.00 |
| Final-label consistency | 1.00 | 1.00 |
| Minimum requirement consistency | 1.00 | 1.00 |
| Mean executed checks | 1.00 | 1.00 |
| Mean charged completion tokens | 50.80 | 50.40 |

Seed labels: {"no": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.98, 0.98, 0.99, 0.98, 0.98]}.
Known-answer consistency per check: {"d1": 1.0}.

Selected labels: {"no": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.98, 0.98, 0.98, 0.98, 0.99]}.
Known-answer consistency per check: {"d1": 1.0}.

Search schedule: {"rounds_started": 15, "rounds_completed": 14, "max_rounds": 15}. Stop: round_limit.
Escalated: True. Usage: {"search": 62, "final": 10, "completion_tokens_or_reserved": 11081, "input_tokens": 127981}.

### Change the image into pencil drawing — luna_only

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 0.00 | 0.00 |
| Resolved draws / 5 | 5.00 | 5.00 |
| Final-label consistency | 1.00 | 1.00 |
| Minimum requirement consistency | 1.00 | 1.00 |
| Mean executed checks | 1.00 | 1.00 |
| Mean charged completion tokens | 63.20 | 67.40 |

Seed labels: {"yes": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.98, 0.98, 0.98, 0.98, 0.97]}.
Known-answer consistency per check: {"d1": 1.0}.

Selected labels: {"yes": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.97, 0.98, 0.96, 0.97, 0.96]}.
Known-answer consistency per check: {"d1": 1.0}.

Search schedule: {"rounds_started": 15, "rounds_completed": 12, "max_rounds": 15}. Stop: round_limit.
Escalated: False. Usage: {"search": 64, "final": 10, "completion_tokens_or_reserved": 19551, "input_tokens": 132175}.

### Change the image into pencil drawing — luna_then_sol

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 0.00 | 5.00 |
| Resolved draws / 5 | 5.00 | 5.00 |
| Final-label consistency | 1.00 | 1.00 |
| Minimum requirement consistency | 1.00 | 1.00 |
| Mean executed checks | 1.00 | 2.00 |
| Mean charged completion tokens | 64.80 | 156.80 |

Seed labels: {"yes": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.97, 0.98, 0.98, 0.97, 0.98]}.
Known-answer consistency per check: {"d1": 1.0}.

Selected labels: {"partial": 5}. Observation events: {"observed": 10}.
Confidence per check: {"d1_contours": [0.91, 0.91, 0.91, 0.91, 0.91], "d1_shading": [0.96, 0.96, 0.96, 0.94, 0.96]}.
Known-answer consistency per check: {"d1_contours": 1.0, "d1_shading": 1.0}.

Search schedule: {"rounds_started": 14, "rounds_completed": 12, "max_rounds": 15}. Stop: budget_exhausted: Case luna_then_sol/aurora-task-52fd3fa52d915723d12d::mgie search allowance exhausted.
Escalated: True. Usage: {"search": 109, "final": 15, "completion_tokens_or_reserved": 21492, "input_tokens": 261899}.

### Give the woman a helmet — luna_only

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 5.00 | 5.00 |
| Resolved draws / 5 | 5.00 | 5.00 |
| Final-label consistency | 1.00 | 1.00 |
| Minimum requirement consistency | 1.00 | 1.00 |
| Mean executed checks | 1.00 | 1.00 |
| Mean charged completion tokens | 45.20 | 44.80 |

Seed labels: {"yes": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.99, 0.99, 0.99, 0.99, 0.99]}.
Known-answer consistency per check: {"d1": 1.0}.

Selected labels: {"yes": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.99, 0.99, 0.99, 0.99, 0.99]}.
Known-answer consistency per check: {"d1": 1.0}.

Search schedule: {"rounds_started": 0, "rounds_completed": 0, "max_rounds": 15}. Stop: confirmation_qualified.
Escalated: False. Usage: {"search": 6, "final": 10, "completion_tokens_or_reserved": 719, "input_tokens": 30016}.

### Give the woman a helmet — luna_then_sol

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 5.00 | 5.00 |
| Resolved draws / 5 | 5.00 | 5.00 |
| Final-label consistency | 1.00 | 1.00 |
| Minimum requirement consistency | 1.00 | 1.00 |
| Mean executed checks | 1.00 | 1.00 |
| Mean charged completion tokens | 45.40 | 44.20 |

Seed labels: {"yes": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.99, 0.99, 0.99, 0.99, 0.99]}.
Known-answer consistency per check: {"d1": 1.0}.

Selected labels: {"yes": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.99, 0.99, 0.99, 0.99, 0.99]}.
Known-answer consistency per check: {"d1": 1.0}.

Search schedule: {"rounds_started": 0, "rounds_completed": 0, "max_rounds": 15}. Stop: confirmation_qualified.
Escalated: False. Usage: {"search": 6, "final": 10, "completion_tokens_or_reserved": 717, "input_tokens": 30016}.

### Change the background into a basketball court — luna_only

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 5.00 | 5.00 |
| Resolved draws / 5 | 5.00 | 5.00 |
| Final-label consistency | 1.00 | 1.00 |
| Minimum requirement consistency | 1.00 | 1.00 |
| Mean executed checks | 1.00 | 1.00 |
| Mean charged completion tokens | 55.40 | 51.20 |

Seed labels: {"yes": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.99, 0.99, 0.99, 0.99, 0.99]}.
Known-answer consistency per check: {"d1": 1.0}.

Selected labels: {"yes": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.99, 0.99, 0.99, 0.99, 0.99]}.
Known-answer consistency per check: {"d1": 1.0}.

Search schedule: {"rounds_started": 0, "rounds_completed": 0, "max_rounds": 15}. Stop: confirmation_qualified.
Escalated: False. Usage: {"search": 6, "final": 10, "completion_tokens_or_reserved": 868, "input_tokens": 15488}.

### Change the background into a basketball court — luna_then_sol

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 5.00 | 5.00 |
| Resolved draws / 5 | 5.00 | 5.00 |
| Final-label consistency | 1.00 | 1.00 |
| Minimum requirement consistency | 1.00 | 1.00 |
| Mean executed checks | 1.00 | 1.00 |
| Mean charged completion tokens | 53.00 | 53.40 |

Seed labels: {"yes": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.99, 0.99, 0.99, 0.99, 0.99]}.
Known-answer consistency per check: {"d1": 1.0}.

Selected labels: {"yes": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.99, 0.99, 0.99, 0.99, 0.99]}.
Known-answer consistency per check: {"d1": 1.0}.

Search schedule: {"rounds_started": 0, "rounds_completed": 0, "max_rounds": 15}. Stop: confirmation_qualified.
Escalated: False. Usage: {"search": 6, "final": 10, "completion_tokens_or_reserved": 849, "input_tokens": 15488}.

### Move the mug to the right of the headphones — luna_only

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 0.00 | 0.00 |
| Resolved draws / 5 | 5.00 | 5.00 |
| Final-label consistency | 1.00 | 1.00 |
| Minimum requirement consistency | 1.00 | 1.00 |
| Mean executed checks | 1.00 | 1.00 |
| Mean charged completion tokens | 56.40 | 56.00 |

Seed labels: {"yes": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.98, 0.98, 0.98, 0.98, 0.99]}.
Known-answer consistency per check: {"d1": 1.0}.

Selected labels: {"yes": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.99, 0.96, 0.99, 0.99, 0.98]}.
Known-answer consistency per check: {"d1": 1.0}.

Search schedule: {"rounds_started": 15, "rounds_completed": 15, "max_rounds": 15}. Stop: round_limit.
Escalated: False. Usage: {"search": 75, "final": 10, "completion_tokens_or_reserved": 17246, "input_tokens": 258362}.

### Move the mug to the right of the headphones — luna_then_sol

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 0.00 | 0.00 |
| Resolved draws / 5 | 5.00 | 5.00 |
| Final-label consistency | 1.00 | 1.00 |
| Minimum requirement consistency | 1.00 | 1.00 |
| Mean executed checks | 1.00 | 1.00 |
| Mean charged completion tokens | 58.00 | 55.00 |

Seed labels: {"yes": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.98, 0.97, 0.94, 0.98, 0.99]}.
Known-answer consistency per check: {"d1": 1.0}.

Selected labels: {"yes": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.99, 0.98, 0.91, 0.98, 0.99]}.
Known-answer consistency per check: {"d1": 1.0}.

Search schedule: {"rounds_started": 15, "rounds_completed": 14, "max_rounds": 15}. Stop: round_limit.
Escalated: True. Usage: {"search": 62, "final": 10, "completion_tokens_or_reserved": 16857, "input_tokens": 224447}.

### Move the book behind the flower — luna_only

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 5.00 | 5.00 |
| Resolved draws / 5 | 5.00 | 5.00 |
| Final-label consistency | 1.00 | 1.00 |
| Minimum requirement consistency | 1.00 | 1.00 |
| Mean executed checks | 1.00 | 1.00 |
| Mean charged completion tokens | 61.20 | 64.20 |

Seed labels: {"no": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.98, 0.98, 0.98, 0.98, 0.98]}.
Known-answer consistency per check: {"d1": 1.0}.

Selected labels: {"no": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.98, 0.99, 0.98, 0.98, 0.98]}.
Known-answer consistency per check: {"d1": 1.0}.

Search schedule: {"rounds_started": 0, "rounds_completed": 0, "max_rounds": 15}. Stop: confirmation_qualified.
Escalated: False. Usage: {"search": 6, "final": 10, "completion_tokens_or_reserved": 961, "input_tokens": 32288}.

### Move the book behind the flower — luna_then_sol

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 5.00 | 5.00 |
| Resolved draws / 5 | 5.00 | 5.00 |
| Final-label consistency | 1.00 | 1.00 |
| Minimum requirement consistency | 1.00 | 1.00 |
| Mean executed checks | 1.00 | 1.00 |
| Mean charged completion tokens | 58.80 | 61.00 |

Seed labels: {"no": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.98, 0.99, 0.98, 0.99, 0.98]}.
Known-answer consistency per check: {"d1": 1.0}.

Selected labels: {"no": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.98, 0.99, 0.94, 0.98, 0.99]}.
Known-answer consistency per check: {"d1": 1.0}.

Search schedule: {"rounds_started": 0, "rounds_completed": 0, "max_rounds": 15}. Stop: confirmation_qualified.
Escalated: False. Usage: {"search": 6, "final": 10, "completion_tokens_or_reserved": 935, "input_tokens": 32288}.

### Stuffing the paper into the cup — luna_only

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 5.00 | 5.00 |
| Resolved draws / 5 | 5.00 | 5.00 |
| Final-label consistency | 1.00 | 1.00 |
| Minimum requirement consistency | 1.00 | 1.00 |
| Mean executed checks | 1.00 | 1.00 |
| Mean charged completion tokens | 58.20 | 55.00 |

Seed labels: {"no": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.98, 0.99, 0.98, 0.99, 0.94]}.
Known-answer consistency per check: {"d1": 1.0}.

Selected labels: {"no": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.98, 0.98, 0.98, 0.98, 0.98]}.
Known-answer consistency per check: {"d1": 1.0}.

Search schedule: {"rounds_started": 0, "rounds_completed": 0, "max_rounds": 15}. Stop: confirmation_qualified.
Escalated: False. Usage: {"search": 6, "final": 10, "completion_tokens_or_reserved": 928, "input_tokens": 10112}.

### Stuffing the paper into the cup — luna_then_sol

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 5.00 | 5.00 |
| Resolved draws / 5 | 5.00 | 5.00 |
| Final-label consistency | 1.00 | 1.00 |
| Minimum requirement consistency | 1.00 | 1.00 |
| Mean executed checks | 1.00 | 1.00 |
| Mean charged completion tokens | 57.80 | 53.60 |

Seed labels: {"no": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.98, 0.98, 0.99, 0.98, 0.99]}.
Known-answer consistency per check: {"d1": 1.0}.

Selected labels: {"no": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.98, 0.97, 0.98, 0.98, 0.98]}.
Known-answer consistency per check: {"d1": 1.0}.

Search schedule: {"rounds_started": 0, "rounds_completed": 0, "max_rounds": 15}. Stop: confirmation_qualified.
Escalated: False. Usage: {"search": 6, "final": 10, "completion_tokens_or_reserved": 896, "input_tokens": 10112}.

### Make this look like a comic book photo — luna_only

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 5.00 | 5.00 |
| Resolved draws / 5 | 5.00 | 5.00 |
| Final-label consistency | 1.00 | 1.00 |
| Minimum requirement consistency | 1.00 | 1.00 |
| Mean executed checks | 1.00 | 1.00 |
| Mean charged completion tokens | 70.80 | 76.40 |

Seed labels: {"no": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.94, 0.91, 0.94, 0.94, 0.91]}.
Known-answer consistency per check: {"d1": 1.0}.

Selected labels: {"no": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.91, 0.91, 0.91, 0.91, 0.91]}.
Known-answer consistency per check: {"d1": 1.0}.

Search schedule: {"rounds_started": 0, "rounds_completed": 0, "max_rounds": 15}. Stop: confirmation_qualified.
Escalated: False. Usage: {"search": 6, "final": 10, "completion_tokens_or_reserved": 1195, "input_tokens": 15392}.

### Make this look like a comic book photo — luna_then_sol

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 5.00 | 5.00 |
| Resolved draws / 5 | 5.00 | 5.00 |
| Final-label consistency | 1.00 | 1.00 |
| Minimum requirement consistency | 1.00 | 1.00 |
| Mean executed checks | 1.00 | 1.00 |
| Mean charged completion tokens | 73.80 | 73.40 |

Seed labels: {"no": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.91, 0.94, 0.91, 0.91, 0.94]}.
Known-answer consistency per check: {"d1": 1.0}.

Selected labels: {"no": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.91, 0.91, 0.91, 0.94, 0.91]}.
Known-answer consistency per check: {"d1": 1.0}.

Search schedule: {"rounds_started": 0, "rounds_completed": 0, "max_rounds": 15}. Stop: confirmation_qualified.
Escalated: False. Usage: {"search": 6, "final": 10, "completion_tokens_or_reserved": 1181, "input_tokens": 15392}.

### Turn the image into a drawing made from chalk — luna_only

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 0.00 | 5.00 |
| Resolved draws / 5 | 5.00 | 5.00 |
| Final-label consistency | 1.00 | 1.00 |
| Minimum requirement consistency | 1.00 | 1.00 |
| Mean executed checks | 1.00 | 2.00 |
| Mean charged completion tokens | 61.20 | 163.40 |

Seed labels: {"yes": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.94, 0.91, 0.94, 0.96, 0.91]}.
Known-answer consistency per check: {"d1": 1.0}.

Selected labels: {"partial": 5}. Observation events: {"observed": 10}.
Confidence per check: {"d1_complete": [0.97, 0.97, 0.96, 0.97, 0.96], "d1_progress": [0.98, 0.98, 0.98, 0.98, 0.98]}.
Known-answer consistency per check: {"d1_complete": 1.0, "d1_progress": 1.0}.

Search schedule: {"rounds_started": 5, "rounds_completed": 5, "max_rounds": 15}. Stop: confirmation_qualified.
Escalated: False. Usage: {"search": 37, "final": 15, "completion_tokens_or_reserved": 5482, "input_tokens": 74045}.

### Turn the image into a drawing made from chalk — luna_then_sol

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 0.00 | 1.00 |
| Resolved draws / 5 | 5.00 | 5.00 |
| Final-label consistency | 1.00 | 0.80 |
| Minimum requirement consistency | 1.00 | 0.80 |
| Mean executed checks | 1.00 | 2.00 |
| Mean charged completion tokens | 65.40 | 178.20 |

Seed labels: {"yes": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.94, 0.91, 0.94, 0.91, 0.94]}.
Known-answer consistency per check: {"d1": 1.0}.

Selected labels: {"no": 4, "partial": 1}. Observation events: {"observed": 10}.
Confidence per check: {"d1_chalk_medium": [0.94, 0.94, 0.94, 0.94, 0.91], "d1_drawn_representation": [0.94, 0.91, 0.94, 0.94, 0.91]}.
Known-answer consistency per check: {"d1_chalk_medium": 1.0, "d1_drawn_representation": 0.8}.

Search schedule: {"rounds_started": 13, "rounds_completed": 12, "max_rounds": 15}. Stop: budget_exhausted: Case luna_then_sol/aurora-task-ce641cb29939011016cc::mgie search allowance exhausted.
Escalated: True. Usage: {"search": 109, "final": 15, "completion_tokens_or_reserved": 18974, "input_tokens": 237450}.

### Put a frog in the toilet — luna_only

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 0.00 | 4.00 |
| Resolved draws / 5 | 5.00 | 4.00 |
| Final-label consistency | 1.00 | 0.80 |
| Minimum requirement consistency | 1.00 | 0.80 |
| Mean executed checks | 1.00 | 2.00 |
| Mean charged completion tokens | 53.40 | 309.60 |

Seed labels: {"yes": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.99, 0.99, 0.99, 0.99, 0.99]}.
Known-answer consistency per check: {"d1": 1.0}.

Selected labels: {"partial": 4, "unresolved": 1}. Observation events: {"observed": 9, "transport_failure": 1}.
Confidence per check: {"d1_bowl": [0.99, 0.99, 0.99, 0.99, 0.99], "d1_scope": [0.99, null, 0.99, 0.99, 0.99]}.
Known-answer consistency per check: {"d1_bowl": 1.0, "d1_scope": 0.8}.

Search schedule: {"rounds_started": 13, "rounds_completed": 13, "max_rounds": 15}. Stop: confirmation_qualified.
Escalated: False. Usage: {"search": 65, "final": 15, "completion_tokens_or_reserved": 8494, "input_tokens": 280911}.

### Put a frog in the toilet — luna_then_sol

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 0.00 | 0.00 |
| Resolved draws / 5 | 4.00 | 5.00 |
| Final-label consistency | 0.80 | 1.00 |
| Minimum requirement consistency | 0.80 | 1.00 |
| Mean executed checks | 1.00 | 1.00 |
| Mean charged completion tokens | 242.40 | 50.20 |

Seed labels: {"yes": 4, "unresolved": 1}. Observation events: {"observed": 4, "transport_failure": 1}.
Confidence per check: {"d1": [0.99, 0.99, null, 0.99, 0.99]}.
Known-answer consistency per check: {"d1": 0.8}.

Selected labels: {"yes": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.99, 0.99, 0.99, 0.99, 0.99]}.
Known-answer consistency per check: {"d1": 1.0}.

Search schedule: {"rounds_started": 15, "rounds_completed": 14, "max_rounds": 15}. Stop: round_limit.
Escalated: True. Usage: {"search": 58, "final": 10, "completion_tokens_or_reserved": 10077, "input_tokens": 240324}.

### the small gray rubber cylinder becomes brown — luna_only

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 3.00 | 5.00 |
| Resolved draws / 5 | 5.00 | 5.00 |
| Final-label consistency | 0.60 | 1.00 |
| Minimum requirement consistency | 0.60 | 1.00 |
| Mean executed checks | 1.00 | 1.00 |
| Mean charged completion tokens | 67.40 | 66.20 |

Seed labels: {"yes": 3, "no": 2}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.96, 0.98, 0.91, 0.91, 0.98]}.
Known-answer consistency per check: {"d1": 0.6}.

Selected labels: {"yes": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.96, 0.96, 0.96, 0.98, 0.94]}.
Known-answer consistency per check: {"d1": 1.0}.

Search schedule: {"rounds_started": 0, "rounds_completed": 0, "max_rounds": 15}. Stop: confirmation_qualified.
Escalated: False. Usage: {"search": 6, "final": 10, "completion_tokens_or_reserved": 1067, "input_tokens": 12784}.

### the small gray rubber cylinder becomes brown — luna_then_sol

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 3.00 | 5.00 |
| Resolved draws / 5 | 5.00 | 5.00 |
| Final-label consistency | 0.60 | 1.00 |
| Minimum requirement consistency | 0.60 | 1.00 |
| Mean executed checks | 1.00 | 2.00 |
| Mean charged completion tokens | 65.60 | 135.60 |

Seed labels: {"yes": 3, "no": 2}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.98, 0.98, 0.96, 0.91, 0.91]}.
Known-answer consistency per check: {"d1": 0.6}.

Selected labels: {"yes": 5}. Observation events: {"observed": 10}.
Confidence per check: {"d1_color": [0.98, 0.98, 0.98, 0.98, 0.98], "d1_identity": [0.94, 0.91, 0.94, 0.94, 0.91]}.
Known-answer consistency per check: {"d1_color": 1.0, "d1_identity": 1.0}.

Search schedule: {"rounds_started": 1, "rounds_completed": 1, "max_rounds": 15}. Stop: confirmation_qualified.
Escalated: False. Usage: {"search": 21, "final": 15, "completion_tokens_or_reserved": 3016, "input_tokens": 36816}.

## Accounting

{
  "calls": 1204,
  "completion_tokens_or_reserved": 181938,
  "input_tokens": 2505899,
  "consecutive_errors": 0,
  "stopped": null,
  "final_calls": 280,
  "final_tokens": 19016
}

Returned models: gpt-6-luna, gpt-6.1-sol
Error: none

Historical results are descriptive. This comparison isolates proposer escalation under the same new runtime. Confidence is self-report, semantic audit is fallible, and unvisited alternatives remain untested. A reference-conflict flag requests review; it does not certify that the saved label is wrong.
