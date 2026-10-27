# Semantic rubric with the frozen v69 teacher

`rubric.json` is the verified executable full-data correction rubric;
`rubric.txt` is its matching readable form. Load it with
`SemanticRubricPolicy(VisualSemanticPolicy(teacher_artifact), rubric_artifact)`
and use `SemanticRubricJudge` with the existing v69 encoder and call interface.
The teacher artifact is
`logs/exps/261021-frozen-visual-policy-v69/policy.json`. Its identity is pinned
inside the rubric; a different teacher is rejected.

The source-held learning procedure scores 223/276 versus v69's 222/276, with
one gain and zero losses, unchanged coverage and all 99 original cases retained.
Each fold learns its own rubric. The final all-data rubric differs and does not
fire on the 915 fitting examples; it preserves their existing predictions.
This is a development estimate after selection, not fresh final validation.

The final exception has three evidence conditions plus a teacher-grade guard.
It executes over validated instruction-relative LLM evidence. If no rule
matches, retain the boosted teacher. Invalid or missing bound evidence retains
the original regular fallback. Similarity thresholds remain measurements rather
than physical-fact guarantees. The ensemble is still required; standalone
prose-only LLM rubric execution has not been established.

See `docs/calitree_semantic_rubric_v70.md` and
`docs/experiments/calitree_semantic_hybrid_v72_completion.json` for methods,
commands, verification and limitations. No new paid calls or serving changes
were made.
