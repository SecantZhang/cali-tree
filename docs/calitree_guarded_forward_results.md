# Completed frozen 36-case guarded-policy comparison

The user-approved baseline completed on October 20, 2026. There were 36 counted
attempts: 35 successful regular judgments and one SSL/connection transport
failure, retained without a retry. All 36 cases remain in the main denominator.
No extraction, fitting or reference-label changes were performed.

The cohort has 36 distinct source groups and 12 references per class. These
sources were excluded from fitting the new gates, verifiers and correction
regions. They have disclosed older research exposure, so this is source-disjoint
validation of these fixes, not a globally untouched benchmark.

## Accuracy

Correct outputs out of 36, for every bank:

| System | Bank 1 | Bank 2 | Bank 3 |
|---|---:|---:|---:|
| Regular judge | 20 (55.6%) | 20 (55.6%) | 20 (55.6%) |
| v27 | 21 (58.3%) | 19 (52.8%) | 21 (58.3%) |
| v28 | 21 (58.3%) | 19 (52.8%) | 20 (55.6%) |
| v32 guarded merge | 21 (58.3%) | 19 (52.8%) | 21 (58.3%) |
| v33 outcome warrant | 21 (58.3%) | 19 (52.8%) | 21 (58.3%) |
| v35 verification only | **21 (58.3%)** | **19 (52.8%)** | **22 (61.1%)** |
| v35 verification plus corrections | 21 (58.3%) | 19 (52.8%) | 22 (61.1%) |

Verification only makes no prediction changes in banks 1 and 2. In bank 3,
it rejects the previously accepted Partial prediction for N022, “Make him stand
up,” and falls back to regular's correct No. It loses no previously correct
v27 decisions. The gain therefore remains on the 34-case subset with successful
regular judgment and cached extraction: bank 3 improves 21/34 to 22/34.

The regular transport failure is N046. Cached upstream evidence is missing for
N057, which correctly uses regular fallback. On their common successful subset,
regular scores 20/34; the verification-only banks score 20/34, 19/34 and 22/34.
These are supplementary numbers, not replacements for the full denominator.

Only one additional correct decision is observed in this cohort. That is a
small positive result, not strong statistical evidence of broad improvement.
Bank 2 remains worse than regular. No best bank is selected or hidden.

## Coverage and the correction-region tradeoff

Tree acceptance and accuracy conditional on acceptance:

| System | Bank 1 | Bank 2 | Bank 3 |
|---|---|---|---|
| v27 | 14/36 covered; 10/14 correct | 8/36; 4/8 correct | 10/36; 7/10 correct |
| Verification only | 14/36; 10/14 correct | 8/36; 4/8 correct | 9/36; 7/9 correct |
| Verification plus corrections | 15/36; 10/15 correct | 9/36; 4/9 correct | 9/36; 7/9 correct |

Verification-only coverage is 38.9%, 22.2% and 25.0%; accepted accuracy is 71.4%,
50.0% and 77.8%. The third bank removes one wrong acceptance. Coverage still
does not certify a uniformly reliable decision region, especially in bank 2.

The correction arm changes N024, “Change the background to Snoopy dog
wallpaper,” from regular's Partial to No in banks 1 and 2, while the reference
is Yes. Both answers are wrong, so total accuracy is unchanged; accepted
precision, macro F1 and ordinal error worsen. Macro F1 is 0.5701/0.5136/0.6126
for verification only versus 0.5669/0.5100/0.6126 with corrections.

The new `VerifiedSemanticJudge` therefore defaults to the **predeclared
verification-only arm**, with `enable_corrections=True` available explicitly.
This serving-mode choice follows the comparison. The underlying policies and
both arms were frozen before collection; no weights, clauses or regions were
refitted using these 36 references. The cohort is now development evidence for
future revisions.

## Implemented behavior and retained local accuracy

The serving path uses the v32 semantics-preserving merged regions, the v35
verdict verifier and the unchanged regular judge. It reuses cached bound
evidence, preserves existing verified routes when justified, and falls back
when the regular-aware guard rejects them. It never votes indiscriminately
across experts or asks a model at each tree node.

Example configuration, using a caller-supplied durable model-call ledger and
bound-evidence cache:

```python
import json
from pathlib import Path
from critical.core.calibration.regular_aware_gate_v35 import RegularAwareGate
from critical.core.optimization.prompt.calitree.verified_semantic_judge import VerifiedSemanticJudge

path = Path("logs/exps/261020-regular-aware-v35/full/split1/gate.json")
policy = RegularAwareGate.restore(json.loads(path.read_text()))
judge = VerifiedSemanticJudge(calls, policy, evidence_cache=cache, identity=identity)
result = judge.judge(instruction, evidence, case_id=case_id)
```

All three frozen bank artifacts remain available. This wrapper always obtains
one regular judgment, even on covered inputs; it is an accuracy-oriented
alternative to the original gate that could skip regular. No existing global
pipeline entry point is silently replaced.

The serving audit checks all 144 local predictions/coverage, 179 previously
correct routes, 432 hypothetical wrapper scenarios and 108 predictions using
the actual fresh baseline. All pass. Thirty-one focused tests pass.

The safe merge algorithm retains two reductions (63 to 61 definitions), rather
than v28's unsafe 44-region widening. Previously audited per-task symbolic
obligations and child-support retention remain valid. On the reviewed 80-case
source-held-out development study, this verification-only mode scores 57/53/56
versus v27's 57/50/50. The higher 59/57/56 correction-arm pilot scores should
not be substituted for the selected serving mode.

## Budget and audit

- Approved limits: 36 requests, 73,728 completion tokens; no retries/extraction.
- Counted attempts: **36**, with 35 completed and one transport failure.
- Recorded successful input/completion tokens: **40,462 / 1,918**.
- Completion usage plus the failed slot's reservation: **3,966**, within the cap.
- Recorded-usage estimate: **$0.0050** at the previously verified Luna rates;
  **$0.0060** including the failed output reservation. Failed-request billing
  and any unreported input usage are unknown; these are estimates, not invoices.

The completion auditor independently reconstructs all durable slots, reconciles
token records/reservations, rechecks fitting-source exclusion and recounts all
25 metric arms. The source model and analysis hashes remain frozen. The prior
broader-suite eight dependency/asset failures remain documented; the focused
checks and full data replay pass.

Artifacts:

- `logs/exps/261020-guarded-forward-v32-r1/full_results.json`
- `logs/exps/261020-guarded-forward-v32-r1/supplemental_v35/full_results.json`
- `logs/exps/261020-guarded-forward-v32-r1/execution_audit.json`
- `logs/exps/261020-verified-serving-v35/verification.json`

Reproduce completion checks with:

```bash
PYTHONPATH=. python run/verify_calitree_guarded_forward_completion.py \
  --output-dir logs/exps/261020-guarded-forward-v32-r1 \
  --serving-audit-dir logs/exps/261020-verified-serving-v35
```

Preparation documents and their “pending” fields are retained as historical
snapshots. The authorization record, completed responses and this report
supersede that earlier operational status.
