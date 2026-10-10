# Twelve-case typed optimizer: saved final comparison

Status: completed. Twelve previously observed local fitting cases; four per reference class. Repeats are measurements within cases, not additional cases or evidence of generalization.

## Definitions

- Matches: final predictions equal to the reference label, out of five fresh draws.
- Resolved: draws that produced a usable final label, whether correct or wrong.
- Confidence: lowest numeric self-reported confidence across executed checks; missing values are counted separately. It is not calibrated probability.
- Checks: saved program size; skipped or failed calls can lower actual executed checks.
- Robust: approved semantic audit, qualifying complete confirmation, and all frozen final gates. Nested-required additionally needs an executed added evidence-context check.

## Raw measurements

| Method | Seed → selected matches / 60 | Seed → selected resolved / 60 | Verified robust cases |
|---|---:|---:|---:|
| criterion-only | 17 → 31 | 49 → 47 | 4 |
| nested-required | 16 → 24 | 49 → 39 | 0 |

The raw denominators retain all twelve cases, including failed preparation. All final measurements are complete.

**Protocol caveat:** the first continuation repeated seven nested-mug proposal slots because replay changed a saved failure diagnostic. All costs remain charged. That scope is excluded from valid robustness claims and the paired comparison below; the raw measurements retain it for transparency. The second continuation preserves historical diagnostics and guards inherited logical slots before any new request.

## Paired comparison excluding the affected mug case

Both methods use the same remaining eleven cases; the two invalid-seed cases remain failures. This subset is no longer class-balanced.

| Method | Seed → selected matches / 55 | Selected resolved / 55 |
|---|---:|---:|
| criterion-only | 17 → 31 | 42 |
| nested-required | 16 → 24 | 39 |

## Per-case results

| Case / reference | Method | Seed → selected matches / 5 | Selected resolved / 5 | Lowest confidence (missing) | Checks | Result |
|---|---|---:|---:|---|---:|---|
| White DVD / no | criterion-only | not executed | not executed | — (0) | 0 | unresolved |
| White DVD / no | nested-required | not executed | not executed | — (0) | 0 | unresolved |
| Closed jacket / yes | criterion-only | 0 → 0 | 5 | 0.91 (0) | 3 | unconfirmed |
| Closed jacket / yes | nested-required | 0 → 0 | 5 | 0.88 (0) | 3 | structural_failure |
| Pencil drawing / partial | criterion-only | 0 → 5 | 5 | 0.94 (0) | 3 | locally_robust |
| Pencil drawing / partial | nested-required | 0 → 1 | 4 | 0.91 (1) | 4 | unconfirmed |
| Helmet / yes | criterion-only | 5 → 4 | 4 | 0.99 (1) | 3 | unresolved |
| Helmet / yes | nested-required | 5 → 4 | 4 | 0.99 (1) | 3 | structural_failure |
| Basketball background / yes | criterion-only | 5 → 4 | 5 | 0.78 (0) | 3 | unconfirmed |
| Basketball background / yes | nested-required | 3 → 0 | 2 | 0.91 (3) | 4 | unconfirmed |
| Mug position / partial | criterion-only | 0 → 0 | 5 | 0.98 (0) | 3 | unconfirmed |
| Mug position / partial | nested-required | 0 → 0 | 0 | 0.91 (1) | 4 | unconfirmed / protocol deviation |
| Book position / no | criterion-only | 5 → 3 | 3 | 0.91 (0) | 3 | unconfirmed |
| Book position / no | nested-required | 5 → 5 | 5 | 0.94 (0) | 3 | structural_failure |
| Paper in cup / no | criterion-only | 2 → 5 | 5 | 0.96 (0) | 3 | locally_robust |
| Paper in cup / no | nested-required | 3 → 4 | 5 | 0.72 (0) | 3 | structural_failure |
| Comic style / no | criterion-only | 0 → 5 | 5 | 0.94 (0) | 3 | locally_robust |
| Comic style / no | nested-required | 0 → 5 | 5 | 0.94 (0) | 4 | unconfirmed |
| Chalk drawing / partial | criterion-only | 0 → 5 | 5 | 0.91 (0) | 3 | locally_robust |
| Chalk drawing / partial | nested-required | 0 → 5 | 5 | 0.88 (0) | 4 | unconfirmed |
| Frog in toilet / partial | criterion-only | 0 → 0 | 5 | 0.99 (0) | 3 | unconfirmed |
| Frog in toilet / partial | nested-required | 0 → 0 | 4 | 0.99 (1) | 3 | structural_failure |
| Brown cylinder / yes | criterion-only | not executed | not executed | — (0) | 0 | unresolved |
| Brown cylinder / yes | nested-required | not executed | not executed | — (0) | 0 | unresolved |

## Usage and verification

Combined model calls: 2364. Final calls: 607.
Charged completion tokens: 420200. Input tokens: 7288931.
Ceilings remain 3,600 calls and 4,608,000 completion tokens. Inherited ledgers are not added again. Synthetic TLS diagnostics made no model calls and are not part of these optimizer measurements.
Returned model identities: ["gpt-6-luna"].

Exact programs, observations, audits and lineages remain in `frozen/`, `prepared/`, `observations/` and `jobs/`. See `analysis.md`, `component_analysis.json`, `protocol_verification.json`, `continuation_verification.json` and `protocol_deviations.json`.

### White DVD / criterion-only

Rejection reasons: []. Preparation error: ValueError: Evidence questions must be distinct from each other and fulfillment.
Direct final-call failures: {}.
Completed search rounds: None. Added evidence-context checks: [].
Requirement consistency: None. Mean executed checks: None. Mean charged checker completion tokens per draw: None.
Case-arm usage: {}.

### White DVD / nested-required

Rejection reasons: []. Preparation error: ValueError: Evidence questions must be distinct from each other and fulfillment.
Direct final-call failures: {}.
Completed search rounds: None. Added evidence-context checks: [].
Requirement consistency: None. Mean executed checks: None. Mean charged checker completion tokens per draw: None.
Case-arm usage: {}.

### Closed jacket / criterion-only

Rejection reasons: ["target_mismatch", "confirmation_missing_or_unqualified"]. Preparation error: None.
Direct final-call failures: {}.
Completed search rounds: 7. Added evidence-context checks: [].
Requirement consistency: 1.0. Mean executed checks: 3.0. Mean charged checker completion tokens per draw: 183.2.
Case-arm usage: {"search": 109, "final": 30, "completion_tokens_or_reserved": 18714, "input_tokens": 293605}.

### Closed jacket / nested-required

Rejection reasons: ["target_mismatch", "confirmation_missing_or_unqualified", "no_eligible_executed_nested_check"]. Preparation error: None.
Direct final-call failures: {}.
Completed search rounds: 15. Added evidence-context checks: [].
Requirement consistency: 1.0. Mean executed checks: 3.0. Mean charged checker completion tokens per draw: 184.0.
Case-arm usage: {"search": 90, "final": 30, "completion_tokens_or_reserved": 18653, "input_tokens": 310777}.

### Pencil drawing / criterion-only

Rejection reasons: []. Preparation error: None.
Direct final-call failures: {}.
Completed search rounds: 2. Added evidence-context checks: [].
Requirement consistency: 1.0. Mean executed checks: 3.0. Mean charged checker completion tokens per draw: 216.2.
Case-arm usage: {"search": 48, "final": 30, "completion_tokens_or_reserved": 7466, "input_tokens": 136268}.

### Pencil drawing / nested-required

Rejection reasons: ["unresolved", "target_mismatch", "requirement_instability", "node_instability:s3", "node_instability:fulfillment", "confidence", "confirmation_missing_or_unqualified"]. Preparation error: None.
Direct final-call failures: {"CallFailure": 1}.
Completed search rounds: 10. Added evidence-context checks: ["s3"].
Requirement consistency: 0.6. Mean executed checks: 3.8. Mean charged checker completion tokens per draw: 447.4.
Case-arm usage: {"search": 109, "final": 34, "completion_tokens_or_reserved": 27279, "input_tokens": 485134}.

### Helmet / criterion-only

Rejection reasons: ["unresolved", "confidence"]. Preparation error: None.
Direct final-call failures: {"CallFailure": 1}.
Completed search rounds: 4. Added evidence-context checks: [].
Requirement consistency: 0.8. Mean executed checks: 2.8. Mean charged checker completion tokens per draw: 339.2.
Case-arm usage: {"search": 59, "final": 29, "completion_tokens_or_reserved": 11584, "input_tokens": 199586}.

### Helmet / nested-required

Rejection reasons: ["semantic_audit", "unresolved", "confidence", "confirmation_missing_or_unqualified", "no_eligible_executed_nested_check"]. Preparation error: None.
Direct final-call failures: {"CallFailure": 1}.
Completed search rounds: 15. Added evidence-context checks: [].
Requirement consistency: 0.8. Mean executed checks: 2.8. Mean charged checker completion tokens per draw: 329.0.
Case-arm usage: {"search": 80, "final": 29, "completion_tokens_or_reserved": 22039, "input_tokens": 338215}.

### Basketball background / criterion-only

Rejection reasons: ["confidence", "confirmation_missing_or_unqualified"]. Preparation error: None.
Direct final-call failures: {}.
Completed search rounds: 6. Added evidence-context checks: [].
Requirement consistency: 0.8. Mean executed checks: 3.0. Mean charged checker completion tokens per draw: 192.6.
Case-arm usage: {"search": 109, "final": 30, "completion_tokens_or_reserved": 19850, "input_tokens": 311429}.

### Basketball background / nested-required

Rejection reasons: ["unresolved", "target_mismatch", "requirement_instability", "node_instability:s1", "node_instability:s3", "insufficient_activation:fulfillment", "confidence", "confirmation_missing_or_unqualified"]. Preparation error: None.
Direct final-call failures: {"CallFailure": 3}.
Completed search rounds: 12. Added evidence-context checks: ["s3"].
Requirement consistency: 0.4. Mean executed checks: 3.0. Mean charged checker completion tokens per draw: 758.8.
Case-arm usage: {"search": 109, "final": 30, "completion_tokens_or_reserved": 34081, "input_tokens": 633088}.

### Mug position / criterion-only

Rejection reasons: ["target_mismatch", "confirmation_missing_or_unqualified"]. Preparation error: None.
Direct final-call failures: {}.
Completed search rounds: 12. Added evidence-context checks: [].
Requirement consistency: 1.0. Mean executed checks: 3.0. Mean charged checker completion tokens per draw: 153.4.
Case-arm usage: {"search": 109, "final": 30, "completion_tokens_or_reserved": 23087, "input_tokens": 569905}.

### Mug position / nested-required

Rejection reasons: ["unresolved", "target_mismatch", "requirement_instability", "node_instability:s3", "confidence", "confirmation_missing_or_unqualified"]. Preparation error: None.
Direct final-call failures: {"CallFailure": 1}.
Completed search rounds: 12. Added evidence-context checks: ["s3"].
Requirement consistency: 0.0. Mean executed checks: 2.8. Mean charged checker completion tokens per draw: 388.2.
Case-arm usage: {"search": 109, "final": 29, "completion_tokens_or_reserved": 30011, "input_tokens": 499242}.

### Book position / criterion-only

Rejection reasons: ["unresolved", "target_mismatch", "requirement_instability", "node_instability:fulfillment", "confirmation_missing_or_unqualified"]. Preparation error: None.
Direct final-call failures: {}.
Completed search rounds: 6. Added evidence-context checks: [].
Requirement consistency: 0.6. Mean executed checks: 3.0. Mean charged checker completion tokens per draw: 225.6.
Case-arm usage: {"search": 109, "final": 30, "completion_tokens_or_reserved": 22818, "input_tokens": 425946}.

### Book position / nested-required

Rejection reasons: ["confirmation_missing_or_unqualified", "no_eligible_executed_nested_check"]. Preparation error: None.
Direct final-call failures: {}.
Completed search rounds: 15. Added evidence-context checks: [].
Requirement consistency: 1.0. Mean executed checks: 3.0. Mean charged checker completion tokens per draw: 200.4.
Case-arm usage: {"search": 86, "final": 30, "completion_tokens_or_reserved": 20317, "input_tokens": 399990}.

### Paper in cup / criterion-only

Rejection reasons: []. Preparation error: None.
Direct final-call failures: {}.
Completed search rounds: 2. Added evidence-context checks: [].
Requirement consistency: 1.0. Mean executed checks: 3.0. Mean charged checker completion tokens per draw: 175.0.
Case-arm usage: {"search": 33, "final": 30, "completion_tokens_or_reserved": 5378, "input_tokens": 80038}.

### Paper in cup / nested-required

Rejection reasons: ["semantic_audit", "node_instability:s2", "confidence", "confirmation_missing_or_unqualified", "no_eligible_executed_nested_check"]. Preparation error: None.
Direct final-call failures: {}.
Completed search rounds: 15. Added evidence-context checks: [].
Requirement consistency: 0.8. Mean executed checks: 3.0. Mean charged checker completion tokens per draw: 173.8.
Case-arm usage: {"search": 90, "final": 30, "completion_tokens_or_reserved": 18457, "input_tokens": 293935}.

### Comic style / criterion-only

Rejection reasons: []. Preparation error: None.
Direct final-call failures: {}.
Completed search rounds: 1. Added evidence-context checks: [].
Requirement consistency: 1.0. Mean executed checks: 3.0. Mean charged checker completion tokens per draw: 190.2.
Case-arm usage: {"search": 40, "final": 30, "completion_tokens_or_reserved": 6795, "input_tokens": 97118}.

### Comic style / nested-required

Rejection reasons: ["confirmation_missing_or_unqualified"]. Preparation error: None.
Direct final-call failures: {}.
Completed search rounds: 14. Added evidence-context checks: ["s3"].
Requirement consistency: 1.0. Mean executed checks: 4.0. Mean charged checker completion tokens per draw: 262.4.
Case-arm usage: {"search": 109, "final": 34, "completion_tokens_or_reserved": 34230, "input_tokens": 495903}.

### Chalk drawing / criterion-only

Rejection reasons: []. Preparation error: None.
Direct final-call failures: {}.
Completed search rounds: 1. Added evidence-context checks: [].
Requirement consistency: 1.0. Mean executed checks: 3.0. Mean charged checker completion tokens per draw: 217.0.
Case-arm usage: {"search": 42, "final": 30, "completion_tokens_or_reserved": 5769, "input_tokens": 112909}.

### Chalk drawing / nested-required

Rejection reasons: ["confirmation_missing_or_unqualified"]. Preparation error: None.
Direct final-call failures: {}.
Completed search rounds: 15. Added evidence-context checks: ["s3"].
Requirement consistency: 1.0. Mean executed checks: 4.0. Mean charged checker completion tokens per draw: 275.6.
Case-arm usage: {"search": 101, "final": 35, "completion_tokens_or_reserved": 37179, "input_tokens": 501538}.

### Frog in toilet / criterion-only

Rejection reasons: ["target_mismatch", "confirmation_missing_or_unqualified"]. Preparation error: None.
Direct final-call failures: {}.
Completed search rounds: 15. Added evidence-context checks: [].
Requirement consistency: 1.0. Mean executed checks: 3.0. Mean charged checker completion tokens per draw: 207.0.
Case-arm usage: {"search": 105, "final": 29, "completion_tokens_or_reserved": 26801, "input_tokens": 604761}.

### Frog in toilet / nested-required

Rejection reasons: ["semantic_audit", "unresolved", "target_mismatch", "confidence", "confirmation_missing_or_unqualified", "no_eligible_executed_nested_check"]. Preparation error: None.
Direct final-call failures: {"CallFailure": 1}.
Completed search rounds: 15. Added evidence-context checks: [].
Requirement consistency: 0.8. Mean executed checks: 2.6. Mean charged checker completion tokens per draw: 325.0.
Case-arm usage: {"search": 89, "final": 28, "completion_tokens_or_reserved": 24655, "input_tokens": 479748}.

### Brown cylinder / criterion-only

Rejection reasons: []. Preparation error: GraphValidationError: s2 may reference only earlier support indices.
Direct final-call failures: {}.
Completed search rounds: None. Added evidence-context checks: [].
Requirement consistency: None. Mean executed checks: None. Mean charged checker completion tokens per draw: None.
Case-arm usage: {}.

### Brown cylinder / nested-required

Rejection reasons: []. Preparation error: GraphValidationError: s2 may reference only earlier support indices.
Direct final-call failures: {}.
Completed search rounds: None. Added evidence-context checks: [].
Requirement consistency: None. Mean executed checks: None. Mean charged checker completion tokens per draw: None.
Case-arm usage: {}.
