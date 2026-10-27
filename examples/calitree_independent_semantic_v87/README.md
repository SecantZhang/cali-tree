# Optional independent semantic expert

This opt-in policy adds a request-bound GPT-6.1 Sol judgment to the existing v72
semantic hybrid. The source-held cached replay scores225/276 (81.5%), two
corrections and no losses versus223/276. Only15 primary cases have valid cached
Sol views; this is not a complete or fresh Sol benchmark. The >85% goal is unmet.

`policy.json` contains two explicit review rules and the exact generic Sol
request contract. `rubric.txt` is its identical rendered gate text. In that text,
the independent "regular" judge means Sol; the original Luna judgment remains
part of the unchanged boosted base. No case/source/editor IDs or object-name
lookup rules enter selection.

Load the existing base artifacts and the new policy:

```python
import json
from pathlib import Path
from critical.core.calibration.visual_semantic_policy_v69 import VisualSemanticPolicy
from critical.core.calibration.semantic_rubric_runtime_v70 import SemanticRubricPolicy
from critical.core.calibration.independent_expert_v87 import IndependentExpertPolicy
from critical.core.optimization.prompt.calitree.independent_semantic_judge_v87 import IndependentSemanticJudge

root = Path("/absolute/path/to/calitree-mlsys")
load = lambda path: json.loads((root / path).read_text())
base = SemanticRubricPolicy(
    VisualSemanticPolicy(load("logs/exps/261021-frozen-visual-policy-v69/policy.json")),
    load("examples/calitree_semantic_hybrid_v72/rubric.json"),
)
policy = IndependentExpertPolicy(
    base, load("examples/calitree_independent_semantic_v87/policy.json")
)
judge = IndependentSemanticJudge(calls=None, policy=policy, encoder=None)
# Supply cached program/observation/interpretation/regular_judgment/vision_record
# to judge.judge(..., expert_record=record). Missing independent records retain
# v72; this class never calls Sol automatically.
```

`record_from_job` converts a completed durable generic-judge slot into a bound
record. The policy checks the instruction/program, ordered source/edited image
hashes, exact prompt/schema/model profile and execution hash. Retained failed
slots become absent records. The contrastive v75 pilot uses another prompt/schema
and Sol profile; its future outputs must not be passed to this generic contract.

`policy.review_bound(...)` identifies whether an independent judgment could
change the decision. It returns possible proposals and the existing base route,
never a new grade. This lets a caller inspect semantic routing before acquiring
another judgment. All99 original cached inputs request no independent review;
their decisions also survive all three hypothetical Sol labels in each fit.

Verification: `logs/exps/261023-verified-independent-expert-v87-r2` checks36 native
models, re-induces six gates and replays915 inputs through the actual bound judge.
See `docs/calitree_independent_semantic_v87.md` for scope and limitations.
