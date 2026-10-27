# Shared semantic factors for the boosted backbone

**Implemented and verified without new observations or fitting.** The full
visual backbone's1200 trees compress to513 shared semantic factors. Canonical
serialized scoring bytes fall5,672,915→2,275,487 (59.9%). V112 and V144 retain
their existing predictions, protected local accuracy, coverage and routing in
the source-fold and high-level cached replays. V112 remains the selected default.

## What is merged

A tree is a three-score function of its named Boolean checks. Trees testing
the same predicates can use different test orders. Canonicalizing the order
aligns their leaf coordinates, after which all three class contributions can
be added into one shared factor:

```text
Tree A: contribution f(completion, identity, preservation)
Tree B: contribution g(preservation, completion, identity)
                    ↓ align Boolean coordinates
Shared factor: h(completion, identity, preservation) = f + g
```

Every source tree contributes exactly once. The compiler stores all nonzero
leaf vectors and treats only exactly zero entries as zero. It does not round
weights, prune small contributions, use labels, infer equivalence from equal
fitting columns, or merge merely similar conditions. The feature descriptions
remain attached to the shared factor vocabulary.

This is exact sharing of equivalent semantic predicate structure, not a new
abstract judging rubric. A factor is a conditional contribution to No/Partial/
Yes scores, not an independently authoritative grade. The runtime still
combines all matching factors, then uses the original scale and softmax.

## Full-data backbone complexity

| Measure | Original | Merged | Reduction |
|---|---:|---:|---:|
| Trees / shared factors |1200|513|57.3%|
| Per-input condition occurrences |9574|4095|57.2%|
| Stored class-score scalars |915168|89550|90.2%|
| Canonical scoring representation bytes |5672915|2275487|59.9%|

Byte counts include the same declared feature names and used semantic
descriptions. This measures the scoring representation, not the whole pipeline
bundle. Fewer condition evaluations and stored parameters are established;
wall-clock latency and peak memory reductions have not been benchmarked.
Evidence extraction, image encoding, the semantic correction layers and LLM
request counts do not change. Predictive capacity is unchanged in real arithmetic.

The five source-held backbones compress to471/484/496/489/529 factors. The
full-data model uses513. No alternative is selected by its evaluation score.

## Accuracy and routing

| Policy with original or merged backbone | Correct /276 | Overall | Balanced |
|---|---:|---:|---:|
| V112 |227|82.2%|67.9%|
| V144 candidate |226|81.9%|71.1%|

All99 original cases and144 local slots remain correct in each of six
contexts. Upstream coverage remains273/276; regular fallbacks are unchanged.
The original semantic and independent-expert routes retain priority. Review
eligibility, the V112 residual's Boolean context and native residual outputs,
V144 first-match corrections and all final cached predictions are rechecked.

The source-held figures retain their previous development status; compression
does not constitute a fresh accuracy/generalization evaluation. It does not
broaden semantic regions or introduce new accepted task types.

## Numerical and verification scope

Independent table verification visits all760368 Boolean assignments across
the shared factors in six models. It independently maps each assignment back
to the original trees and checks the summed score vectors and complete source
membership. Factor-wise equality implies equality of the total additive
function over its Boolean domain in real arithmetic.

Floating-point addition order changes. Scores are not claimed bit-identical:
maximum class-support difference against cached native scores is2.28e-15;
scalar and high-level route differences are at most1.78e-15. The acceptance
tolerance is1e-12. An unseen input exactly at a numerical decision threshold
is not covered by a bitwise-equivalence guarantee.

The audit additionally verifies:

- 5490 scalar/native cases across six models.
- 6664860 unchanged Boolean context values.
- 10980 V112/V144 final predictions.
- 915 complete bound requests through the actual high-level judge, comparing
  judgments, rationales, sources and every route field, with tolerance only for
  floats. The verification substitutes the compact scorer while retaining the
  original parent artifacts for their semantic contracts.
- 20 focused tests, including reordered checks, exact cancellation, constants,
  missing/invalid input, integrity checks, V112 polynomial compression and the
  unchanged selected pipeline.

## Runtime and artifacts

The compact scorer is independently executable and retains no original forest:

```python
import json
from critical.core.calibration.boosted_factor_merge_v175 import FactorExecutor

artifact = json.load(open('logs/exps/261026-boosted-factor-merge-v176-r1/fold5/merged.json'))
scorer = FactorExecutor(artifact)
supports = scorer.probabilities(named_boolean_features)
```

The current selected loader still loads the original V112 artifact format.
The high-level audit is an executor substitution test; this experiment does
not silently rebind or deploy a new selected policy. A loader integration can
be reviewed separately if this representation is selected for serving.

- Completed run: `logs/exps/261026-boosted-factor-merge-v176-r1`.
- Compact full-data scorer: `fold5/merged.json` under that run.
- `compression.json`: all six size/condition/parameter comparisons.
- `verification.json`: complete factor/native/context/bound checks.
- `source_snapshot`, `protocol.json`, `manifest.json`, `run.log` and
  `llm-histories.log`: reproducibility and zero-call accounting.

No API, observer, encoder, fitting or reserved-source calls were made. Merging
similar but inequivalent semantic conditions would change the decision function
and needs a separate accuracy/coverage experiment.
