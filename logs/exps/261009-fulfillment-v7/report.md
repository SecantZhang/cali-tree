# Weighted fulfillment versus binary comparison

Twelve previously observed local fitting cases, four per class. Repeats are within-case measurements. No held-out generalization or atomic correctness claim.

Status: completed

Both arms use the same label-blind anchored grading calls on fresh independently observed programs. Fulfillment measures degree, not confidence. Protected weighted mean: >=.9 yes, <=.1 no, otherwise partial. Unknown mass is [0,1]; resolve only when the entire score interval has one label. Binary derives strict complete (score 1) votes and uses all/some/none. Audit/readout disabled. The historical v6 boolean observer differs; this fresh pair isolates aggregation under a common graded observer.
Agreement means reference matches; coverage means a resolved answer, including wrong answers. Each case has five fresh final draws. Missing or unresolved draws count as nonmatches; repeated draws are not additional cases. Both arms use the corrected runtime and strict gates.

| Arm | Seed → selected matches | Selected resolved | Locally robust cases | Escalated cases |
|---|---:|---:|---:|---:|
| binary | 27 → 35 / 60 | 60 / 60 | 7 / 12 | 0 / 12 |
| fulfillment | 30 → 48 / 60 | 59 / 60 | 8 / 12 | 0 / 12 |

Accurate and repeatable means **all five selected final labels match the reference**, with all five resolved.
Raw means the scheduled observations before recovery. Effective permits one predeclared transport-only replacement check per report; valid wrong/uncertain/schema-invalid observations are never replaced.

| Method | Raw accurate and repeatable cases | Effective accurate and repeatable cases |
|---|---:|---:|
| binary | 5 / 12 | 7 / 12 |
| fulfillment | 6 / 12 | 8 / 12 |

| Instruction / reference | Arm | Seed → selected matches / 5 | Resolved / 5 | Mean executed checks | Confidence gate | Status / failure reason |
|---|---|---:|---:|---:|---|---|
| transform the black DVD into a white DVD / no | binary | 2 → 5 | 5 | 2.0 | passed | locally_robust;  |
| transform the black DVD into a white DVD / no | fulfillment | 0 → 5 | 5 | 2.0 | passed | locally_robust;  |
| Make her close her jacket fully / yes | binary | 0 → 0 | 5 | 1.0 | passed | stable_but_mismatched; target_mismatch, confirmation_missing_or_unqualified |
| Make her close her jacket fully / yes | fulfillment | 0 → 0 | 5 | 1.0 | passed | stable_but_mismatched; target_mismatch, confirmation_missing_or_unqualified |
| Change the image into pencil drawing / partial | binary | 0 → 0 | 5 | 1.0 | passed | unstable_and_mismatched; target_mismatch, confirmation_missing_or_unqualified |
| Change the image into pencil drawing / partial | fulfillment | 5 → 4 | 5 | 1.0 | passed | unstable_and_mismatched; target_mismatch |
| Give the woman a helmet / yes | binary | 5 → 5 | 5 | 1.0 | passed | locally_robust;  |
| Give the woman a helmet / yes | fulfillment | 5 → 5 | 5 | 1.0 | passed | locally_robust;  |
| Change the background into a basketball court / yes | binary | 0 → 5 | 5 | 1.0 | passed | locally_robust;  |
| Change the background into a basketball court / yes | fulfillment | 0 → 5 | 5 | 1.0 | passed | locally_robust;  |
| Move the mug to the right of the headphones / partial | binary | 0 → 0 | 5 | 1.0 | passed | stable_but_mismatched; target_mismatch, confirmation_missing_or_unqualified |
| Move the mug to the right of the headphones / partial | fulfillment | 0 → 5 | 5 | 1.0 | passed | locally_robust;  |
| Move the book behind the flower / no | binary | 5 → 5 | 5 | 1.0 | passed | locally_robust;  |
| Move the book behind the flower / no | fulfillment | 5 → 5 | 5 | 1.0 | passed | locally_robust;  |
| Stuffing the paper into the cup / no | binary | 5 → 5 | 5 | 1.0 | passed | locally_robust;  |
| Stuffing the paper into the cup / no | fulfillment | 5 → 5 | 5 | 1.0 | passed | locally_robust;  |
| Make this look like a comic book photo / no | binary | 5 → 5 | 5 | 2.0 | passed | locally_robust;  |
| Make this look like a comic book photo / no | fulfillment | 0 → 5 | 5 | 2.0 | passed | locally_robust;  |
| Turn the image into a drawing made from chalk / partial | binary | 0 → 0 | 5 | 1.0 | passed | stable_but_mismatched; target_mismatch, confirmation_missing_or_unqualified |
| Turn the image into a drawing made from chalk / partial | fulfillment | 5 → 4 | 4 | 1.0 | failed/unavailable | unresolved; unresolved, target_mismatch, confidence |
| Put a frog in the toilet / partial | binary | 0 → 0 | 5 | 1.0 | passed | stable_but_mismatched; target_mismatch, confirmation_missing_or_unqualified |
| Put a frog in the toilet / partial | fulfillment | 0 → 0 | 5 | 1.0 | passed | stable_but_mismatched; target_mismatch, confirmation_missing_or_unqualified |
| the small gray rubber cylinder becomes brown / yes | binary | 5 → 5 | 5 | 1.0 | passed | locally_robust;  |
| the small gray rubber cylinder becomes brown / yes | fulfillment | 5 → 5 | 5 | 1.0 | passed | locally_robust;  |

## Per-case execution details

Consistency is measured separately from reference agreement. An uncertain answer can repeat consistently yet fail the known-answer stability gate. Skipped checks remain untested. The observation counts below count checks across five runs, not independent cases.

### transform the black DVD into a white DVD — binary

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 2.00 | 5.00 |
| Resolved draws / 5 | 5.00 | 5.00 |
| Final-label consistency | 0.60 | 1.00 |
| Minimum requirement consistency | 0.60 | 1.00 |
| Mean executed checks | 2.00 | 2.00 |
| Mean charged completion tokens | 183.60 | 198.20 |

Seed labels: {"partial": 3, "no": 2}. Observation events: {"observed": 10}.
Confidence per check: {"d1": [0.88, 0.91, 0.72, 0.58, 0.91], "d2": [0.84, 0.88, 0.78, 0.84, 0.88]}.
Known-answer consistency per check: {"d1": 0.6, "d2": 1.0}.

Fulfillment score bounds: [{"lower": 0.625, "upper": 0.625, "score": 0.625, "binary_label": "partial", "fulfillment_label": "partial", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.75, "upper": 0.75, "score": 0.75, "binary_label": "partial", "fulfillment_label": "partial", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.5, "upper": 0.5, "score": 0.5, "binary_label": "no", "fulfillment_label": "partial", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.5, "upper": 0.5, "score": 0.5, "binary_label": "no", "fulfillment_label": "partial", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.75, "upper": 0.75, "score": 0.75, "binary_label": "partial", "fulfillment_label": "partial", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}].
Same-observation counterfactual agreement: {"binary": 0.4, "fulfillment": 0.0}.

Selected labels: {"no": 5}. Observation events: {"observed": 10}.
Confidence per check: {"d1": [0.98, 0.98, 0.98, 0.98, 0.98], "d2": [0.88, 0.91, 0.88, 0.91, 0.91]}.
Known-answer consistency per check: {"d1": 1.0, "d2": 1.0}.

Fulfillment score bounds: [{"lower": 0.25, "upper": 0.25, "score": 0.25, "binary_label": "no", "fulfillment_label": "partial", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.25, "upper": 0.25, "score": 0.25, "binary_label": "no", "fulfillment_label": "partial", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.25, "upper": 0.25, "score": 0.25, "binary_label": "no", "fulfillment_label": "partial", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.25, "upper": 0.25, "score": 0.25, "binary_label": "no", "fulfillment_label": "partial", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.25, "upper": 0.25, "score": 0.25, "binary_label": "no", "fulfillment_label": "partial", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}].
Same-observation counterfactual agreement: {"binary": 1.0, "fulfillment": 0.0}.

Search schedule: {"rounds_started": 1, "rounds_completed": 0, "max_rounds": 15}. Stop: confirmation_qualified.
Escalated: False. Usage: {"search": 19, "final": 20, "completion_tokens_or_reserved": 5746, "input_tokens": 57828}.

### transform the black DVD into a white DVD — fulfillment

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 0.00 | 5.00 |
| Resolved draws / 5 | 5.00 | 5.00 |
| Final-label consistency | 1.00 | 1.00 |
| Minimum requirement consistency | 1.00 | 1.00 |
| Mean executed checks | 2.00 | 2.00 |
| Mean charged completion tokens | 163.20 | 179.60 |

Seed labels: {"partial": 5}. Observation events: {"observed": 10}.
Confidence per check: {"d1": [0.72, 0.91, 0.91, 0.94, 0.91], "d2": [0.88, 0.88, 0.88, 0.91, 0.78]}.
Known-answer consistency per check: {"d1": 0.8, "d2": 1.0}.

Fulfillment score bounds: [{"lower": 0.5, "upper": 0.5, "score": 0.5, "binary_label": "no", "fulfillment_label": "partial", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.625, "upper": 0.625, "score": 0.625, "binary_label": "partial", "fulfillment_label": "partial", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.625, "upper": 0.625, "score": 0.625, "binary_label": "partial", "fulfillment_label": "partial", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.75, "upper": 0.75, "score": 0.75, "binary_label": "partial", "fulfillment_label": "partial", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.75, "upper": 0.75, "score": 0.75, "binary_label": "partial", "fulfillment_label": "partial", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}].
Same-observation counterfactual agreement: {"binary": 0.2, "fulfillment": 0.0}.

Selected labels: {"no": 5}. Observation events: {"observed": 10}.
Confidence per check: {"d1": [0.91, 0.94, 0.96, 0.91, 0.94], "d2": [0.98, 0.98, 0.98, 0.96, 0.98]}.
Known-answer consistency per check: {"d1": 1.0, "d2": 1.0}.

Fulfillment score bounds: [{"lower": 0.0, "upper": 0.0, "score": 0.0, "binary_label": "no", "fulfillment_label": "no", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.0, "upper": 0.0, "score": 0.0, "binary_label": "no", "fulfillment_label": "no", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.0, "upper": 0.0, "score": 0.0, "binary_label": "no", "fulfillment_label": "no", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.0, "upper": 0.0, "score": 0.0, "binary_label": "no", "fulfillment_label": "no", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.0, "upper": 0.0, "score": 0.0, "binary_label": "no", "fulfillment_label": "no", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}].
Same-observation counterfactual agreement: {"binary": 1.0, "fulfillment": 1.0}.

Search schedule: {"rounds_started": 2, "rounds_completed": 2, "max_rounds": 15}. Stop: confirmation_qualified.
Escalated: False. Usage: {"search": 24, "final": 20, "completion_tokens_or_reserved": 5103, "input_tokens": 73736}.

### Make her close her jacket fully — binary

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 0.00 | 0.00 |
| Resolved draws / 5 | 5.00 | 5.00 |
| Final-label consistency | 1.00 | 1.00 |
| Minimum requirement consistency | 1.00 | 1.00 |
| Mean executed checks | 1.00 | 1.00 |
| Mean charged completion tokens | 64.40 | 68.40 |

Seed labels: {"no": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.96, 0.94, 0.98, 0.98, 0.98]}.
Known-answer consistency per check: {"d1": 1.0}.

Fulfillment score bounds: [{"lower": 0.0, "upper": 0.0, "score": 0.0, "binary_label": "no", "fulfillment_label": "no", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.0, "upper": 0.0, "score": 0.0, "binary_label": "no", "fulfillment_label": "no", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.0, "upper": 0.0, "score": 0.0, "binary_label": "no", "fulfillment_label": "no", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.0, "upper": 0.0, "score": 0.0, "binary_label": "no", "fulfillment_label": "no", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.0, "upper": 0.0, "score": 0.0, "binary_label": "no", "fulfillment_label": "no", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}].
Same-observation counterfactual agreement: {"binary": 0.0, "fulfillment": 0.0}.

Selected labels: {"no": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.98, 0.98, 0.91, 0.91, 0.98]}.
Known-answer consistency per check: {"d1": 1.0}.

Fulfillment score bounds: [{"lower": 0.0, "upper": 0.0, "score": 0.0, "binary_label": "no", "fulfillment_label": "no", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.0, "upper": 0.0, "score": 0.0, "binary_label": "no", "fulfillment_label": "no", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.0, "upper": 0.0, "score": 0.0, "binary_label": "no", "fulfillment_label": "no", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.0, "upper": 0.0, "score": 0.0, "binary_label": "no", "fulfillment_label": "no", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.0, "upper": 0.0, "score": 0.0, "binary_label": "no", "fulfillment_label": "no", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}].
Same-observation counterfactual agreement: {"binary": 0.0, "fulfillment": 0.0}.

Search schedule: {"rounds_started": 15, "rounds_completed": 15, "max_rounds": 15}. Stop: round_limit.
Escalated: False. Usage: {"search": 54, "final": 10, "completion_tokens_or_reserved": 9268, "input_tokens": 162173}.

### Make her close her jacket fully — fulfillment

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 0.00 | 0.00 |
| Resolved draws / 5 | 5.00 | 5.00 |
| Final-label consistency | 1.00 | 1.00 |
| Minimum requirement consistency | 1.00 | 1.00 |
| Mean executed checks | 1.00 | 1.00 |
| Mean charged completion tokens | 66.20 | 65.80 |

Seed labels: {"no": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.98, 0.98, 0.98, 0.91, 0.91]}.
Known-answer consistency per check: {"d1": 1.0}.

Fulfillment score bounds: [{"lower": 0.0, "upper": 0.0, "score": 0.0, "binary_label": "no", "fulfillment_label": "no", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.0, "upper": 0.0, "score": 0.0, "binary_label": "no", "fulfillment_label": "no", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.0, "upper": 0.0, "score": 0.0, "binary_label": "no", "fulfillment_label": "no", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.0, "upper": 0.0, "score": 0.0, "binary_label": "no", "fulfillment_label": "no", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.0, "upper": 0.0, "score": 0.0, "binary_label": "no", "fulfillment_label": "no", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}].
Same-observation counterfactual agreement: {"binary": 0.0, "fulfillment": 0.0}.

Selected labels: {"no": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.96, 0.94, 0.96, 0.91, 0.98]}.
Known-answer consistency per check: {"d1": 1.0}.

Fulfillment score bounds: [{"lower": 0.0, "upper": 0.0, "score": 0.0, "binary_label": "no", "fulfillment_label": "no", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.0, "upper": 0.0, "score": 0.0, "binary_label": "no", "fulfillment_label": "no", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.0, "upper": 0.0, "score": 0.0, "binary_label": "no", "fulfillment_label": "no", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.0, "upper": 0.0, "score": 0.0, "binary_label": "no", "fulfillment_label": "no", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.0, "upper": 0.0, "score": 0.0, "binary_label": "no", "fulfillment_label": "no", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}].
Same-observation counterfactual agreement: {"binary": 0.0, "fulfillment": 0.0}.

Search schedule: {"rounds_started": 15, "rounds_completed": 14, "max_rounds": 15}. Stop: round_limit.
Escalated: False. Usage: {"search": 54, "final": 10, "completion_tokens_or_reserved": 13571, "input_tokens": 175012}.

### Change the image into pencil drawing — binary

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 0.00 | 0.00 |
| Resolved draws / 5 | 5.00 | 5.00 |
| Final-label consistency | 1.00 | 0.80 |
| Minimum requirement consistency | 1.00 | 0.80 |
| Mean executed checks | 1.00 | 1.00 |
| Mean charged completion tokens | 97.40 | 98.00 |

Seed labels: {"no": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.88, 0.91, 0.91, 0.88, 0.88]}.
Known-answer consistency per check: {"d1": 1.0}.

Fulfillment score bounds: [{"lower": 0.65, "upper": 0.65, "score": 0.65, "binary_label": "no", "fulfillment_label": "partial", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.85, "upper": 0.85, "score": 0.85, "binary_label": "no", "fulfillment_label": "partial", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.85, "upper": 0.85, "score": 0.85, "binary_label": "no", "fulfillment_label": "partial", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.75, "upper": 0.75, "score": 0.75, "binary_label": "no", "fulfillment_label": "partial", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.65, "upper": 0.65, "score": 0.65, "binary_label": "no", "fulfillment_label": "partial", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}].
Same-observation counterfactual agreement: {"binary": 0.0, "fulfillment": 1.0}.

Selected labels: {"no": 4, "yes": 1}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.88, 0.88, 0.91, 0.91, 0.94]}.
Known-answer consistency per check: {"d1": 0.8}.

Fulfillment score bounds: [{"lower": 0.65, "upper": 0.65, "score": 0.65, "binary_label": "no", "fulfillment_label": "partial", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.65, "upper": 0.65, "score": 0.65, "binary_label": "no", "fulfillment_label": "partial", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.85, "upper": 0.85, "score": 0.85, "binary_label": "no", "fulfillment_label": "partial", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.85, "upper": 0.85, "score": 0.85, "binary_label": "no", "fulfillment_label": "partial", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}].
Same-observation counterfactual agreement: {"binary": 0.0, "fulfillment": 0.8}.

Search schedule: {"rounds_started": 15, "rounds_completed": 10, "max_rounds": 15}. Stop: round_limit.
Escalated: False. Usage: {"search": 60, "final": 10, "completion_tokens_or_reserved": 28590, "input_tokens": 180989}.

### Change the image into pencil drawing — fulfillment

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 5.00 | 4.00 |
| Resolved draws / 5 | 5.00 | 5.00 |
| Final-label consistency | 1.00 | 0.80 |
| Minimum requirement consistency | 1.00 | 0.80 |
| Mean executed checks | 1.00 | 1.00 |
| Mean charged completion tokens | 302.60 | 92.80 |

Seed labels: {"partial": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.91, 0.88, 0.88, 0.91, 0.91]}.
Known-answer consistency per check: {"d1": 1.0}.

Fulfillment score bounds: [{"lower": 0.85, "upper": 0.85, "score": 0.85, "binary_label": "no", "fulfillment_label": "partial", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.65, "upper": 0.65, "score": 0.65, "binary_label": "no", "fulfillment_label": "partial", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.65, "upper": 0.65, "score": 0.65, "binary_label": "no", "fulfillment_label": "partial", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.85, "upper": 0.85, "score": 0.85, "binary_label": "no", "fulfillment_label": "partial", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.85, "upper": 0.85, "score": 0.85, "binary_label": "no", "fulfillment_label": "partial", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}].
Same-observation counterfactual agreement: {"binary": 0.0, "fulfillment": 1.0}.

Selected labels: {"partial": 4, "yes": 1}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.91, 0.88, 0.94, 0.91, 0.91]}.
Known-answer consistency per check: {"d1": 0.8}.

Fulfillment score bounds: [{"lower": 0.85, "upper": 0.85, "score": 0.85, "binary_label": "no", "fulfillment_label": "partial", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.65, "upper": 0.65, "score": 0.65, "binary_label": "no", "fulfillment_label": "partial", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.75, "upper": 0.75, "score": 0.75, "binary_label": "no", "fulfillment_label": "partial", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.85, "upper": 0.85, "score": 0.85, "binary_label": "no", "fulfillment_label": "partial", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}].
Same-observation counterfactual agreement: {"binary": 0.0, "fulfillment": 0.8}.

Search schedule: {"rounds_started": 0, "rounds_completed": 0, "max_rounds": 15}. Stop: confirmation_qualified.
Escalated: False. Usage: {"search": 6, "final": 11, "completion_tokens_or_reserved": 2568, "input_tokens": 19840}.

### Give the woman a helmet — binary

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 5.00 | 5.00 |
| Resolved draws / 5 | 5.00 | 5.00 |
| Final-label consistency | 1.00 | 1.00 |
| Minimum requirement consistency | 1.00 | 1.00 |
| Mean executed checks | 1.00 | 1.00 |
| Mean charged completion tokens | 51.80 | 53.80 |

Seed labels: {"yes": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.99, 0.99, 0.98, 0.98, 0.99]}.
Known-answer consistency per check: {"d1": 1.0}.

Fulfillment score bounds: [{"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}].
Same-observation counterfactual agreement: {"binary": 1.0, "fulfillment": 1.0}.

Selected labels: {"yes": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.99, 0.99, 0.99, 0.99, 0.99]}.
Known-answer consistency per check: {"d1": 1.0}.

Fulfillment score bounds: [{"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}].
Same-observation counterfactual agreement: {"binary": 1.0, "fulfillment": 1.0}.

Search schedule: {"rounds_started": 0, "rounds_completed": 0, "max_rounds": 15}. Stop: confirmation_qualified.
Escalated: False. Usage: {"search": 6, "final": 10, "completion_tokens_or_reserved": 842, "input_tokens": 34288}.

### Give the woman a helmet — fulfillment

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 5.00 | 5.00 |
| Resolved draws / 5 | 5.00 | 5.00 |
| Final-label consistency | 1.00 | 1.00 |
| Minimum requirement consistency | 1.00 | 1.00 |
| Mean executed checks | 1.00 | 1.00 |
| Mean charged completion tokens | 53.60 | 261.40 |

Seed labels: {"yes": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.99, 0.99, 0.98, 0.99, 0.99]}.
Known-answer consistency per check: {"d1": 1.0}.

Fulfillment score bounds: [{"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}].
Same-observation counterfactual agreement: {"binary": 1.0, "fulfillment": 1.0}.

Selected labels: {"yes": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.98, 0.98, 0.98, 0.99, 0.99]}.
Known-answer consistency per check: {"d1": 1.0}.

Fulfillment score bounds: [{"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}].
Same-observation counterfactual agreement: {"binary": 1.0, "fulfillment": 1.0}.

Search schedule: {"rounds_started": 0, "rounds_completed": 0, "max_rounds": 15}. Stop: confirmation_qualified.
Escalated: False. Usage: {"search": 6, "final": 11, "completion_tokens_or_reserved": 1889, "input_tokens": 34288}.

### Change the background into a basketball court — binary

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 0.00 | 5.00 |
| Resolved draws / 5 | 5.00 | 5.00 |
| Final-label consistency | 1.00 | 1.00 |
| Minimum requirement consistency | 1.00 | 1.00 |
| Mean executed checks | 1.00 | 1.00 |
| Mean charged completion tokens | 84.60 | 276.60 |

Seed labels: {"no": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.96, 0.96, 0.94, 0.94, 0.94]}.
Known-answer consistency per check: {"d1": 1.0}.

Fulfillment score bounds: [{"lower": 0.75, "upper": 0.75, "score": 0.75, "binary_label": "no", "fulfillment_label": "partial", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.75, "upper": 0.75, "score": 0.75, "binary_label": "no", "fulfillment_label": "partial", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.75, "upper": 0.75, "score": 0.75, "binary_label": "no", "fulfillment_label": "partial", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.75, "upper": 0.75, "score": 0.75, "binary_label": "no", "fulfillment_label": "partial", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.75, "upper": 0.75, "score": 0.75, "binary_label": "no", "fulfillment_label": "partial", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}].
Same-observation counterfactual agreement: {"binary": 0.0, "fulfillment": 0.0}.

Selected labels: {"yes": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.98, 0.98, 0.98, 0.98, 0.99]}.
Known-answer consistency per check: {"d1": 1.0}.

Fulfillment score bounds: [{"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}].
Same-observation counterfactual agreement: {"binary": 1.0, "fulfillment": 1.0}.

Search schedule: {"rounds_started": 1, "rounds_completed": 0, "max_rounds": 15}. Stop: confirmation_qualified.
Escalated: False. Usage: {"search": 11, "final": 11, "completion_tokens_or_reserved": 4302, "input_tokens": 31489}.

### Change the background into a basketball court — fulfillment

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 0.00 | 5.00 |
| Resolved draws / 5 | 5.00 | 5.00 |
| Final-label consistency | 1.00 | 1.00 |
| Minimum requirement consistency | 1.00 | 1.00 |
| Mean executed checks | 1.00 | 1.00 |
| Mean charged completion tokens | 81.40 | 72.20 |

Seed labels: {"partial": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.94, 0.94, 0.94, 0.94, 0.94]}.
Known-answer consistency per check: {"d1": 1.0}.

Fulfillment score bounds: [{"lower": 0.75, "upper": 0.75, "score": 0.75, "binary_label": "no", "fulfillment_label": "partial", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.75, "upper": 0.75, "score": 0.75, "binary_label": "no", "fulfillment_label": "partial", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.75, "upper": 0.75, "score": 0.75, "binary_label": "no", "fulfillment_label": "partial", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.75, "upper": 0.75, "score": 0.75, "binary_label": "no", "fulfillment_label": "partial", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.75, "upper": 0.75, "score": 0.75, "binary_label": "no", "fulfillment_label": "partial", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}].
Same-observation counterfactual agreement: {"binary": 0.0, "fulfillment": 0.0}.

Selected labels: {"yes": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.99, 0.99, 0.99, 0.99, 0.99]}.
Known-answer consistency per check: {"d1": 1.0}.

Fulfillment score bounds: [{"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}].
Same-observation counterfactual agreement: {"binary": 1.0, "fulfillment": 1.0}.

Search schedule: {"rounds_started": 2, "rounds_completed": 2, "max_rounds": 15}. Stop: confirmation_qualified.
Escalated: False. Usage: {"search": 19, "final": 10, "completion_tokens_or_reserved": 3708, "input_tokens": 57949}.

### Move the mug to the right of the headphones — binary

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 0.00 | 0.00 |
| Resolved draws / 5 | 5.00 | 5.00 |
| Final-label consistency | 1.00 | 1.00 |
| Minimum requirement consistency | 1.00 | 1.00 |
| Mean executed checks | 1.00 | 1.00 |
| Mean charged completion tokens | 63.00 | 63.00 |

Seed labels: {"yes": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.94, 0.94, 0.94, 0.94, 0.94]}.
Known-answer consistency per check: {"d1": 1.0}.

Fulfillment score bounds: [{"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}].
Same-observation counterfactual agreement: {"binary": 0.0, "fulfillment": 0.0}.

Selected labels: {"yes": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.94, 0.94, 0.94, 0.94, 0.94]}.
Known-answer consistency per check: {"d1": 1.0}.

Fulfillment score bounds: [{"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}].
Same-observation counterfactual agreement: {"binary": 0.0, "fulfillment": 0.0}.

Search schedule: {"rounds_started": 15, "rounds_completed": 15, "max_rounds": 15}. Stop: round_limit.
Escalated: False. Usage: {"search": 59, "final": 10, "completion_tokens_or_reserved": 20423, "input_tokens": 287616}.

### Move the mug to the right of the headphones — fulfillment

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 0.00 | 5.00 |
| Resolved draws / 5 | 5.00 | 5.00 |
| Final-label consistency | 1.00 | 1.00 |
| Minimum requirement consistency | 1.00 | 1.00 |
| Mean executed checks | 1.00 | 1.00 |
| Mean charged completion tokens | 61.60 | 130.20 |

Seed labels: {"yes": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.94, 0.98, 0.94, 0.94, 0.94]}.
Known-answer consistency per check: {"d1": 1.0}.

Fulfillment score bounds: [{"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}].
Same-observation counterfactual agreement: {"binary": 0.0, "fulfillment": 0.0}.

Selected labels: {"partial": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.88, 0.84, 0.84, 0.88, 0.91]}.
Known-answer consistency per check: {"d1": 1.0}.

Fulfillment score bounds: [{"lower": 0.5, "upper": 0.5, "score": 0.5, "binary_label": "no", "fulfillment_label": "partial", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.5, "upper": 0.5, "score": 0.5, "binary_label": "no", "fulfillment_label": "partial", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.5, "upper": 0.5, "score": 0.5, "binary_label": "no", "fulfillment_label": "partial", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.5, "upper": 0.5, "score": 0.5, "binary_label": "no", "fulfillment_label": "partial", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.5, "upper": 0.5, "score": 0.5, "binary_label": "no", "fulfillment_label": "partial", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}].
Same-observation counterfactual agreement: {"binary": 0.0, "fulfillment": 1.0}.

Search schedule: {"rounds_started": 4, "rounds_completed": 4, "max_rounds": 15}. Stop: confirmation_qualified.
Escalated: False. Usage: {"search": 22, "final": 10, "completion_tokens_or_reserved": 6489, "input_tokens": 103819}.

### Move the book behind the flower — binary

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 5.00 | 5.00 |
| Resolved draws / 5 | 5.00 | 5.00 |
| Final-label consistency | 1.00 | 1.00 |
| Minimum requirement consistency | 1.00 | 1.00 |
| Mean executed checks | 1.00 | 1.00 |
| Mean charged completion tokens | 79.40 | 78.00 |

Seed labels: {"no": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.94, 0.98, 0.98, 0.98, 0.98]}.
Known-answer consistency per check: {"d1": 1.0}.

Fulfillment score bounds: [{"lower": 0.0, "upper": 0.0, "score": 0.0, "binary_label": "no", "fulfillment_label": "no", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.0, "upper": 0.0, "score": 0.0, "binary_label": "no", "fulfillment_label": "no", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.0, "upper": 0.0, "score": 0.0, "binary_label": "no", "fulfillment_label": "no", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.0, "upper": 0.0, "score": 0.0, "binary_label": "no", "fulfillment_label": "no", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.0, "upper": 0.0, "score": 0.0, "binary_label": "no", "fulfillment_label": "no", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}].
Same-observation counterfactual agreement: {"binary": 1.0, "fulfillment": 1.0}.

Selected labels: {"no": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.98, 0.94, 0.98, 0.98, 0.98]}.
Known-answer consistency per check: {"d1": 1.0}.

Fulfillment score bounds: [{"lower": 0.0, "upper": 0.0, "score": 0.0, "binary_label": "no", "fulfillment_label": "no", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.0, "upper": 0.0, "score": 0.0, "binary_label": "no", "fulfillment_label": "no", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.0, "upper": 0.0, "score": 0.0, "binary_label": "no", "fulfillment_label": "no", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.0, "upper": 0.0, "score": 0.0, "binary_label": "no", "fulfillment_label": "no", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.0, "upper": 0.0, "score": 0.0, "binary_label": "no", "fulfillment_label": "no", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}].
Same-observation counterfactual agreement: {"binary": 1.0, "fulfillment": 1.0}.

Search schedule: {"rounds_started": 0, "rounds_completed": 0, "max_rounds": 15}. Stop: confirmation_qualified.
Escalated: False. Usage: {"search": 6, "final": 10, "completion_tokens_or_reserved": 1290, "input_tokens": 37088}.

### Move the book behind the flower — fulfillment

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 5.00 | 5.00 |
| Resolved draws / 5 | 5.00 | 5.00 |
| Final-label consistency | 1.00 | 1.00 |
| Minimum requirement consistency | 1.00 | 1.00 |
| Mean executed checks | 1.00 | 1.00 |
| Mean charged completion tokens | 80.40 | 82.40 |

Seed labels: {"no": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.98, 0.96, 0.98, 0.96, 0.98]}.
Known-answer consistency per check: {"d1": 1.0}.

Fulfillment score bounds: [{"lower": 0.0, "upper": 0.0, "score": 0.0, "binary_label": "no", "fulfillment_label": "no", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.0, "upper": 0.0, "score": 0.0, "binary_label": "no", "fulfillment_label": "no", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.0, "upper": 0.0, "score": 0.0, "binary_label": "no", "fulfillment_label": "no", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.0, "upper": 0.0, "score": 0.0, "binary_label": "no", "fulfillment_label": "no", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.0, "upper": 0.0, "score": 0.0, "binary_label": "no", "fulfillment_label": "no", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}].
Same-observation counterfactual agreement: {"binary": 1.0, "fulfillment": 1.0}.

Selected labels: {"no": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.98, 0.94, 0.98, 0.96, 0.98]}.
Known-answer consistency per check: {"d1": 1.0}.

Fulfillment score bounds: [{"lower": 0.0, "upper": 0.0, "score": 0.0, "binary_label": "no", "fulfillment_label": "no", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.0, "upper": 0.0, "score": 0.0, "binary_label": "no", "fulfillment_label": "no", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.0, "upper": 0.0, "score": 0.0, "binary_label": "no", "fulfillment_label": "no", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.0, "upper": 0.0, "score": 0.0, "binary_label": "no", "fulfillment_label": "no", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.0, "upper": 0.0, "score": 0.0, "binary_label": "no", "fulfillment_label": "no", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}].
Same-observation counterfactual agreement: {"binary": 1.0, "fulfillment": 1.0}.

Search schedule: {"rounds_started": 0, "rounds_completed": 0, "max_rounds": 15}. Stop: confirmation_qualified.
Escalated: False. Usage: {"search": 6, "final": 10, "completion_tokens_or_reserved": 1309, "input_tokens": 37088}.

### Stuffing the paper into the cup — binary

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 5.00 | 5.00 |
| Resolved draws / 5 | 5.00 | 5.00 |
| Final-label consistency | 1.00 | 1.00 |
| Minimum requirement consistency | 1.00 | 1.00 |
| Mean executed checks | 1.00 | 1.00 |
| Mean charged completion tokens | 74.60 | 72.20 |

Seed labels: {"no": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.99, 0.99, 0.99, 0.99, 0.99]}.
Known-answer consistency per check: {"d1": 1.0}.

Fulfillment score bounds: [{"lower": 0.0, "upper": 0.0, "score": 0.0, "binary_label": "no", "fulfillment_label": "no", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.0, "upper": 0.0, "score": 0.0, "binary_label": "no", "fulfillment_label": "no", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.0, "upper": 0.0, "score": 0.0, "binary_label": "no", "fulfillment_label": "no", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.0, "upper": 0.0, "score": 0.0, "binary_label": "no", "fulfillment_label": "no", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.0, "upper": 0.0, "score": 0.0, "binary_label": "no", "fulfillment_label": "no", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}].
Same-observation counterfactual agreement: {"binary": 1.0, "fulfillment": 1.0}.

Selected labels: {"no": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.99, 0.99, 0.99, 0.99, 0.98]}.
Known-answer consistency per check: {"d1": 1.0}.

Fulfillment score bounds: [{"lower": 0.0, "upper": 0.0, "score": 0.0, "binary_label": "no", "fulfillment_label": "no", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.0, "upper": 0.0, "score": 0.0, "binary_label": "no", "fulfillment_label": "no", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.0, "upper": 0.0, "score": 0.0, "binary_label": "no", "fulfillment_label": "no", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.0, "upper": 0.0, "score": 0.0, "binary_label": "no", "fulfillment_label": "no", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.0, "upper": 0.0, "score": 0.0, "binary_label": "no", "fulfillment_label": "no", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}].
Same-observation counterfactual agreement: {"binary": 1.0, "fulfillment": 1.0}.

Search schedule: {"rounds_started": 0, "rounds_completed": 0, "max_rounds": 15}. Stop: confirmation_qualified.
Escalated: False. Usage: {"search": 6, "final": 10, "completion_tokens_or_reserved": 1167, "input_tokens": 14416}.

### Stuffing the paper into the cup — fulfillment

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 5.00 | 5.00 |
| Resolved draws / 5 | 5.00 | 5.00 |
| Final-label consistency | 1.00 | 1.00 |
| Minimum requirement consistency | 1.00 | 1.00 |
| Mean executed checks | 1.00 | 1.00 |
| Mean charged completion tokens | 74.60 | 70.60 |

Seed labels: {"no": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.99, 0.99, 0.98, 0.99, 0.99]}.
Known-answer consistency per check: {"d1": 1.0}.

Fulfillment score bounds: [{"lower": 0.0, "upper": 0.0, "score": 0.0, "binary_label": "no", "fulfillment_label": "no", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.0, "upper": 0.0, "score": 0.0, "binary_label": "no", "fulfillment_label": "no", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.0, "upper": 0.0, "score": 0.0, "binary_label": "no", "fulfillment_label": "no", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.0, "upper": 0.0, "score": 0.0, "binary_label": "no", "fulfillment_label": "no", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.0, "upper": 0.0, "score": 0.0, "binary_label": "no", "fulfillment_label": "no", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}].
Same-observation counterfactual agreement: {"binary": 1.0, "fulfillment": 1.0}.

Selected labels: {"no": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.99, 0.99, 0.99, 0.99, 0.99]}.
Known-answer consistency per check: {"d1": 1.0}.

Fulfillment score bounds: [{"lower": 0.0, "upper": 0.0, "score": 0.0, "binary_label": "no", "fulfillment_label": "no", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.0, "upper": 0.0, "score": 0.0, "binary_label": "no", "fulfillment_label": "no", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.0, "upper": 0.0, "score": 0.0, "binary_label": "no", "fulfillment_label": "no", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.0, "upper": 0.0, "score": 0.0, "binary_label": "no", "fulfillment_label": "no", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.0, "upper": 0.0, "score": 0.0, "binary_label": "no", "fulfillment_label": "no", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}].
Same-observation counterfactual agreement: {"binary": 1.0, "fulfillment": 1.0}.

Search schedule: {"rounds_started": 0, "rounds_completed": 0, "max_rounds": 15}. Stop: confirmation_qualified.
Escalated: False. Usage: {"search": 6, "final": 10, "completion_tokens_or_reserved": 1165, "input_tokens": 14416}.

### Make this look like a comic book photo — binary

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 5.00 | 5.00 |
| Resolved draws / 5 | 5.00 | 5.00 |
| Final-label consistency | 1.00 | 1.00 |
| Minimum requirement consistency | 1.00 | 1.00 |
| Mean executed checks | 2.00 | 2.00 |
| Mean charged completion tokens | 156.80 | 359.80 |

Seed labels: {"no": 5}. Observation events: {"observed": 10}.
Confidence per check: {"d1": [0.97, 0.96, 0.96, 0.98, 0.97], "d2": [0.91, 0.94, 0.91, 0.91, 0.88]}.
Known-answer consistency per check: {"d1": 1.0, "d2": 1.0}.

Fulfillment score bounds: [{"lower": 0.175, "upper": 0.175, "score": 0.175, "binary_label": "no", "fulfillment_label": "partial", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.25, "upper": 0.25, "score": 0.25, "binary_label": "no", "fulfillment_label": "partial", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.25, "upper": 0.25, "score": 0.25, "binary_label": "no", "fulfillment_label": "partial", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.175, "upper": 0.175, "score": 0.175, "binary_label": "no", "fulfillment_label": "partial", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.175, "upper": 0.175, "score": 0.175, "binary_label": "no", "fulfillment_label": "partial", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}].
Same-observation counterfactual agreement: {"binary": 1.0, "fulfillment": 0.0}.

Selected labels: {"no": 5}. Observation events: {"observed": 10}.
Confidence per check: {"d1": [0.94, 0.98, 0.97, 0.96, 0.97], "d2": [0.88, 0.91, 0.91, 0.94, 0.91]}.
Known-answer consistency per check: {"d1": 1.0, "d2": 1.0}.

Fulfillment score bounds: [{"lower": 0.175, "upper": 0.175, "score": 0.175, "binary_label": "no", "fulfillment_label": "partial", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.175, "upper": 0.175, "score": 0.175, "binary_label": "no", "fulfillment_label": "partial", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.275, "upper": 0.275, "score": 0.275, "binary_label": "no", "fulfillment_label": "partial", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.25, "upper": 0.25, "score": 0.25, "binary_label": "no", "fulfillment_label": "partial", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.175, "upper": 0.175, "score": 0.175, "binary_label": "no", "fulfillment_label": "partial", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}].
Same-observation counterfactual agreement: {"binary": 1.0, "fulfillment": 0.0}.

Search schedule: {"rounds_started": 0, "rounds_completed": 0, "max_rounds": 15}. Stop: confirmation_qualified.
Escalated: False. Usage: {"search": 13, "final": 21, "completion_tokens_or_reserved": 4555, "input_tokens": 40480}.

### Make this look like a comic book photo — fulfillment

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 0.00 | 5.00 |
| Resolved draws / 5 | 5.00 | 5.00 |
| Final-label consistency | 1.00 | 1.00 |
| Minimum requirement consistency | 1.00 | 1.00 |
| Mean executed checks | 2.00 | 2.00 |
| Mean charged completion tokens | 368.00 | 150.00 |

Seed labels: {"partial": 5}. Observation events: {"observed": 10}.
Confidence per check: {"d1": [0.96, 0.98, 0.94, 0.96, 0.98], "d2": [0.91, 0.91, 0.94, 0.91, 0.88]}.
Known-answer consistency per check: {"d1": 1.0, "d2": 1.0}.

Fulfillment score bounds: [{"lower": 0.175, "upper": 0.175, "score": 0.175, "binary_label": "no", "fulfillment_label": "partial", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.175, "upper": 0.175, "score": 0.175, "binary_label": "no", "fulfillment_label": "partial", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.25, "upper": 0.25, "score": 0.25, "binary_label": "no", "fulfillment_label": "partial", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.175, "upper": 0.175, "score": 0.175, "binary_label": "no", "fulfillment_label": "partial", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.25, "upper": 0.25, "score": 0.25, "binary_label": "no", "fulfillment_label": "partial", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}].
Same-observation counterfactual agreement: {"binary": 1.0, "fulfillment": 0.0}.

Selected labels: {"no": 5}. Observation events: {"observed": 10}.
Confidence per check: {"d1": [0.96, 0.98, 0.98, 0.96, 0.96], "d2": [0.97, 0.97, 0.97, 0.98, 0.98]}.
Known-answer consistency per check: {"d1": 1.0, "d2": 1.0}.

Fulfillment score bounds: [{"lower": 0.0, "upper": 0.0, "score": 0.0, "binary_label": "no", "fulfillment_label": "no", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.0, "upper": 0.0, "score": 0.0, "binary_label": "no", "fulfillment_label": "no", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.0, "upper": 0.0, "score": 0.0, "binary_label": "no", "fulfillment_label": "no", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.0, "upper": 0.0, "score": 0.0, "binary_label": "no", "fulfillment_label": "no", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.0, "upper": 0.0, "score": 0.0, "binary_label": "no", "fulfillment_label": "no", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}].
Same-observation counterfactual agreement: {"binary": 1.0, "fulfillment": 1.0}.

Search schedule: {"rounds_started": 1, "rounds_completed": 1, "max_rounds": 15}. Stop: confirmation_qualified.
Escalated: False. Usage: {"search": 18, "final": 21, "completion_tokens_or_reserved": 4569, "input_tokens": 57085}.

### Turn the image into a drawing made from chalk — binary

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 0.00 | 0.00 |
| Resolved draws / 5 | 5.00 | 5.00 |
| Final-label consistency | 1.00 | 1.00 |
| Minimum requirement consistency | 1.00 | 1.00 |
| Mean executed checks | 1.00 | 1.00 |
| Mean charged completion tokens | 103.40 | 104.80 |

Seed labels: {"no": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.91, 0.9, 0.88, 0.91, 0.88]}.
Known-answer consistency per check: {"d1": 1.0}.

Fulfillment score bounds: [{"lower": 0.85, "upper": 0.85, "score": 0.85, "binary_label": "no", "fulfillment_label": "partial", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.85, "upper": 0.85, "score": 0.85, "binary_label": "no", "fulfillment_label": "partial", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.85, "upper": 0.85, "score": 0.85, "binary_label": "no", "fulfillment_label": "partial", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.85, "upper": 0.85, "score": 0.85, "binary_label": "no", "fulfillment_label": "partial", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.85, "upper": 0.85, "score": 0.85, "binary_label": "no", "fulfillment_label": "partial", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}].
Same-observation counterfactual agreement: {"binary": 0.0, "fulfillment": 1.0}.

Selected labels: {"no": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.9, 0.91, 0.9, 0.91, 0.91]}.
Known-answer consistency per check: {"d1": 1.0}.

Fulfillment score bounds: [{"lower": 0.85, "upper": 0.85, "score": 0.85, "binary_label": "no", "fulfillment_label": "partial", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.85, "upper": 0.85, "score": 0.85, "binary_label": "no", "fulfillment_label": "partial", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.85, "upper": 0.85, "score": 0.85, "binary_label": "no", "fulfillment_label": "partial", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.85, "upper": 0.85, "score": 0.85, "binary_label": "no", "fulfillment_label": "partial", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.85, "upper": 0.85, "score": 0.85, "binary_label": "no", "fulfillment_label": "partial", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}].
Same-observation counterfactual agreement: {"binary": 0.0, "fulfillment": 1.0}.

Search schedule: {"rounds_started": 15, "rounds_completed": 15, "max_rounds": 15}. Stop: round_limit.
Escalated: False. Usage: {"search": 51, "final": 10, "completion_tokens_or_reserved": 9349, "input_tokens": 180251}.

### Turn the image into a drawing made from chalk — fulfillment

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 5.00 | 4.00 |
| Resolved draws / 5 | 5.00 | 4.00 |
| Final-label consistency | 1.00 | 0.80 |
| Minimum requirement consistency | 1.00 | 0.80 |
| Mean executed checks | 1.00 | 1.00 |
| Mean charged completion tokens | 98.80 | 494.80 |

Seed labels: {"partial": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.91, 0.88, 0.91, 0.91, 0.91]}.
Known-answer consistency per check: {"d1": 1.0}.

Fulfillment score bounds: [{"lower": 0.85, "upper": 0.85, "score": 0.85, "binary_label": "no", "fulfillment_label": "partial", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.85, "upper": 0.85, "score": 0.85, "binary_label": "no", "fulfillment_label": "partial", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.85, "upper": 0.85, "score": 0.85, "binary_label": "no", "fulfillment_label": "partial", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.85, "upper": 0.85, "score": 0.85, "binary_label": "no", "fulfillment_label": "partial", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.85, "upper": 0.85, "score": 0.85, "binary_label": "no", "fulfillment_label": "partial", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}].
Same-observation counterfactual agreement: {"binary": 0.0, "fulfillment": 1.0}.

Selected labels: {"partial": 4, "unresolved": 1}. Observation events: {"observed": 4, "transport_failure": 1}.
Confidence per check: {"d1": [0.9, 0.88, null, 0.91, 0.91]}.
Known-answer consistency per check: {"d1": 0.8}.

Fulfillment score bounds: [{"lower": 0.85, "upper": 0.85, "score": 0.85, "binary_label": "no", "fulfillment_label": "partial", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.85, "upper": 0.85, "score": 0.85, "binary_label": "no", "fulfillment_label": "partial", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.0, "upper": 1.0, "score": null, "binary_label": null, "fulfillment_label": null, "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.85, "upper": 0.85, "score": 0.85, "binary_label": "no", "fulfillment_label": "partial", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 0.85, "upper": 0.85, "score": 0.85, "binary_label": "no", "fulfillment_label": "partial", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}].
Same-observation counterfactual agreement: {"binary": 0.0, "fulfillment": 0.8}.

Search schedule: {"rounds_started": 0, "rounds_completed": 0, "max_rounds": 15}. Stop: confirmation_qualified.
Escalated: False. Usage: {"search": 6, "final": 11, "completion_tokens_or_reserved": 3517, "input_tokens": 19230}.

### Put a frog in the toilet — binary

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 0.00 | 0.00 |
| Resolved draws / 5 | 5.00 | 5.00 |
| Final-label consistency | 1.00 | 1.00 |
| Minimum requirement consistency | 1.00 | 1.00 |
| Mean executed checks | 1.00 | 1.00 |
| Mean charged completion tokens | 61.00 | 64.80 |

Seed labels: {"yes": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.99, 0.99, 0.99, 0.99, 0.99]}.
Known-answer consistency per check: {"d1": 1.0}.

Fulfillment score bounds: [{"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}].
Same-observation counterfactual agreement: {"binary": 0.0, "fulfillment": 0.0}.

Selected labels: {"yes": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.99, 0.99, 0.99, 0.99, 0.99]}.
Known-answer consistency per check: {"d1": 1.0}.

Fulfillment score bounds: [{"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}].
Same-observation counterfactual agreement: {"binary": 0.0, "fulfillment": 0.0}.

Search schedule: {"rounds_started": 15, "rounds_completed": 13, "max_rounds": 15}. Stop: round_limit.
Escalated: False. Usage: {"search": 55, "final": 10, "completion_tokens_or_reserved": 13561, "input_tokens": 306831}.

### Put a frog in the toilet — fulfillment

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 0.00 | 0.00 |
| Resolved draws / 5 | 5.00 | 5.00 |
| Final-label consistency | 1.00 | 1.00 |
| Minimum requirement consistency | 1.00 | 1.00 |
| Mean executed checks | 1.00 | 1.00 |
| Mean charged completion tokens | 63.60 | 65.60 |

Seed labels: {"yes": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.99, 0.99, 0.99, 0.99, 0.99]}.
Known-answer consistency per check: {"d1": 1.0}.

Fulfillment score bounds: [{"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}].
Same-observation counterfactual agreement: {"binary": 0.0, "fulfillment": 0.0}.

Selected labels: {"yes": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.99, 0.99, 0.99, 0.99, 0.99]}.
Known-answer consistency per check: {"d1": 1.0}.

Fulfillment score bounds: [{"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}].
Same-observation counterfactual agreement: {"binary": 0.0, "fulfillment": 0.0}.

Search schedule: {"rounds_started": 15, "rounds_completed": 14, "max_rounds": 15}. Stop: round_limit.
Escalated: False. Usage: {"search": 49, "final": 10, "completion_tokens_or_reserved": 11304, "input_tokens": 270907}.

### the small gray rubber cylinder becomes brown — binary

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 5.00 | 5.00 |
| Resolved draws / 5 | 5.00 | 5.00 |
| Final-label consistency | 1.00 | 1.00 |
| Minimum requirement consistency | 1.00 | 1.00 |
| Mean executed checks | 1.00 | 1.00 |
| Mean charged completion tokens | 59.20 | 60.40 |

Seed labels: {"yes": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.98, 0.96, 0.98, 0.98, 0.98]}.
Known-answer consistency per check: {"d1": 1.0}.

Fulfillment score bounds: [{"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}].
Same-observation counterfactual agreement: {"binary": 1.0, "fulfillment": 1.0}.

Selected labels: {"yes": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.98, 0.96, 0.98, 0.96, 0.98]}.
Known-answer consistency per check: {"d1": 1.0}.

Fulfillment score bounds: [{"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "binary", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}].
Same-observation counterfactual agreement: {"binary": 1.0, "fulfillment": 1.0}.

Search schedule: {"rounds_started": 0, "rounds_completed": 0, "max_rounds": 15}. Stop: confirmation_qualified.
Escalated: False. Usage: {"search": 6, "final": 10, "completion_tokens_or_reserved": 924, "input_tokens": 17120}.

### the small gray rubber cylinder becomes brown — fulfillment

| Measurement | Seed | Selected |
|---|---:|---:|
| Reference matches / 5 | 5.00 | 5.00 |
| Resolved draws / 5 | 5.00 | 5.00 |
| Final-label consistency | 1.00 | 1.00 |
| Minimum requirement consistency | 1.00 | 1.00 |
| Mean executed checks | 1.00 | 1.00 |
| Mean charged completion tokens | 60.20 | 264.00 |

Seed labels: {"yes": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.98, 0.96, 0.96, 0.96, 0.98]}.
Known-answer consistency per check: {"d1": 1.0}.

Fulfillment score bounds: [{"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}].
Same-observation counterfactual agreement: {"binary": 1.0, "fulfillment": 1.0}.

Selected labels: {"yes": 5}. Observation events: {"observed": 5}.
Confidence per check: {"d1": [0.98, 0.98, 0.98, 0.98, 0.98]}.
Known-answer consistency per check: {"d1": 1.0}.

Fulfillment score bounds: [{"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}, {"lower": 1.0, "upper": 1.0, "score": 1.0, "binary_label": "yes", "fulfillment_label": "yes", "mode": "fulfillment", "thresholds": {"yes": 0.9, "no": 0.1}, "unknowns_are_intervals": true, "semantic_audit": "disabled", "model_readout": false}].
Same-observation counterfactual agreement: {"binary": 1.0, "fulfillment": 1.0}.

Search schedule: {"rounds_started": 0, "rounds_completed": 0, "max_rounds": 15}. Stop: confirmation_qualified.
Escalated: False. Usage: {"search": 6, "final": 11, "completion_tokens_or_reserved": 1940, "input_tokens": 17120}.

## Accounting

{
  "calls": 867,
  "completion_tokens_or_reserved": 160478,
  "input_tokens": 2239059,
  "consecutive_errors": 0,
  "stopped": null,
  "authorized_resumes": [
    {
      "version": "v4-authorized-transport-continuation",
      "calls": 188,
      "charged_completion_tokens": 51046,
      "prior_budget_sha256": "6deea97a6a1cb617d1decc37357f437f19671ca2f3fa8d22bd5e5da2a54cdfb8",
      "failed_slots_retried": false,
      "authorization": "Explicit --resume --release-transport-stop invocation"
    }
  ],
  "final_calls": 287,
  "final_tokens": 29904
}

Returned models: gpt-6-luna
Error: none

Historical results are descriptive. This comparison isolates proposer escalation under the same new runtime. Confidence is self-report, semantic audit is fallible, and unvisited alternatives remain untested. A reference-conflict flag requests review; it does not certify that the saved label is wrong.
