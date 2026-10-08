# Broad versus forced decomposition: saved-data analysis

Each row is one previously observed case fitted by one method. Seed and selected programs each have five fresh final draws. Repeated draws measure local behavior; there are only three independent cases.

| Case | Method | Correct seed answers / 5 | Correct selected answers / 5 | Usable selected answers / 5 | Selected checks | Changed program? | Passed all robustness gates? |
|---|---|---:|---:|---:|---:|---|---|
| Change the background into a basketball court | broad-greedy | 2 | 1 | 3 | 1 | true | no: unresolved |
| Change the background into a basketball court | decomposed-greedy | 3 | 4 | 5 | 3 | false | yes |
| Turn the image into a drawing made from chalk | broad-greedy | 0 | 5 | 5 | 1 | true | yes |
| Turn the image into a drawing made from chalk | decomposed-greedy | 0 | 0 | 5 | 3 | false | no: unresolved |
| Put a frog in the toilet | broad-greedy | 0 | 1 | 5 | 1 | false | no: unstable_and_mismatched |
| Put a frog in the toilet | decomposed-greedy | 0 | 0 | 5 | 3 | false | no: unresolved |

Correct answers = matching the saved reference label; unanswered/invalid calls count as incorrect. Usable answers = resolved yes/partial/no, even if wrong. Changed program = different executable hash. Passing all gates also requires audit approval, consistency and confidence; it cannot be inferred from correctness alone.

## Change the background into a basketball court — broad-greedy

Reference label: `yes`. Seed labels: {"partial": 3, "yes": 2}; selected labels: {"partial": 2, "yes": 1, "None": 2}.
Selected semantic audit: True; The program preserves the sole requested outcome and its target/reference, with an applicable fulfillment check that distinguishes complete, partial, absent, and unknown using image-grounded evidence. It adds no unsupported constraints or inferences, and the tree has no routing or dependency issues.
Proposed transactions: 3; rejected diagnostics: {}.
Final acceptance: {"qualified": false, "reasons": ["unresolved", "target_mismatch", "requirement_instability", "node_instability:n1", "confidence"], "policy": {"repeats": 5, "agreement": 0.8, "consistency": 0.8, "confidence": 0.8, "minimum_eligible": 3}}.

| Component | Visual input | Question | Final states | Lowest reported confidence |
|---|---|---|---|---:|
| n1 (requested) | source and edited images | Does the edited image show the background changed into a recognizable basketball court? | {"partial": 2, "complete": 1, "unknown": 2} | 0.98 |

Measured scope usage, including preparation-independent search and final checks: {"search": 28, "final": 10, "completion_tokens_or_reserved": 8174, "input_tokens": 54841}.

## Change the background into a basketball court — decomposed-greedy

Reference label: `yes`. Seed labels: {"None": 1, "partial": 1, "yes": 3}; selected labels: {"yes": 4, "partial": 1}.
Selected semantic audit: True; The supports separately assess a recognizable basketball-court background and specific incomplete progress toward one. The readout uses both observations to distinguish complete, partial, absent, and unknown; it treats known negatives as evidence and does not require unseen facts.
Proposed transactions: 3; rejected diagnostics: {}.
Final acceptance: {"qualified": true, "reasons": [], "policy": {"repeats": 5, "agreement": 0.8, "consistency": 0.8, "confidence": 0.8, "minimum_eligible": 3}}.

| Component | Visual input | Question | Final states | Lowest reported confidence |
|---|---|---|---|---:|
| n1 (support) | source and edited images | Is the visible background recognizably a basketball court? | {"pass": 4, "fail": 1} | 0.91 |
| n2 (support) | source and edited images | Is there visible evidence that the background has been changed toward a basketball court, even if it is not recognizably a complete court? | {"pass": 5} | 0.99 |
| n3 (requested) | saved evidence only | Does the image show the background changed into a basketball court? | {"complete": 4, "partial": 1} | 0.98 |

Measured scope usage, including preparation-independent search and final checks: {"search": 33, "final": 29, "completion_tokens_or_reserved": 8333, "input_tokens": 121256}.

## Turn the image into a drawing made from chalk — broad-greedy

Reference label: `partial`. Seed labels: {"yes": 5}; selected labels: {"partial": 5}.
Selected semantic audit: True; The tree program preserves the sole requested outcome, its target and reference, and the rubric’s complete/partial/absent/unknown distinctions. Its criteria do not add a specific technique or subject-removal constraint, and no routing, dependency, or inference changes the requested check.
Proposed transactions: 3; rejected diagnostics: {}.
Final acceptance: {"qualified": true, "reasons": [], "policy": {"repeats": 5, "agreement": 0.8, "consistency": 0.8, "confidence": 0.8, "minimum_eligible": 3}}.

| Component | Visual input | Question | Final states | Lowest reported confidence |
|---|---|---|---|---:|
| n1 (requested) | source and edited images | Has the image been transformed into a drawing that reads as made from chalk? | {"partial": 5} | 0.94 |

Measured scope usage, including preparation-independent search and final checks: {"search": 22, "final": 10, "completion_tokens_or_reserved": 2832, "input_tokens": 50058}.

## Turn the image into a drawing made from chalk — decomposed-greedy

Reference label: `partial`. Seed labels: {"yes": 5}; selected labels: {"yes": 5}.
Selected semantic audit: False; The two supports are distinct and relevant, and the readout maps their pass/fail/unknown combinations to the rubric states. But the medium support is too narrow: it requires visible chalk-like marks or texture, so a chalk drawing without those particular visible cues may be marked fail. The readout would then treat that failure as evidence of incomplete fulfillment, potentially misclassifying a completed edit.
Proposed transactions: 4; rejected diagnostics: {"Reordering must name every node exactly once": 2}.
Final acceptance: {"qualified": false, "reasons": ["semantic_audit", "target_mismatch"], "policy": {"repeats": 5, "agreement": 0.8, "consistency": 0.8, "confidence": 0.8, "minimum_eligible": 3}}.

| Component | Visual input | Question | Final states | Lowest reported confidence |
|---|---|---|---|---:|
| n1 (support) | source and edited images | Does the edited image visibly have a chalk-like drawing medium or surface treatment? | {"pass": 5} | 0.94 |
| n2 (support) | source and edited images | Does the edited image visibly present its depicted content as a drawing rather than as an unchanged photograph? | {"pass": 5} | 0.97 |
| n3 (requested) | saved evidence only | Has the image been transformed into a drawing made from chalk? | {"complete": 5} | 0.96 |

Measured scope usage, including preparation-independent search and final checks: {"search": 5, "final": 30, "completion_tokens_or_reserved": 3316, "input_tokens": 44042}.

## Put a frog in the toilet — broad-greedy

Reference label: `partial`. Seed labels: {"yes": 5}; selected labels: {"yes": 4, "partial": 1}.
Selected semantic audit: True; Faithfully captures the requested frog-in-toilet placement and distinguishes complete, partial, absent, and insufficient evidence without adding requirements.
Proposed transactions: 2; rejected diagnostics: {"Need one to four edits and a diagnostic reason": 1}.
Final acceptance: {"qualified": false, "reasons": ["target_mismatch"], "policy": {"repeats": 5, "agreement": 0.8, "consistency": 0.8, "confidence": 0.8, "minimum_eligible": 3}}.

| Component | Visual input | Question | Final states | Lowest reported confidence |
|---|---|---|---|---:|
| n1 (requested) | source and edited images | Is a frog placed inside the toilet? | {"complete": 4, "partial": 1} | 0.98 |

Measured scope usage, including preparation-independent search and final checks: {"search": 19, "final": 10, "completion_tokens_or_reserved": 2139, "input_tokens": 97467}.

## Put a frog in the toilet — decomposed-greedy

Reference label: `partial`. Seed labels: {"yes": 5}; selected labels: {"yes": 5}.
Selected semantic audit: False; The supports are distinct and relevant, but they do not preserve enough evidence for the readout: frog presence and toilet presence separately cannot establish whether the frog is inside the toilet or partly placed there. The readout must infer placement not recorded by either support.
Proposed transactions: 3; rejected diagnostics: {}.
Final acceptance: {"qualified": false, "reasons": ["semantic_audit", "target_mismatch"], "policy": {"repeats": 5, "agreement": 0.8, "consistency": 0.8, "confidence": 0.8, "minimum_eligible": 3}}.

| Component | Visual input | Question | Final states | Lowest reported confidence |
|---|---|---|---|---:|
| n1 (support) | source and edited images | Is a frog visibly present in the edited image? | {"pass": 5} | 1 |
| n2 (support) | source and edited images | Is the toilet visibly identifiable in the edited image? | {"pass": 5} | 0.99 |
| n3 (requested) | saved evidence only | Based only on the saved observations and image-grounded evidence from both supports, was a frog added inside the toilet? | {"complete": 5} | 1 |

Measured scope usage, including preparation-independent search and final checks: {"search": 6, "final": 30, "completion_tokens_or_reserved": 3489, "input_tokens": 86089}.

## Interpretation limits

Forcing several calls does not guarantee a useful decomposition. A component set must record the relation or property needed for fulfillment, and its readout must preserve the original scoring rules. A rejected semantic audit remains a rejection even when observed labels match. Proposal-format failures limit what this test says about the effectiveness of structural repair. Confidence is reported by the model and is not calibrated probability. No final observations were used to change the frozen selected programs. Broad-versus-decomposed fidelity is recorded separately in scoring_fidelity.json.
