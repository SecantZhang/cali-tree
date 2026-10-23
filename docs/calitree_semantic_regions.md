# Semantic rule regions and expert routing

The v26 prototype makes each expert's supported task-and-evidence regions
explicit. It is opt-in and preserves the deployed trees and their verdicts.

## Two stages of coverage

1. **Task shortlisting:** use the compiled outcome kinds and desired truth states,
   whether identity correspondence is required, and whether the request is
   compound. The result identifies candidate regions and experts. It never claims
   that a decision is ready.
2. **Decision coverage:** require an exact terminal path, the original evidence
   guards and semantic-support conditions, and all existing counterexample and
   merge-abstention checks. The full frozen expert bank must first accept and
   agree. Only then can a locally supported region authorize that same verdict.

For example, a spatial-relation task can shortlist experts with supported spatial
regions. The image evidence must still establish a supported path and satisfy its
other checks. Similar task wording alone cannot establish correctness. A new
object name can share a structural task profile; an unsupported task/path
combination falls back to the regular judge.

The full-bank veto is intentional: excluding an expert from the semantic shortlist
must not hide a disagreement that previously caused a fallback. This first
implementation therefore does not claim fewer tree executions or model calls.
It is a routing/coverage interface with conservative decision semantics, not a
latency optimization or a trained LLM router.

## Region definition

Each region contains:

- A structural task scope, with no object names or case IDs.
- An expert reference, frozen evidence-rule reference, and complete root-to-leaf
  path. Ancestor conditions remain attached.
- The conditional overall No/Partial/Yes verdict.
- A deterministic semantic description and descriptions of all path predicates,
  evidence guards and semantic-support conditions.
- Counts of supporting local sources, distinct instructions and original batches.

The region means the conjunction of these conditions, subject to the global
rejection checks. Experts still predict the overall judgment; the interface does
not blend separate dimension scores. Region artifacts contain counts, not local
case membership lists. Reference labels are used offline to establish correct
support and are never inference inputs.

To retain local coverage, an exact task/path region may have only **one** local
supporting example. Its inherited broader evidence rule has multiple-source
support, but that does not establish repeated support for this narrower region.
The counts are exposed explicitly; they are not confidence probabilities.

## Results

All regions were built from each split's 48 local examples before development
replay. No development labels were used to create or broaden regions.

| Split | Experts | Task scopes | Regions | Single-example regions | Local accuracy | Development accuracy before → after |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 4 | 12 | 51 | 42 | 48/48 | 40/50 → 39/50 |
| 2 | 3 | 13 | 62 | 49 | 48/48 | 40/50 → 40/50 |
| 3 | 2 | 12 | 36 | 26 | 48/48 | 36/50 → 36/50 |

- All **144 local predictions** and all twelve original batches at 12/12 remain
  correct, using raw inputs with cached extraction and renamed request IDs.
- Three development cases become new deferrals: N071 in split 1, N070 in split 2,
  and N110 in split 3. They were all correct tree acceptances. The regular judge
  is wrong on N071 and correct on the other two; total score changes **116→115/150**.
- Accepted development coverage changes 38→35/150. All old deferrals retain the
  same exact regular response. No old deferral becomes an acceptance, and no
  retained tree acceptance changes verdict.
- The region layer adds metadata and restrictions; it does not compress or merge
  the experts. There are 149 regions, including 117 supported by one example.
  Exact task/path grouping is therefore fairly fragmented.

The prototype makes coverage inspectable and preserves local accuracy, but the
stricter gate is not an overall accuracy improvement. Keep it opt-in. Coarsening
regions or requiring more independent support would be a separate experiment
with local retention checks, not an implicit change to this result.

## Usage

```python
import json
from critical.core.calibration.semantic_regions_v26 import SemanticRegionGate
from critical.core.optimization.prompt.calitree.bound_evidence_cache import CachedEvidenceCoveredJudge

gate = SemanticRegionGate(json.load(open('examples/calitree_semantic_regions_v26/split2_gate.json')))
candidates = gate.shortlist(compiled_program)  # decision_ready is always False
# Existing evidence/caching pipeline; no additional LLM routing call.
judge = CachedEvidenceCoveredJudge(calls, gate, cache, identity=model_identity)
result = judge.judge(instruction, evidence, case_id=request_id)
for ref in result['route'].get('semantic_regions', []):
    explanation = gate.definition(ref)
```

Use `gate.export()` for serialization and `SemanticRegionGate(...)` to restore.
Rebuild regions from local examples after changing the expert bank; existing
region bindings must not be copied onto a different parent tree.

```bash
PYTHONPATH=. python run/calitree_semantic_regions_v26.py \
  --parent-run logs/exps/261019-pairwise-merge-v24-r1 \
  --output-dir logs/exps/261020-semantic-regions-v26
PYTHONPATH=. python run/calitree_semantic_regions_v26.py \
  --verify --output-dir logs/exps/261020-semantic-regions-v26
```

Use a fresh output directory for a new build. The independent replay refits every
region with reversed row order, checks source/code hashes, replays 294 cases and
validates local preservation and rejection monotonicity. All 96 focused tests
pass. There are zero new model calls and zero reserved final predictions. No
default inference path changed. Results concern cached evidence and known
regression cases, not a calibrated probability of correctness on unseen inputs.
