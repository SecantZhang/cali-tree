# Frozen router-free CaliTree union judge

One semantic policy learned from eight six-case AURORA groups through seven
accepted merges. Local fit is 46/48 (95.8%); a historically exposed separate
development cohort scores 10/12. The final fifty remain unevaluated.

The final root uses only its immediate children's predicates: fourteen terminal
rules over eleven semantic predicates. Five lower-level merges required
full-grammar repair. This is local consolidation and final-root predicate reuse,
not a claim of universal semantic correctness or statistical robustness.

`manifest.json` authenticates `judge.json`, the upstream prompts, and the
compiler schema. There is one inference policy and no router. No source
membership, fitting data, or reference labels are required at inference.

```python
from critical.core.calibration.semantic_hierarchy.union_runtime_v11 import load
judge = load("examples/calitree_union_reuse_v11")
decision = judge.predict_bound(program, observation, image_pair_ref, interpretation)
```

The upstream stages remain the same three single-attempt GPT-6.1 Sol/high passes:
compile checks, observe SOURCE/EDITED, interpret evidence. Executing this package
makes no model call and performs no optimization. Generic code from this
repository is required; training experiment logs are not.

See [the full report](../../docs/calitree_router_free_union_merging.md) for data,
gates, controls, source lineage, and limitations.
