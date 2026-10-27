# Optional guarded weighted semantic review

Verified227/276 development accuracy;99/99 original decisions,144/144 original
slots and273/276 coverage retained. The >85% goal is still unmet. This artifact
adds bound local Qwen task/preservation evidence and100 weighted clauses to the
existing v87 policy. It makes no independent API call per predicate or clause.

```python
import json
from pathlib import Path
from critical.core.calibration.visual_semantic_policy_v69 import VisualSemanticPolicy
from critical.core.calibration.semantic_rubric_runtime_v70 import SemanticRubricPolicy
from critical.core.calibration.independent_expert_v87 import IndependentExpertPolicy
from critical.core.calibration.semantic_residual_runtime_v104 import SemanticResidualPolicy
from critical.core.optimization.prompt.calitree.semantic_residual_judge_v104 import SemanticResidualJudge

root = Path('/absolute/path/to/calitree-mlsys')
load = lambda path: json.loads((root / path).read_text())
teacher = VisualSemanticPolicy(load('logs/exps/261021-frozen-visual-policy-v69/policy.json'))
semantic = SemanticRubricPolicy(teacher, load('examples/calitree_semantic_hybrid_v72/rubric.json'))
base = IndependentExpertPolicy(semantic, load('examples/calitree_independent_semantic_v87/policy.json'))
policy = SemanticResidualPolicy(base, load('examples/calitree_weighted_semantic_v105/policy.json'))
judge = SemanticResidualJudge(calls=None, policy=policy, encoder=None)
# Supply all cached program/observation/interpretation/regular_judgment/
# vision_record inputs to judge.judge(..., expert_record=..., local_record=...).
# Missing/foreign local records keep the existing decision. No model is called.
```

For fresh local observations, construct a logged`LocalQwenGrammarEngine` with
the pinned checkpoint and the exact exported observer profile. Wrap it in
`LocalObserver` from`critical.core.decision.local_observer_v99` and pass it as
`observer=` to the judge. An omitted`local_record` then permits one joint local
observation only inside the review region. Explicit`local_record=None` means a
known unavailable observation and never triggers another attempt. The previous
vision/extraction inputs still need the normal pipeline; this wrapper does not
replace upstream evidence extraction.

The exported artifact uses the256-visual-token/256-output profile, not the
separate v108 high-resolution experiment. Never pass records from a different
profile. The runtime validates program, ordered image pair, prompt and model
identity. A new checkpoint file location is allowed only when its compute file
hashes match. All weights/conditions/descriptions are content-bound and replayed
against the native models; old teacher support is nested under the prior route
when a new grade is selected.

See`docs/calitree_weighted_semantic_v105.md` for paired changes, statistical
limits and the full audit. Serving defaults are unchanged.
