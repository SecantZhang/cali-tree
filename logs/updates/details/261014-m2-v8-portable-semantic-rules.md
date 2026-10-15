# M2 v8: case-independent semantic rules under the clarified objective

- User accepted local accuracy above 90% and clarified that generalizability
  means rules should not be specific to the case input; held-out accuracy is a
  future large-corpus question rather than this goal's acceptance gate.
- Added a closed portable vocabulary: instruction operation kinds, semantic
  progress/endpoints/materiality, and any/all physical evidence states. Removed
  raw check cardinalities, majority thresholds, case/object/instruction literals,
  pixel coordinates, and exact observed-case signature routing.
- Compact portable fit reaches 46/48. A generic training-time semantic review
  removes an explicit core-endpoint-missing => Yes exception, yielding the
  recommended 44/48 (91.7%) policy: fourteen rules, thirteen predicates, at least
  two distinct sources and instruction texts per rule. A deeper unreviewed
  portable fit reaches 47/48 and is preserved as a fitting diagnostic.
- Exported a deployment-only rule artifact with no source IDs, training records,
  or fitting labels. Replacing all source/batch identifiers and reversing row
  order produces identical deployed content. All 515 equivalent-check variants
  preserve portable features, predictions and traces with semantic interpretations
  held fixed.
- 147 scoped tests pass. Independent audit recomputes all 48 predictions and
  checks source support, field whitelists, exact review replay, and rule syntax.
- This goal used 59 explicitly approved GPT-6.1 Sol/high text-only calls over
  cached M1 physical evidence (47 training, 12 development). All were valid, with
  no new image presentations, labels in payloads, or final-fifty calls.
- Preserved the earlier negative transfer experiments: physical nested selection
  21/48, interpretation-based nested selection 18/48, and a scoped candidate
  25/48 on held-out groups but 7/12 on frozen supplementary development versus
  v4's 9/12. V8 is not promoted on a statistical-generalization claim.
- Added reproducible reviewed-policy export, a strict deployment executor,
  rule-support examples, semantic review, call accounting and portability audits.
  Larger-corpus accuracy and full-model paraphrase/repeat robustness remain open.
- Report: `docs/calitree_m2_portable_semantic_v8.md`.
