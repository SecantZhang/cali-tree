# Counting endpoint leaf experiment

Twelve previously observed local fitting cases, four per class. Repeats are within-case measurements. No held-out generalization or atomic correctness claim.

Status: completed

Semantic auditing is disabled. All independent required conditions pass → yes; all fail → no; mixed → partial; any unknown → unresolved. No model readout runs. The confidence/repeat gates still govern empirical robust status.
Agreement means reference matches; coverage means a resolved answer, including wrong answers. Each case has five fresh final draws. Missing or unresolved draws count as nonmatches; repeated draws are not additional cases. Both arms use the corrected runtime and strict gates.

| Arm | Seed → selected matches | Selected resolved | Locally robust cases | Escalated cases |
|---|---:|---:|---:|---:|
| luna_only | 29 → 52 / 60 | 58 / 60 | 8 / 12 | 0 / 12 |
| luna_then_sol | 30 → 42 / 60 | 58 / 60 | 6 / 12 | 4 / 12 |

Accurate and repeatable means **all five selected final labels match the reference**, with all five resolved.
Raw means the scheduled observations before recovery. Effective permits one predeclared transport-only replacement check per report; valid wrong/uncertain/schema-invalid observations are never replaced.

| Method | Raw accurate and repeatable cases | Effective accurate and repeatable cases |
|---|---:|---:|
| luna_only | 7 / 12 | 8 / 12 |
| luna_then_sol | 5 / 12 | 6 / 12 |

| Instruction / reference | Arm | Seed → selected matches / 5 | Resolved / 5 | Mean executed checks | Confidence gate | Status / failure reason |
|---|---|---:|---:|---:|---|---|
| transform the black DVD into a white DVD / no | luna_only | 0 → 5 | 5 | 1.0 | passed | locally_robust;  |
| transform the black DVD into a white DVD / no | luna_then_sol | 0 → 0 | 5 | 1.0 | passed | stable_but_mismatched; target_mismatch, confirmation_missing_or_unqualified |
| Make her close her jacket fully / yes | luna_only | 0 → 0 | 5 | 1.0 | passed | stable_but_mismatched; target_mismatch, confirmation_missing_or_unqualified |
| Make her close her jacket fully / yes | luna_then_sol | 0 → 0 | 5 | 1.0 | passed | stable_but_mismatched; target_mismatch, confirmation_missing_or_unqualified |
| Change the image into pencil drawing / partial | luna_only | 4 → 5 | 5 | 2.0 | passed | locally_robust;  |
| Change the image into pencil drawing / partial | luna_then_sol | 5 → 4 | 4 | 2.0 | failed/unavailable | unresolved; unresolved, target_mismatch, confidence |
| Give the woman a helmet / yes | luna_only | 5 → 5 | 5 | 1.0 | passed | locally_robust;  |
| Give the woman a helmet / yes | luna_then_sol | 5 → 5 | 5 | 1.0 | passed | locally_robust;  |
| Change the background into a basketball court / yes | luna_only | 5 → 4 | 5 | 1.0 | passed | unstable_and_mismatched; target_mismatch |
| Change the background into a basketball court / yes | luna_then_sol | 4 → 4 | 5 | 1.0 | passed | unstable_and_mismatched; target_mismatch, confirmation_missing_or_unqualified |
| Move the mug to the right of the headphones / partial | luna_only | 0 → 5 | 5 | 3.0 | passed | locally_robust;  |
| Move the mug to the right of the headphones / partial | luna_then_sol | 0 → 5 | 5 | 2.0 | passed | locally_robust;  |
| Move the book behind the flower / no | luna_only | 5 → 5 | 5 | 1.0 | passed | locally_robust;  |
| Move the book behind the flower / no | luna_then_sol | 5 → 5 | 5 | 1.0 | passed | locally_robust;  |
| Stuffing the paper into the cup / no | luna_only | 5 → 5 | 5 | 1.0 | passed | locally_robust;  |
| Stuffing the paper into the cup / no | luna_then_sol | 5 → 5 | 5 | 1.0 | passed | locally_robust;  |
| Make this look like a comic book photo / no | luna_only | 0 → 5 | 5 | 2.0 | passed | locally_robust;  |
| Make this look like a comic book photo / no | luna_then_sol | 0 → 5 | 5 | 2.0 | passed | locally_robust;  |
| Turn the image into a drawing made from chalk / partial | luna_only | 0 → 4 | 4 | 4.0 | failed/unavailable | unresolved; unresolved, target_mismatch, confidence |
| Turn the image into a drawing made from chalk / partial | luna_then_sol | 1 → 4 | 4 | 3.0 | failed/unavailable | unresolved; unresolved, target_mismatch, node_instability:d1, confidence |
| Put a frog in the toilet / partial | luna_only | 0 → 4 | 4 | 4.0 | failed/unavailable | unresolved; unresolved, target_mismatch, confidence |
| Put a frog in the toilet / partial | luna_then_sol | 0 → 0 | 5 | 1.0 | passed | stable_but_mismatched; target_mismatch, confirmation_missing_or_unqualified |
| the small gray rubber cylinder becomes brown / yes | luna_only | 5 → 5 | 5 | 2.0 | passed | locally_robust;  |
| the small gray rubber cylinder becomes brown / yes | luna_then_sol | 5 → 5 | 5 | 1.0 | passed | locally_robust;  |

## Per-case execution details

Consistency is measured separately from reference agreement. An uncertain answer can repeat consistently yet fail the known-answer stability gate. Skipped checks remain untested. The observation counts below count checks across five runs, not independent cases.

### transform the black DVD into a white DVD — luna_only

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 0.00 | 5.00 |
| Resolved draws / 5 | 5.00 | 5.00 |
| Final-label consistency | 1.00 | 1.00 |
| Minimum requirement consistency | 1.00 | 1.00 |
| Mean executed checks | 1.00 | 1.00 |
| Mean charged completion tokens | 59.00 | 85.80 |

Seed labels: {"yes": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.91, 0.91, 0.96, 0.96, 0.94]}.
Known-answer consistency per check: {"d1": 1.0}.

Selected labels: {"no": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.94, 0.96, 0.91, 0.91, 0.91]}.
Known-answer consistency per check: {"d1": 1.0}.

Search schedule: {"rounds_started": 1, "rounds_completed": 1, "max_rounds": 15}. Stop: confirmation_qualified.
Escalated: False. Usage: {"search": 10, "final": 10, "completion_tokens_or_reserved": 1992, "input_tokens": 27104}.

### transform the black DVD into a white DVD — luna_then_sol

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 0.00 | 0.00 |
| Resolved draws / 5 | 5.00 | 5.00 |
| Final-label consistency | 1.00 | 1.00 |
| Minimum requirement consistency | 1.00 | 1.00 |
| Mean executed checks | 1.00 | 1.00 |
| Mean charged completion tokens | 59.40 | 54.60 |

Seed labels: {"yes": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.94, 0.96, 0.96, 0.98, 0.94]}.
Known-answer consistency per check: {"d1": 1.0}.

Selected labels: {"yes": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.96, 0.98, 0.98, 0.96, 0.98]}.
Known-answer consistency per check: {"d1": 1.0}.

Search schedule: {"rounds_started": 15, "rounds_completed": 15, "max_rounds": 15}. Stop: round_limit.
Escalated: True. Usage: {"search": 58, "final": 10, "completion_tokens_or_reserved": 9724, "input_tokens": 208900}.

### Make her close her jacket fully — luna_only

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 0.00 | 0.00 |
| Resolved draws / 5 | 5.00 | 5.00 |
| Final-label consistency | 1.00 | 1.00 |
| Minimum requirement consistency | 1.00 | 1.00 |
| Mean executed checks | 1.00 | 1.00 |
| Mean charged completion tokens | 65.80 | 64.20 |

Seed labels: {"no": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.98, 0.98, 0.98, 0.98, 0.98]}.
Known-answer consistency per check: {"d1": 1.0}.

Selected labels: {"no": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.99, 0.99, 0.99, 0.98, 0.98]}.
Known-answer consistency per check: {"d1": 1.0}.

Search schedule: {"rounds_started": 15, "rounds_completed": 14, "max_rounds": 15}. Stop: round_limit.
Escalated: False. Usage: {"search": 49, "final": 10, "completion_tokens_or_reserved": 9749, "input_tokens": 131489}.

### Make her close her jacket fully — luna_then_sol

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 0.00 | 0.00 |
| Resolved draws / 5 | 5.00 | 5.00 |
| Final-label consistency | 1.00 | 1.00 |
| Minimum requirement consistency | 1.00 | 1.00 |
| Mean executed checks | 1.00 | 1.00 |
| Mean charged completion tokens | 64.20 | 64.40 |

Seed labels: {"no": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.98, 0.99, 0.98, 0.98, 0.98]}.
Known-answer consistency per check: {"d1": 1.0}.

Selected labels: {"no": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.99, 0.99, 0.98, 0.98, 0.98]}.
Known-answer consistency per check: {"d1": 1.0}.

Search schedule: {"rounds_started": 15, "rounds_completed": 15, "max_rounds": 15}. Stop: round_limit.
Escalated: True. Usage: {"search": 49, "final": 10, "completion_tokens_or_reserved": 5185, "input_tokens": 125509}.

### Change the image into pencil drawing — luna_only

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 4.00 | 5.00 |
| Resolved draws / 5 | 5.00 | 5.00 |
| Final-label consistency | 0.80 | 1.00 |
| Minimum requirement consistency | 0.80 | 1.00 |
| Mean executed checks | 2.00 | 2.00 |
| Mean charged completion tokens | 143.60 | 357.80 |

Seed labels: {"no": 1, "partial": 4}. Observation events: {"observed": 10}.
Confidence per check: {"d1": [0.94, 0.94, 0.94, 0.94, 0.94], "d2": [0.94, 0.91, 0.91, 0.91, 0.91]}.
Known-answer consistency per check: {"d1": 1.0, "d2": 0.8}.

Selected labels: {"partial": 5}. Observation events: {"observed": 10}.
Confidence per check: {"d1": [0.94, 0.94, 0.94, 0.94, 0.94], "d2": [0.91, 0.94, 0.91, 0.91, 0.91]}.
Known-answer consistency per check: {"d1": 1.0, "d2": 1.0}.

Search schedule: {"rounds_started": 0, "rounds_completed": 0, "max_rounds": 15}. Stop: confirmation_qualified.
Escalated: False. Usage: {"search": 12, "final": 21, "completion_tokens_or_reserved": 3411, "input_tokens": 34960}.

### Change the image into pencil drawing — luna_then_sol

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 5.00 | 4.00 |
| Resolved draws / 5 | 5.00 | 4.00 |
| Final-label consistency | 1.00 | 0.80 |
| Minimum requirement consistency | 1.00 | 0.80 |
| Mean executed checks | 2.00 | 2.00 |
| Mean charged completion tokens | 351.20 | 547.80 |

Seed labels: {"partial": 5}. Observation events: {"observed": 10}.
Confidence per check: {"d1": [0.96, 0.96, 0.94, 0.94, 0.94], "d2": [0.91, 0.91, 0.91, 0.91, 0.91]}.
Known-answer consistency per check: {"d1": 1.0, "d2": 1.0}.

Selected labels: {"partial": 4, "unresolved": 1}. Observation events: {"observed": 9, "transport_failure": 1}.
Confidence per check: {"d1": [0.94, null, 0.94, 0.94, 0.94], "d2": [0.91, 0.91, 0.94, 0.91, 0.91]}.
Known-answer consistency per check: {"d1": 0.8, "d2": 1.0}.

Search schedule: {"rounds_started": 0, "rounds_completed": 0, "max_rounds": 15}. Stop: confirmation_qualified.
Escalated: False. Usage: {"search": 12, "final": 22, "completion_tokens_or_reserved": 5364, "input_tokens": 33866}.

### Give the woman a helmet — luna_only

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 5.00 | 5.00 |
| Resolved draws / 5 | 5.00 | 5.00 |
| Final-label consistency | 1.00 | 1.00 |
| Minimum requirement consistency | 1.00 | 1.00 |
| Mean executed checks | 1.00 | 1.00 |
| Mean charged completion tokens | 53.40 | 53.60 |

Seed labels: {"yes": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.99, 0.99, 0.99, 0.99, 0.99]}.
Known-answer consistency per check: {"d1": 1.0}.

Selected labels: {"yes": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.99, 0.99, 0.99, 0.99, 0.99]}.
Known-answer consistency per check: {"d1": 1.0}.

Search schedule: {"rounds_started": 0, "rounds_completed": 0, "max_rounds": 15}. Stop: confirmation_qualified.
Escalated: False. Usage: {"search": 6, "final": 10, "completion_tokens_or_reserved": 860, "input_tokens": 31952}.

### Give the woman a helmet — luna_then_sol

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 5.00 | 5.00 |
| Resolved draws / 5 | 5.00 | 5.00 |
| Final-label consistency | 1.00 | 1.00 |
| Minimum requirement consistency | 1.00 | 1.00 |
| Mean executed checks | 1.00 | 1.00 |
| Mean charged completion tokens | 52.00 | 257.40 |

Seed labels: {"yes": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.99, 0.99, 0.99, 0.99, 0.99]}.
Known-answer consistency per check: {"d1": 1.0}.

Selected labels: {"yes": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.99, 0.99, 0.99, 0.99, 0.99]}.
Known-answer consistency per check: {"d1": 1.0}.

Search schedule: {"rounds_started": 0, "rounds_completed": 0, "max_rounds": 15}. Stop: confirmation_qualified.
Escalated: False. Usage: {"search": 6, "final": 11, "completion_tokens_or_reserved": 1862, "input_tokens": 31952}.

### Change the background into a basketball court — luna_only

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 5.00 | 4.00 |
| Resolved draws / 5 | 5.00 | 5.00 |
| Final-label consistency | 1.00 | 0.80 |
| Minimum requirement consistency | 1.00 | 0.80 |
| Mean executed checks | 1.00 | 1.00 |
| Mean charged completion tokens | 72.80 | 75.40 |

Seed labels: {"yes": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.99, 0.99, 0.99, 0.99, 0.99]}.
Known-answer consistency per check: {"d1": 1.0}.

Selected labels: {"yes": 4, "no": 1}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.99, 0.99, 0.91, 0.99, 0.99]}.
Known-answer consistency per check: {"d1": 0.8}.

Search schedule: {"rounds_started": 0, "rounds_completed": 0, "max_rounds": 15}. Stop: confirmation_qualified.
Escalated: False. Usage: {"search": 6, "final": 10, "completion_tokens_or_reserved": 1160, "input_tokens": 17168}.

### Change the background into a basketball court — luna_then_sol

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 4.00 | 4.00 |
| Resolved draws / 5 | 5.00 | 5.00 |
| Final-label consistency | 0.80 | 0.80 |
| Minimum requirement consistency | 0.80 | 0.80 |
| Mean executed checks | 1.00 | 1.00 |
| Mean charged completion tokens | 77.20 | 70.20 |

Seed labels: {"yes": 4, "no": 1}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.99, 0.99, 0.88, 0.99, 0.99]}.
Known-answer consistency per check: {"d1": 0.8}.

Selected labels: {"yes": 4, "no": 1}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.99, 0.99, 0.99, 0.99, 0.88]}.
Known-answer consistency per check: {"d1": 0.8}.

Search schedule: {"rounds_started": 15, "rounds_completed": 14, "max_rounds": 15}. Stop: round_limit.
Escalated: True. Usage: {"search": 53, "final": 10, "completion_tokens_or_reserved": 8742, "input_tokens": 212123}.

### Move the mug to the right of the headphones — luna_only

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 0.00 | 5.00 |
| Resolved draws / 5 | 5.00 | 5.00 |
| Final-label consistency | 1.00 | 1.00 |
| Minimum requirement consistency | 1.00 | 1.00 |
| Mean executed checks | 1.00 | 3.00 |
| Mean charged completion tokens | 66.40 | 230.20 |

Seed labels: {"yes": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.98, 0.91, 0.96, 0.98, 0.98]}.
Known-answer consistency per check: {"d1": 1.0}.

Selected labels: {"partial": 5}. Observation events: {"observed": 15}.
Confidence per check: {"d1a": [0.94, 0.94, 0.96, 0.94, 0.94], "d1b": [0.98, 0.94, 0.96, 0.97, 0.96], "d2a": [0.98, 0.98, 0.98, 0.99, 0.99]}.
Known-answer consistency per check: {"d1a": 1.0, "d1b": 1.0, "d2a": 1.0}.

Search schedule: {"rounds_started": 2, "rounds_completed": 2, "max_rounds": 15}. Stop: confirmation_qualified.
Escalated: False. Usage: {"search": 28, "final": 20, "completion_tokens_or_reserved": 5279, "input_tokens": 117573}.

### Move the mug to the right of the headphones — luna_then_sol

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 0.00 | 5.00 |
| Resolved draws / 5 | 5.00 | 5.00 |
| Final-label consistency | 1.00 | 1.00 |
| Minimum requirement consistency | 1.00 | 1.00 |
| Mean executed checks | 1.00 | 2.00 |
| Mean charged completion tokens | 64.60 | 121.40 |

Seed labels: {"yes": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.91, 0.99, 0.98, 0.91, 0.91]}.
Known-answer consistency per check: {"d1": 1.0}.

Selected labels: {"partial": 5}. Observation events: {"observed": 10}.
Confidence per check: {"d1a": [0.98, 0.97, 0.97, 0.97, 0.97], "d1b": [0.99, 0.99, 0.99, 0.99, 0.99]}.
Known-answer consistency per check: {"d1a": 1.0, "d1b": 1.0}.

Search schedule: {"rounds_started": 1, "rounds_completed": 1, "max_rounds": 15}. Stop: confirmation_qualified.
Escalated: False. Usage: {"search": 16, "final": 15, "completion_tokens_or_reserved": 2855, "input_tokens": 72370}.

### Move the book behind the flower — luna_only

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 5.00 | 5.00 |
| Resolved draws / 5 | 5.00 | 5.00 |
| Final-label consistency | 1.00 | 1.00 |
| Minimum requirement consistency | 1.00 | 1.00 |
| Mean executed checks | 1.00 | 1.00 |
| Mean charged completion tokens | 74.00 | 81.80 |

Seed labels: {"no": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.99, 0.99, 0.99, 0.99, 0.99]}.
Known-answer consistency per check: {"d1": 1.0}.

Selected labels: {"no": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.99, 0.99, 0.99, 0.99, 0.99]}.
Known-answer consistency per check: {"d1": 1.0}.

Search schedule: {"rounds_started": 0, "rounds_completed": 0, "max_rounds": 15}. Stop: confirmation_qualified.
Escalated: False. Usage: {"search": 6, "final": 10, "completion_tokens_or_reserved": 1186, "input_tokens": 34576}.

### Move the book behind the flower — luna_then_sol

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 5.00 | 5.00 |
| Resolved draws / 5 | 5.00 | 5.00 |
| Final-label consistency | 1.00 | 1.00 |
| Minimum requirement consistency | 1.00 | 1.00 |
| Mean executed checks | 1.00 | 1.00 |
| Mean charged completion tokens | 69.00 | 65.80 |

Seed labels: {"no": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.99, 0.99, 0.99, 0.99, 0.99]}.
Known-answer consistency per check: {"d1": 1.0}.

Selected labels: {"no": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.99, 0.99, 0.99, 0.99, 0.99]}.
Known-answer consistency per check: {"d1": 1.0}.

Search schedule: {"rounds_started": 0, "rounds_completed": 0, "max_rounds": 15}. Stop: confirmation_qualified.
Escalated: False. Usage: {"search": 6, "final": 10, "completion_tokens_or_reserved": 1093, "input_tokens": 34576}.

### Stuffing the paper into the cup — luna_only

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 5.00 | 5.00 |
| Resolved draws / 5 | 5.00 | 5.00 |
| Final-label consistency | 1.00 | 1.00 |
| Minimum requirement consistency | 1.00 | 1.00 |
| Mean executed checks | 1.00 | 1.00 |
| Mean charged completion tokens | 71.40 | 67.80 |

Seed labels: {"no": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.98, 0.99, 0.98, 0.99, 0.99]}.
Known-answer consistency per check: {"d1": 1.0}.

Selected labels: {"no": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.99, 0.98, 0.99, 0.99, 0.99]}.
Known-answer consistency per check: {"d1": 1.0}.

Search schedule: {"rounds_started": 0, "rounds_completed": 0, "max_rounds": 15}. Stop: confirmation_qualified.
Escalated: False. Usage: {"search": 6, "final": 10, "completion_tokens_or_reserved": 1104, "input_tokens": 11856}.

### Stuffing the paper into the cup — luna_then_sol

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 5.00 | 5.00 |
| Resolved draws / 5 | 5.00 | 5.00 |
| Final-label consistency | 1.00 | 1.00 |
| Minimum requirement consistency | 1.00 | 1.00 |
| Mean executed checks | 1.00 | 1.00 |
| Mean charged completion tokens | 70.60 | 71.00 |

Seed labels: {"no": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.99, 0.99, 0.99, 0.99, 0.99]}.
Known-answer consistency per check: {"d1": 1.0}.

Selected labels: {"no": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.99, 0.99, 0.98, 0.99, 0.99]}.
Known-answer consistency per check: {"d1": 1.0}.

Search schedule: {"rounds_started": 0, "rounds_completed": 0, "max_rounds": 15}. Stop: confirmation_qualified.
Escalated: False. Usage: {"search": 6, "final": 10, "completion_tokens_or_reserved": 1117, "input_tokens": 11856}.

### Make this look like a comic book photo — luna_only

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 0.00 | 5.00 |
| Resolved draws / 5 | 5.00 | 5.00 |
| Final-label consistency | 1.00 | 1.00 |
| Minimum requirement consistency | 1.00 | 1.00 |
| Mean executed checks | 2.00 | 2.00 |
| Mean charged completion tokens | 135.80 | 133.20 |

Seed labels: {"partial": 5}. Observation events: {"observed": 10}.
Confidence per check: {"d1": [0.96, 0.94, 0.96, 0.94, 0.94], "d2": [0.94, 0.94, 0.94, 0.94, 0.94]}.
Known-answer consistency per check: {"d1": 1.0, "d2": 1.0}.

Selected labels: {"no": 5}. Observation events: {"observed": 10}.
Confidence per check: {"d1": [0.96, 0.94, 0.94, 0.94, 0.94], "d2": [0.91, 0.94, 0.91, 0.94, 0.91]}.
Known-answer consistency per check: {"d1": 1.0, "d2": 1.0}.

Search schedule: {"rounds_started": 10, "rounds_completed": 9, "max_rounds": 15}. Stop: confirmation_qualified.
Escalated: False. Usage: {"search": 57, "final": 20, "completion_tokens_or_reserved": 9948, "input_tokens": 150432}.

### Make this look like a comic book photo — luna_then_sol

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 0.00 | 5.00 |
| Resolved draws / 5 | 5.00 | 5.00 |
| Final-label consistency | 1.00 | 1.00 |
| Minimum requirement consistency | 1.00 | 1.00 |
| Mean executed checks | 2.00 | 2.00 |
| Mean charged completion tokens | 137.00 | 133.80 |

Seed labels: {"partial": 5}. Observation events: {"observed": 10}.
Confidence per check: {"d1": [0.94, 0.94, 0.94, 0.94, 0.94], "d2": [0.94, 0.94, 0.97, 0.94, 0.94]}.
Known-answer consistency per check: {"d1": 1.0, "d2": 1.0}.

Selected labels: {"no": 5}. Observation events: {"observed": 10}.
Confidence per check: {"d1": [0.94, 0.94, 0.94, 0.94, 0.94], "d2": [0.94, 0.94, 0.96, 0.94, 0.94]}.
Known-answer consistency per check: {"d1": 1.0, "d2": 1.0}.

Search schedule: {"rounds_started": 1, "rounds_completed": 0, "max_rounds": 15}. Stop: confirmation_qualified.
Escalated: False. Usage: {"search": 19, "final": 20, "completion_tokens_or_reserved": 4125, "input_tokens": 47193}.

### Turn the image into a drawing made from chalk — luna_only

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 0.00 | 4.00 |
| Resolved draws / 5 | 5.00 | 4.00 |
| Final-label consistency | 1.00 | 0.80 |
| Minimum requirement consistency | 1.00 | 0.80 |
| Mean executed checks | 2.00 | 4.00 |
| Mean charged completion tokens | 148.40 | 685.80 |

Seed labels: {"yes": 5}. Observation events: {"observed": 10}.
Confidence per check: {"d1": [0.96, 0.94, 0.94, 0.96, 0.97], "d2": [0.94, 0.91, 0.94, 0.91, 0.94]}.
Known-answer consistency per check: {"d1": 1.0, "d2": 1.0}.

Selected labels: {"partial": 4, "unresolved": 1}. Observation events: {"observed": 19, "transport_failure": 1}.
Confidence per check: {"d1_subjects": [0.94, 0.94, 0.94, 0.94, 0.94], "d1_scene": [0.96, 0.96, 0.94, 0.96, 0.94], "d2": [0.91, 0.88, 0.91, 0.91, 0.91], "d3_coherent_drawing": [0.94, 0.94, 0.94, null, 0.94]}.
Known-answer consistency per check: {"d1_subjects": 1.0, "d1_scene": 1.0, "d2": 1.0, "d3_coherent_drawing": 0.8}.

Search schedule: {"rounds_started": 14, "rounds_completed": 11, "max_rounds": 15}. Stop: confirmation_qualified.
Escalated: False. Usage: {"search": 91, "final": 31, "completion_tokens_or_reserved": 20941, "input_tokens": 233402}.

### Turn the image into a drawing made from chalk — luna_then_sol

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 1.00 | 4.00 |
| Resolved draws / 5 | 5.00 | 4.00 |
| Final-label consistency | 0.80 | 0.80 |
| Minimum requirement consistency | 0.80 | 0.80 |
| Mean executed checks | 2.00 | 3.00 |
| Mean charged completion tokens | 150.00 | 611.20 |

Seed labels: {"partial": 1, "yes": 4}. Observation events: {"observed": 10}.
Confidence per check: {"d1": [0.94, 0.94, 0.94, 0.94, 0.94], "d2": [0.91, 0.91, 0.91, 0.91, 0.91]}.
Known-answer consistency per check: {"d1": 0.8, "d2": 1.0}.

Selected labels: {"partial": 4, "unresolved": 1}. Observation events: {"observed": 14, "transport_failure": 1}.
Confidence per check: {"d1": [0.94, 0.94, 0.94, 0.94, 0.94], "d2": [0.91, 0.91, null, 0.91, 0.91], "d3": [0.94, 0.94, 0.94, 0.94, 0.94]}.
Known-answer consistency per check: {"d1": 0.6, "d2": 0.8, "d3": 1.0}.

Search schedule: {"rounds_started": 3, "rounds_completed": 2, "max_rounds": 15}. Stop: confirmation_qualified.
Escalated: False. Usage: {"search": 47, "final": 26, "completion_tokens_or_reserved": 12101, "input_tokens": 108824}.

### Put a frog in the toilet — luna_only

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 0.00 | 4.00 |
| Resolved draws / 5 | 5.00 | 4.00 |
| Final-label consistency | 1.00 | 0.80 |
| Minimum requirement consistency | 1.00 | 0.80 |
| Mean executed checks | 1.00 | 4.00 |
| Mean charged completion tokens | 53.60 | 661.20 |

Seed labels: {"yes": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.99, 0.99, 0.99, 0.99, 0.99]}.
Known-answer consistency per check: {"d1": 1.0}.

Selected labels: {"partial": 4, "unresolved": 1}. Observation events: {"observed": 19, "transport_failure": 1}.
Confidence per check: {"d1_identity": [0.99, 0.99, 0.99, 0.99, 0.99], "d1_bowl_location": [0.99, 0.99, 0.99, 0.99, 0.99], "d1_bowl_occupancy": [0.97, 0.98, 0.96, null, 0.96], "d1_no_frogs_outside_toilet": [0.99, 0.99, 0.99, 0.99, 0.99]}.
Known-answer consistency per check: {"d1_identity": 1.0, "d1_bowl_location": 1.0, "d1_bowl_occupancy": 0.8, "d1_no_frogs_outside_toilet": 1.0}.

Search schedule: {"rounds_started": 7, "rounds_completed": 5, "max_rounds": 15}. Stop: confirmation_qualified.
Escalated: False. Usage: {"search": 86, "final": 26, "completion_tokens_or_reserved": 18498, "input_tokens": 400525}.

### Put a frog in the toilet — luna_then_sol

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 0.00 | 0.00 |
| Resolved draws / 5 | 5.00 | 5.00 |
| Final-label consistency | 1.00 | 1.00 |
| Minimum requirement consistency | 1.00 | 1.00 |
| Mean executed checks | 1.00 | 1.00 |
| Mean charged completion tokens | 54.80 | 55.80 |

Seed labels: {"yes": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.99, 0.99, 0.99, 0.99, 0.99]}.
Known-answer consistency per check: {"d1": 1.0}.

Selected labels: {"yes": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.99, 0.99, 0.99, 0.99, 0.99]}.
Known-answer consistency per check: {"d1": 1.0}.

Search schedule: {"rounds_started": 15, "rounds_completed": 13, "max_rounds": 15}. Stop: round_limit.
Escalated: True. Usage: {"search": 48, "final": 10, "completion_tokens_or_reserved": 11862, "input_tokens": 233992}.

### the small gray rubber cylinder becomes brown — luna_only

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 5.00 | 5.00 |
| Resolved draws / 5 | 5.00 | 5.00 |
| Final-label consistency | 1.00 | 1.00 |
| Minimum requirement consistency | 1.00 | 1.00 |
| Mean executed checks | 1.00 | 2.00 |
| Mean charged completion tokens | 49.20 | 119.20 |

Seed labels: {"yes": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.98, 0.98, 0.98, 0.98, 0.98]}.
Known-answer consistency per check: {"d1": 1.0}.

Selected labels: {"yes": 5}. Observation events: {"observed": 10}.
Confidence per check: {"d1_color": [0.98, 0.98, 0.98, 0.98, 0.98], "d1_identity": [0.96, 0.97, 0.96, 0.97, 0.96]}.
Known-answer consistency per check: {"d1_color": 1.0, "d1_identity": 1.0}.

Search schedule: {"rounds_started": 1, "rounds_completed": 1, "max_rounds": 15}. Stop: confirmation_qualified.
Escalated: False. Usage: {"search": 21, "final": 15, "completion_tokens_or_reserved": 2999, "input_tokens": 42674}.

### the small gray rubber cylinder becomes brown — luna_then_sol

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 5.00 | 5.00 |
| Resolved draws / 5 | 5.00 | 5.00 |
| Final-label consistency | 1.00 | 1.00 |
| Minimum requirement consistency | 1.00 | 1.00 |
| Mean executed checks | 1.00 | 1.00 |
| Mean charged completion tokens | 51.40 | 58.20 |

Seed labels: {"yes": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.98, 0.98, 0.98, 0.98, 0.98]}.
Known-answer consistency per check: {"d1": 1.0}.

Selected labels: {"yes": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.99, 0.99, 0.99, 0.99, 0.99]}.
Known-answer consistency per check: {"d1": 1.0}.

Search schedule: {"rounds_started": 1, "rounds_completed": 1, "max_rounds": 15}. Stop: confirmation_qualified.
Escalated: False. Usage: {"search": 10, "final": 10, "completion_tokens_or_reserved": 1859, "input_tokens": 23863}.

## Accounting

{
  "calls": 1077,
  "completion_tokens_or_reserved": 146232,
  "input_tokens": 2387251,
  "consecutive_errors": 0,
  "stopped": null,
  "final_calls": 357,
  "final_tokens": 34612
}

Returned models: gpt-6-luna, gpt-6.1-sol
Error: none

Historical results are descriptive. This comparison isolates proposer escalation under the same new runtime. Confidence is self-report, semantic audit is fallible, and unvisited alternatives remain untested. A reference-conflict flag requests review; it does not certify that the saved label is wrong.
