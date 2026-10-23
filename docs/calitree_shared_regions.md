# Simplified and shared semantic region definitions

The v27 compiler consolidates duplicate evidence definitions while preserving the
v26 region gate's decision coverage exactly. It is opt-in; the existing experts,
model prompts and default inference path are unchanged.

## How simplification works

A v26 region combines a structural task scope, one expert's evidence rule and a
complete tree path. The compiler expands that definition into a conjunction of
all path predicates, evidence guards and semantic-support predicates. It removes
repeated literals and uses the resulting evidence conjunction plus verdict as a
canonical key, independent of task scope, expert identity and traversal order.

Identical keys share one definition, with an explicit set of permitted task
scopes and links to contributing experts. Two exact Boolean simplifications are
also supported:

- Absorption: `A OR (A AND B)` becomes `A`.
- Complementary branches: `(A AND B) OR (A AND NOT B)` becomes `A`.

These operations apply only to matching verdicts and common task scopes. The
compiler does not assume that different predicates are equivalent because they
happen to agree on training examples. It does not combine arbitrary regions
merely because they predict the same label. A bounded symbolic verifier proves
both directions of the regional union for every task scope and verdict; failure
or proof-budget exhaustion prevents publication.

The runtime evaluates the simplified conjunctions against the extracted Boolean
evidence. It retains the frozen v24 full-bank consensus and rejection gate. It
**does not embed or execute the old v26 region bank as a hidden veto**. Therefore,
coverage preservation follows from the equivalent compiled definitions, not from
running both region systems and forcing the old answer.

## Support and sharing

The compiler counts each original local source once per shared definition. It
also stores separate support counts for every permitted task scope. A larger
pooled support count is not presented as repeated support for each task type.
The runtime contains support counts, not source IDs or lookup tables of examples.

Equivalent definitions can link to multiple experts. A synthetic test constructs
two distinct expert trees with equivalent evidence regions and verifies that the
compiler stores their shared definition once without double-counting examples.
The real three-split bank contains **no exactly equivalent cross-expert evidence
kernels**, so no real cross-expert pooling occurred. Its observed consolidation is
across task scopes within experts. No complementary-branch simplification was
applicable to these real definitions either; their reduction comes from canonical
deduplication and pooling of identical evidence conditions.

Conditions are stored once in a shared literal table and referenced by integer
indices. Task profiles are also stored once. The `definition(ref)` API expands
these references into readable task scopes and predicate descriptions.

## Measured results

These totals cover three alternative split-specific banks, not one bank deployed
with all three splits combined.

| Split | Evidence definitions before → after | Definitions with one pooled source before → after | Canonical JSON bytes before → after | Local accuracy |
|---:|---:|---:|---:|---:|
| 1 | 51 → 24 | 42 → 8 | 90,233 → 86,068 | 48/48 |
| 2 | 62 → 24 | 49 → 4 | 87,893 → 75,149 | 48/48 |
| 3 | 36 → 15 | 26 → 2 | 51,129 → 44,877 | 48/48 |
| Total | **149 → 63** | **117 → 14** | **229,255 → 206,094** | **144/144** |

Evidence definitions fall by 57.7%, and canonical serialized artifact size falls
by 10.1%, including the retained core gate and per-task support metadata. Expanded
evidence-condition occurrences fall 5,292→2,232. This latter measure describes
expanded rule definitions; it is not a model-call or latency measurement.

**The task-conditional support sparsity remains unchanged:** there are still 149
task-to-definition links, including 117 with one supporting source. Pooling makes
the repeated evidence logic smaller and easier to inspect; it does not create
new training evidence or broaden coverage. The decrease to 14 singleton shared
definitions must not be interpreted as resolving the 117 thin task-specific
support links.

All 144 local predictions and all twelve original batches at 12/12 are preserved.
All 294 recorded accept/defer decisions and final predictions match v26, including
all 115 exact regular fallbacks. There are zero new acceptances, zero new deferrals
and zero changed accepted verdicts. Development accuracy remains **115/150**.
The three deferrals introduced by v26 remain; this change does not restore the
older v24 score of 116/150.

## Verification and scope

The audit rebuilds the compiler from local data in reverse row order, checks
source/code hashes, independently recounts pooled and per-task support, verifies
298 Boolean cube implications, and replays all 294 raw/cached cases. All 105
focused unit/regression tests pass, including exhaustive small Boolean-domain
checks, cross-expert deduplication, scope separation, disagreement preservation,
serialization and support-count checks.

The Boolean proof establishes equivalence of the regional coverage functions
under the frozen feature and task contracts, not correctness of the underlying
judge on unseen images. Global consensus and rejection checks remain required.
There are no new model calls or reserved final-set predictions.

The initial expanded-condition draft increased serialized size. Its outputs and
source snapshots remain in `logs/exps/261020-shared-regions-v27`. The final shared
literal-table run is `logs/exps/261020-shared-regions-v27-r1`; that is the audited
and sealed result referenced here.

## Usage

```python
import json
from critical.core.calibration.shared_regions_v27 import SharedRegionGate
from critical.core.optimization.prompt.calitree.bound_evidence_cache import CachedEvidenceCoveredJudge

gate = SharedRegionGate(json.load(open('examples/calitree_shared_regions_v27/split2_gate.json')))
candidates = gate.shortlist(compiled_program)  # candidates only; decision_ready=False
judge = CachedEvidenceCoveredJudge(calls, gate, cache, identity=model_identity)
result = judge.judge(instruction, evidence, case_id=request_id)
for ref in result['route'].get('semantic_regions', []):
    definition = gate.definition(ref)  # includes pooled and per-task support
```

Rebuild regions after changing experts. The simplifier binds to the original
expert bank; it is not a merge learner or a replacement for evidence extraction.

```bash
PYTHONPATH=. python run/calitree_shared_regions_v27.py \
  --parent-run logs/exps/261020-semantic-regions-v26 \
  --output-dir logs/exps/261020-shared-regions-v27-r1
PYTHONPATH=. python run/calitree_shared_regions_v27.py \
  --verify --output-dir logs/exps/261020-shared-regions-v27-r1
```

Use a fresh output directory for a new run. Compact results and the audit are
saved under `docs/experiments/calitree_shared_regions_v27.json` and
`docs/experiments/calitree_shared_regions_completion_audit.json`.
