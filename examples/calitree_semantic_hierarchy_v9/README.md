# Frozen CaliTree semantic inference package

This deployment contains the reviewed M2 pooled fallback after M3–M7 rejected
all thirteen proposed AURORA merges. It scores 44/48 on local fitting sources,
24/48 in grouped development, and 9/12 on separate development. It is an
experimental result, not a final-test or production qualification.

`manifest.json` authenticates the JSON rules, upstream prompt text, compiler
schema, and model contracts. No training records, reference labels, source memberships,
or fitting-time Python objects are required for execution. Generic package
code from this repository is required.

```python
from critical.core.calibration.semantic_hierarchy.hierarchy_export_v9 import load
judge = load("examples/calitree_semantic_hierarchy_v9")
decision = judge.predict_bound(program, observation, image_pair_ref, interpretation)
```

Supply the existing two M1 outputs and one label-blind semantic interpretation.
A fresh case uses three upstream calls with the fixed GPT-6.1 Sol/high model,
SOURCE-first presentation, and one attempt per stage. Loading and executing
this package makes zero model calls. Missing evidence stays unresolved.

See [the study report](../../docs/calitree_m3_m7_semantic_hierarchy.md) for the
rejected parents, audit results, and limitations. The reserved final fifty are
outside this study.
