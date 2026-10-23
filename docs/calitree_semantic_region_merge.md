# Semantic merging of regions across experts

The opt-in v28 search merges similar regions even when their conditions are not
logically equivalent. It reduces the v27 bank from 63 to 44 region definitions
while preserving all measured local predictions and coverage decisions. Seven
final regions combine contributions from multiple experts.

This merges **applicability regions**, not expert trees. The nine frozen expert
trees across the three alternative split banks and their full-bank consensus and
rejection logic remain unchanged.

## Candidate construction

Two regions are eligible when they:

- Predict the same overall verdict.
- Have different sets of contributing experts.
- Overlap in at least one supported structural task scope.
- Have literal-set Jaccard similarity of at least 0.5.
- Share a non-boilerplate semantic or outcome condition.

Similarity is computed from the existing named semantic evidence predicates and
task contracts. There is no new LLM or embedding call. Sharing a label alone is
insufficient. Candidate pairs are ordered by literal similarity multiplied by
task-scope similarity, with deterministic ties.

A proposed parent retains the **intersection of child evidence conditions** and
the **union of permitted task scopes and contributing experts**. This may admit
feature combinations outside either original region. It does not introduce
unobserved task types or invent a new verdict.

## Acceptance and inference

Every proposal must retain each child's locally supported sources and every
original local prediction. It must also preserve all 98 recorded accept/defer
decisions and accepted verdicts per split. Those routing probes include known
development cases: their frozen routing decisions constrain selection, while
human development labels are not read by the merge search. They are therefore
regression data, not held-out validation.

Among passing candidates, selection prefers fewer definitions, fewer conditions,
more pooled local support, more contributing experts, then semantic similarity.
The predeclared limits are 32 rounds and 64 tested candidates per round. The
real runs terminate after 9, 6 and 4 accepted merges, respectively.

At inference, an accepted merged region requires:

1. A supported structural task scope and matching shared evidence conditions.
2. Acceptance and agreement from the unchanged full expert-bank gate, including
   all existing counterexample and merge-abstention checks.
3. At least one **contributing expert** supplying a supported match for that
   verdict. An unrelated expert cannot authorize the merged region.

Failure falls back to the regular judge. The old region bank is not retained as
an executable veto. The runtime uses a new v28 wrapper around the generic shared
condition executor, containing only the new region definitions plus the frozen
expert bank. `expert_refs` identifies contributing experts, not separately called
language models or a new averaged vote.

## Results

These totals describe three alternative split banks, not one combined deployment.

| Split | Regions before → after | Accepted merges | Final cross-expert regions | Local correct | Development correct |
|---:|---:|---:|---:|---:|---:|
| 1 | 24 → 15 | 9 | 2 | 48/48 | 39/50 |
| 2 | 24 → 18 | 6 | 3 | 48/48 | 40/50 |
| 3 | 15 → 11 | 4 | 2 | 48/48 | 36/50 |
| Total | **63 → 44** | **19** | **7** | **144/144** | **115/150** |

- Evidence-condition occurrences: **2,232→1,382**, a 38.1% reduction.
- Canonical serialized bytes, including the core gate and support metadata:
  **206,094→189,355**, an 8.1% reduction.
- Pooled single-example regions: **14→8**.
- Task-to-region links: **149→121**; single-example task links **117→86**.
- All **294 recorded routes and final predictions** remain unchanged, including
  all **115 exact regular fallbacks** and all twelve original batches at 12/12.
- No new acceptances, deferrals or changed accepted verdicts occur on the recorded
  cases. The three earlier v26 deferrals remain; this preserves 115/150 rather than
  restoring the older 116/150 score.

The search evaluates 76 candidate replacements and selects 19. All real candidates
that passed the similarity eligibility criteria also passed the recorded route
checks; a targeted synthetic test verifies that a locally accurate candidate is
rejected when it would newly accept a known deferred case.

Support counts are recomputed from original local examples and require actual
supported contributor matches. They are deduplicated by source and reported both
for the pooled region and each task scope. The same data support broader shared
regions; these reductions are not additional independent observations.

## What is and is not guaranteed

Old regional Boolean coverage is contained in the new regional union. Intersecting
conditions and unioning scopes/contributors retains child applicability. The
reverse implication fails in all three splits: regional conditions are genuinely
broader than exact deduplication permits.

This does not prove improved unseen-case accuracy, or even that every additional
Boolean combination will pass the full-bank veto. Unseen inputs can be accepted
where the previous region gate would have deferred. Local accuracy and known
routing are protected; universal equality to the old region function is explicitly
not claimed. This remains opt-in.

## Verification and reproduction

The final audited run is `logs/exps/261020-semantic-region-merge-v28-r2`. Earlier
unpromoted drafts and source snapshots are retained in the corresponding base
and `-r1` directories. The final version additionally requires a supported match
from a contributing expert.

The audit reproduces candidate ordering, all tested replacements and all accepted
merges with reversed local row order, recounts pooled/per-task support, verifies
unchanged expert/veto artifacts, and replays all 294 cases. Tests cover real
cross-expert widening, local retention, rejection of a newly accepted regression
probe, ignored reference labels in routing probes, contributor requirements,
deduplication, serialization and the unchanged full-bank veto.

```bash
PYTHONPATH=. python run/calitree_semantic_region_merge_v28.py \
  --parent-run logs/exps/261020-shared-regions-v27-r1 \
  --output-dir logs/exps/261020-semantic-region-merge-v28-r2
PYTHONPATH=. python run/calitree_semantic_region_merge_v28.py \
  --verify --output-dir logs/exps/261020-semantic-region-merge-v28-r2
```

Use a fresh output directory for a new build. No model calls or reserved final-set
predictions are made. Existing inference defaults are unchanged.

```python
import json
from critical.core.calibration.semantic_region_merge_v28 import SemanticMergedRegionGate
from critical.core.optimization.prompt.calitree.bound_evidence_cache import CachedEvidenceCoveredJudge

gate = SemanticMergedRegionGate(json.load(open('examples/calitree_semantic_region_merge_v28/split2_gate.json')))
judge = CachedEvidenceCoveredJudge(calls, gate, cache, identity=model_identity)
result = judge.judge(instruction, evidence, case_id=request_id)
for ref in result['route'].get('semantic_regions', []):
    explanation = gate.definition(ref)
```

Rebuild regions after changing expert trees. Do not treat task shortlisting as
permission to bypass evidence, contributing-expert or full-bank checks.

All **116 focused tests pass**. The final audit reproduces **19 accepted merges**
and **76 candidate checks**, preserves all **294 recorded routes and predictions**
and **115 exact regular fallbacks**, and confirms the expert trees and veto are
unchanged. Results and audit are exported under `docs/experiments/`.
