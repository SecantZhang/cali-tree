# Reconstructed semantic rubric with a boosted fallback

The verified hybrid improves the v69 development result from **222/276 (80.4%)
to 223/276 (80.8%)**, with one correction and no losses. It retains the original
99 examples and all 144 local slots in every fit, with unchanged 273/276 coverage.
This is a small source-held development gain after model selection, not a fresh
validation result or evidence of a substantial generalization improvement.

## Implemented representation

The student is an ordered list of short conjunctions over the existing bound
LLM evidence. Each rule has a named semantic condition, a grade and explicit
support from distinct fitting sources. Runtime rules contain no example IDs,
object names, learned numerical weights or reference lookups. Unmatched cases
retain the frozen boosted prediction. Invalid bound evidence retains the exact
regular fallback before any rubric is evaluated.

`SemanticRubric` searches up to three conditions per rule in v70. The v71
`WarrantedRubric` permits four conditions and imposes explicit grading warrants:

- No requires affirmative failure evidence: no meaningful requested progress,
  the wrong direction/target, or loss of an essential original instance.
- Partial requires meaningful progress, or an achieved outcome with an explicit
  endpoint, identity or collateral shortfall.
- Yes requires an achieved endpoint plus identity and collateral warrants.

Uncertainty, task type and neural similarity alone cannot justify a v71 grade.
Numerical vision comparisons retain their literal measurement descriptions;
they are not renamed into physical identity or success guarantees.

Teacher feature priorities guide candidate conditions. Reconstruction fits
teacher grades on each allowed training fold. Correction uses separate inner
source-excluded teacher predictions to identify mistakes, fitting human grades
only on that outer fold's training data. Every candidate is vetoed if it would
change any correct actual teacher prediction among the protected original 99.

The runtime is a semantic grading policy over existing LLM-interpreted evidence.
The prose rendering is inspectable but has not been tested as a standalone
LLM grading prompt. The ensemble remains in the hybrid; this is not a claim
that its entire function has been replaced by a compact rubric.

## Completed first comparisons

| Method | Correct /276 | Changes versus v69 | Original cases | Coverage |
|---|---:|---:|---:|---:|
| Frozen v69 | 222 | — | 99/99 | 273 |
| v70 semantic reconstruction | 220 | 0 gains, 2 losses | 99/99 | 273 |
| v70 grounded reconstruction | 223 | 1 gain, 0 losses | 99/99 | 273 |
| v70 auxiliary-vision reconstruction | 222 | 1 gain, 1 loss | 99/99 | 273 |
| v71 warranted reconstruction, all three vocabularies | 222 | no prediction changes | 99/99 | 273 |

The v70 one-case improvement is not promoted: its decisive clause used an
unestablished identity predicate rather than affirmative identity-failure
evidence. This is a useful example of why semantic feature names alone do not
make the grading justification adequate. V71 explicitly blocks this shortcut.

The warranted reconstructions directly resolve 29/276 semantic-only, 20/276
grounded, and 33/276 auxiliary cases, retaining the teacher elsewhere. All five
source folds and the full fit retain the original 99. These are partial rubric
reconstructions, not whole-ensemble equivalence certificates.

## Verified warranted correction

All 30 inner teacher fits completed. Every corresponding outer evaluation
source and its sibling edits is absent from those fits. The three warranted
correction vocabularies get 222/276 semantic-only, 222/276 grounded, and
**223/276 with auxiliary visual measurements**. The last arm is selected.

The single corrected source-held case is T09M2, requesting a Gustav Klimt style.
The boosted policy and regular judge give Partial; the human reference is No.
Fold 3's rubric gives No when the teacher proposes Partial, the physical style
intermediate checks explicitly fail, the semantic interpretation establishes
only incidental change, and the lower-quartile patch comparison does not meet
the 0.9 threshold. The visual measurement scopes the clause; it is not treated
as proof of style or correctness. Two distinct training sources support it.

The final full-data rubric is a different, single No-to-Partial exception:
all requirements show progress toward the requested goal, all allow replacement,
and the median patch comparison does not meet 0.9. Its redundant replacement
"any" condition is removed because "all" implies "any" for validated nonempty
requirements. V72 proves each per-field simplification by enumerating all
nonempty sets of categorical states. The final rubric has three evidence
conditions plus the teacher-grade guard, with a boosted fallback.

Cross-validation learns a separate rubric in each fold. The final teacher
already fits the style case correctly. Its full-data rubric does not fire on
the 915 fitting cases, whose predictions remain unchanged. **80.8% estimates
the source-held learning procedure; it is not a fresh evaluation of that final
all-data artifact.**

The independent audit cold-loads and checks all 36 native teacher models,
re-induces all six selected rubrics, verifies original-case/144-slot retention,
checks source exclusions and absence of reserved-source overlap, certifies
all/any simplification, and replays all 915 inputs through the high-level bound
judge. Every prediction and coverage decision matches the compiled policy.
All 50 focused new and related existing tests pass.

## Commands and evidence

```bash
PYTHONPATH=/tmp/calitree-catboost-v62:. /path/to/python -m run.calitree_semantic_rubric_v70 \
  --output-dir logs/exps/NEW_RECONSTRUCTION
PYTHONPATH=/tmp/calitree-catboost-v62:. /path/to/python -m run.prepare_calitree_rubric_teachers_v70 \
  --output-dir logs/exps/261023-rubric-inner-teachers-v70 --workers 3
PYTHONPATH=/tmp/calitree-catboost-v62:. /path/to/python -m run.calitree_warranted_rubric_v71 \
  --output-dir logs/exps/NEW_WARRANTED_RUN --correction
PYTHONPATH=/tmp/calitree-catboost-v62:. /path/to/python -m run.verify_calitree_semantic_rubric_v72 \
  --study logs/exps/261023-warranted-rubric-v71-r2 \
  --output-dir logs/exps/NEW_INDEPENDENT_AUDIT
```

The warranted runner consumes the immutable outer teacher cache in
`261023-semantic-rubric-v70-r1` and the prepared inner cache above. Native models
are fitted locally; no model API is called. The exact initial v70 sources are
archived with its experiment because a later extension adds grade-specific
semantic-warrant hooks without changing v70's default behavior.

The first run's numpy-integer reporting failure is archived separately. Its
teacher was reused after converting the reporting scalar to a Python integer;
no model request or paid call was retried.

Verified artifacts are in `logs/exps/261023-verified-semantic-hybrid-v72-r1`:

- `rubric.json` and `rubric.txt`: executable and readable final correction rule.
- `verification.json`: source-held comparison and audit counts.
- `predictions.json`: all 276 source-held outcomes including fallbacks.
- `runtime_predictions.json`: all 915 high-level bound inference replays.
- `fold*/equivalence.json`: exact semantic simplification certificates.

## Reusable inference

```python
from critical.core.calibration.visual_semantic_policy_v69 import VisualSemanticPolicy
from critical.core.calibration.semantic_rubric_runtime_v70 import SemanticRubricPolicy
from critical.core.optimization.prompt.calitree.semantic_rubric_judge_v70 import SemanticRubricJudge

teacher = VisualSemanticPolicy(teacher_artifact)
hybrid = SemanticRubricPolicy(teacher, rubric_artifact)
judge = SemanticRubricJudge(calls, hybrid, encoder)
result = judge.judge(instruction, evidence)
```

Use the existing v69 encoder recipe and authorized call interface. Cached
program/observation/interpretation/regular/vision stages can be supplied exactly
as for v69. Semantic conditions execute locally over the bound LLM evidence;
no LLM request occurs per rule. The runtime pins the teacher, checks the rubric's
rendered text against its executable conditions, preserves failed-slot fallback,
and keeps teacher scores separate when a rubric changes its grade.

Serving defaults are unchanged. The ensemble remains the fallback. A standalone
prose-only LLM execution or a full compact replacement of all 1,200 trees has
not been established. No new paid calls were made; all 80 reserved sources remain
unused.
