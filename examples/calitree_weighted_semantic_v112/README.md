# Selected CaliTree v112

v112 is the selected AURORA inference version as of 2026-10-25. The default
selector is `critical/core/calibration/artifacts/calitree_current.json`; its
component artifact identities are checked when the policy is loaded.

This is the exactly compressed form of the verified v105 policy:60 shared
terms instead of100 branches,33 individual conditions and27 interactions over
28 named concepts. Source-held development accuracy stays227/276 (82.2%),
with67.9% balanced accuracy.
All99 original decisions,144 original slots, coverage and routing are retained.
The >85% goal is unmet.

The default Python entry point loads the complete frozen stack:

```python
from critical.core.optimization.prompt.calitree import CaliTreeJudge

judge = CaliTreeJudge()
# Supply cached program/observation/interpretation/regular_judgment/
# vision_record/expert_record/local_record to judge.judge(...).
# Results include pipeline_version="v112" and the selected policy_ref.
```

Construction makes no model calls. Fresh integrations explicitly supply the
existing `calls`, `encoder`, and matching `observer` interfaces. Missing local
observations retain the preceding policy; explicit `local_record=None` never
triggers another attempt. Optional Sol records are supplied by the caller;
this loader does not acquire a new Sol judgment.

Inspect the selected version or execute cached requests:

```bash
python -m run.calitree_current --describe
python -m run.calitree_current --input cached_requests.json --output-dir NEW_RUN
```

The input is a nonempty JSON list. Every request explicitly supplies
`instruction`, `evidence`, `program`, `observation`, `interpretation`,
`regular_judgment`, and `vision_record`; optional fields are `case_id`,
`expert_record`, and `local_record`. Use null for a retained failed stage.
References and unknown fields are rejected. This CLI makes no provider,
encoder, or local-observer calls.

Manual explicit-version loading remains available as in
`examples/calitree_weighted_semantic_v105/README.md`, with the final policy
path `examples/calitree_weighted_semantic_v112/policy.json`. The runtime API,
positive-warrant/independent-review guard, prior-rule priority and exact local
observer profile are unchanged. This artifact uses the old Qwen3-VL8B256-image-
token/256-output profile; it cannot accept records from the separate v108 or
candidate MLX profiles.

`rubric.txt` is generated from the executable weights/conditions. Terms are
conditional adjustments combined with the teacher's supports, not independent
natural-language grading commands. The common task/preservation warrants still
constrain any changed grade.

Verification re-induces six native models, checks5,490 residuals and executes915
real bound cached judgments. It proves equivalence to the prior policy, not a
new accuracy gain or unchanged generalization from a changed function. See
`docs/calitree_semantic_compression_v112.md` for details and negative12/24-term
alternatives. The separate default-selection replay in
`logs/exps/261025-selected-v112-r1` reproduces all915 bound cached predictions,
coverage and source routes through `CaliTreeJudge`, without fitting or model
calls. The earlier audit's `serving_defaults_changed=false` describes the
original compression experiment; the subsequent default selection is v112.

The later [balanced-accuracy search](../../docs/calitree_balanced_accuracy_v148.md)
finds an exploratory four-rule extension with71.1% balanced accuracy, but its
Partial recall falls53.6%→42.9%. That extension is not selected; the default
remains this exact v112 policy with67.9% balanced accuracy.
