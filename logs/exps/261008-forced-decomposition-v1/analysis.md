# Broad versus forced decomposition: saved-data analysis

Each row is one previously observed case fitted by one method. Seed and selected programs each have five fresh final draws. Repeated draws measure local behavior; there are only three independent cases.

| Case | Method | Correct seed answers / 5 | Correct selected answers / 5 | Usable selected answers / 5 | Selected checks | Changed program? | Passed all robustness gates? |
|---|---|---:|---:|---:|---:|---|---|
| Change the background into a basketball court | broad-greedy | 4 | 4 | 5 | 1 | true | yes |
| Change the background into a basketball court | decomposed-greedy | 3 | 5 | 5 | 3 | false | yes |
| Turn the image into a drawing made from chalk | broad-greedy | 0 | 5 | 5 | 1 | true | yes |
| Turn the image into a drawing made from chalk | decomposed-greedy | 0 | 0 | 5 | 3 | false | no: unresolved |
| Put a frog in the toilet | broad-greedy | 0 | 0 | 5 | 1 | false | no: stable_but_mismatched |
| Put a frog in the toilet | decomposed-greedy | 0 | 0 | 5 | 3 | false | no: unresolved |

Correct answers = matching the saved reference label; unanswered/invalid calls count as incorrect. Usable answers = resolved yes/partial/no, even if wrong. Changed program = different executable hash. Passing all gates also requires audit approval, consistency and confidence; it cannot be inferred from correctness alone.

## Change the background into a basketball court — broad-greedy

Reference label: `yes`. Seed labels: {"partial": 1, "yes": 4}; selected labels: {"partial": 1, "yes": 4}.
Selected semantic audit: True; The program preserves the sole requested background change and its target/reference binding. Its fulfillment check distinguishes complete, partial, absent, and unknown using relevant visual evidence; it adds no unsupported constraints, gates, or inferences. The tree has no routing or dependency complications, and the checker instructions do not encode an expected answer.
Proposed transactions: 2; rejected diagnostics: {}.
Final acceptance: {"qualified": true, "reasons": [], "policy": {"repeats": 5, "agreement": 0.8, "consistency": 0.8, "confidence": 0.8, "minimum_eligible": 3}}.

| Component | Visual input | Question | Final states | Lowest reported confidence |
|---|---|---|---|---:|
| n1 (requested) | source and edited images | In the edited image, has the background been changed into a basketball court? | {"partial": 1, "complete": 4} | 0.94 |

Measured scope usage, including preparation-independent search and final checks: {"search": 26, "final": 10, "completion_tokens_or_reserved": 2453, "input_tokens": 53879}.

## Change the background into a basketball court — decomposed-greedy

Reference label: `yes`. Seed labels: {"None": 2, "yes": 3}; selected labels: {"yes": 5}.
Selected semantic audit: True; The supports separately assess a recognizable basketball-court background and specific incomplete progress toward one. The readout uses both observations to distinguish complete, partial, absent, and unknown; it treats known negatives as evidence and does not require unseen facts.
Proposed transactions: 3; rejected diagnostics: {"Virtual-root children have no activation condition": 2}.
Final acceptance: {"qualified": true, "reasons": [], "policy": {"repeats": 5, "agreement": 0.8, "consistency": 0.8, "confidence": 0.8, "minimum_eligible": 3}}.

| Component | Visual input | Question | Final states | Lowest reported confidence |
|---|---|---|---|---:|
| n1 (support) | source and edited images | Is the visible background recognizably a basketball court? | {"pass": 5} | 0.99 |
| n2 (support) | source and edited images | Is there visible evidence that the background has been changed toward a basketball court, even if it is not recognizably a complete court? | {"pass": 5} | 0.99 |
| n3 (requested) | saved evidence only | Does the image show the background changed into a basketball court? | {"complete": 5} | 0.99 |

Measured scope usage, including preparation-independent search and final checks: {"search": 31, "final": 28, "completion_tokens_or_reserved": 9340, "input_tokens": 117245}.

## Turn the image into a drawing made from chalk — broad-greedy

Reference label: `partial`. Seed labels: {"yes": 5}; selected labels: {"partial": 5}.
Selected semantic audit: True; The tree program preserves the original instruction and rubric: it covers the sole requested outcome, binds the image to a chalk drawing, and uses applicable criteria that distinguish complete, partial, absent, and unknown fulfillment. No unsupported inference, dependency, gate, or extra constraint is introduced.
Proposed transactions: 2; rejected diagnostics: {}.
Final acceptance: {"qualified": true, "reasons": [], "policy": {"repeats": 5, "agreement": 0.8, "consistency": 0.8, "confidence": 0.8, "minimum_eligible": 3}}.

| Component | Visual input | Question | Final states | Lowest reported confidence |
|---|---|---|---|---:|
| n1 (requested) | source and edited images | Compared with the source, has the image as a whole been transformed into a drawing made from chalk, rather than merely given chalk-like texture or contours? | {"partial": 5} | 0.94 |

Measured scope usage, including preparation-independent search and final checks: {"search": 26, "final": 10, "completion_tokens_or_reserved": 3109, "input_tokens": 56566}.

## Turn the image into a drawing made from chalk — decomposed-greedy

Reference label: `partial`. Seed labels: {"yes": 5}; selected labels: {"yes": 5}.
Selected semantic audit: False; The two supports are distinct and relevant, and the readout maps their pass/fail/unknown combinations to the rubric states. But the medium support is too narrow: it requires visible chalk-like marks or texture, so a chalk drawing without those particular visible cues may be marked fail. The readout would then treat that failure as evidence of incomplete fulfillment, potentially misclassifying a completed edit.
Proposed transactions: 3; rejected diagnostics: {"Virtual-root children have no activation condition": 3}.
Final acceptance: {"qualified": false, "reasons": ["semantic_audit", "target_mismatch"], "policy": {"repeats": 5, "agreement": 0.8, "consistency": 0.8, "confidence": 0.8, "minimum_eligible": 3}}.

| Component | Visual input | Question | Final states | Lowest reported confidence |
|---|---|---|---|---:|
| n1 (support) | source and edited images | Does the edited image visibly have a chalk-like drawing medium or surface treatment? | {"pass": 5} | 0.94 |
| n2 (support) | source and edited images | Does the edited image visibly present its depicted content as a drawing rather than as an unchanged photograph? | {"pass": 5} | 0.98 |
| n3 (requested) | saved evidence only | Has the image been transformed into a drawing made from chalk? | {"complete": 5} | 0.96 |

Measured scope usage, including preparation-independent search and final checks: {"search": 3, "final": 30, "completion_tokens_or_reserved": 3774, "input_tokens": 41684}.

## Put a frog in the toilet — broad-greedy

Reference label: `partial`. Seed labels: {"yes": 5}; selected labels: {"yes": 5}.
Selected semantic audit: True; Faithfully captures the requested frog-in-toilet placement and distinguishes complete, partial, absent, and insufficient evidence without adding requirements.
Proposed transactions: 3; rejected diagnostics: {}.
Final acceptance: {"qualified": false, "reasons": ["target_mismatch"], "policy": {"repeats": 5, "agreement": 0.8, "consistency": 0.8, "confidence": 0.8, "minimum_eligible": 3}, "reference_conflict_suspected": true}.

| Component | Visual input | Question | Final states | Lowest reported confidence |
|---|---|---|---|---:|
| n1 (requested) | source and edited images | Is a frog placed inside the toilet? | {"complete": 5} | 0.99 |

Measured scope usage, including preparation-independent search and final checks: {"search": 28, "final": 10, "completion_tokens_or_reserved": 2785, "input_tokens": 119352}.

## Put a frog in the toilet — decomposed-greedy

Reference label: `partial`. Seed labels: {"yes": 5}; selected labels: {"yes": 5}.
Selected semantic audit: False; The supports are distinct and relevant, but they do not preserve enough evidence for the readout: frog presence and toilet presence separately cannot establish whether the frog is inside the toilet or partly placed there. The readout must infer placement not recorded by either support.
Proposed transactions: 3; rejected diagnostics: {"Virtual-root children have no activation condition": 2}.
Final acceptance: {"qualified": false, "reasons": ["semantic_audit", "target_mismatch"], "policy": {"repeats": 5, "agreement": 0.8, "consistency": 0.8, "confidence": 0.8, "minimum_eligible": 3}}.

| Component | Visual input | Question | Final states | Lowest reported confidence |
|---|---|---|---|---:|
| n1 (support) | source and edited images | Is a frog visibly present in the edited image? | {"pass": 5} | 0.99 |
| n2 (support) | source and edited images | Is the toilet visibly identifiable in the edited image? | {"pass": 5} | 0.99 |
| n3 (requested) | saved evidence only | Based only on the saved observations and image-grounded evidence from both supports, was a frog added inside the toilet? | {"complete": 5} | 0.99 |

Measured scope usage, including preparation-independent search and final checks: {"search": 4, "final": 30, "completion_tokens_or_reserved": 3347, "input_tokens": 83492}.

## Interpretation limits

Forcing several calls does not guarantee a useful decomposition. A component set must record the relation or property needed for fulfillment, and its readout must preserve the original scoring rules. A rejected semantic audit remains a rejection even when observed labels match. Proposal-format failures limit what this test says about the effectiveness of structural repair. Confidence is reported by the model and is not calibrated probability. No final observations were used to change the frozen selected programs. Broad-versus-decomposed fidelity is recorded separately in scoring_fidelity.json.
