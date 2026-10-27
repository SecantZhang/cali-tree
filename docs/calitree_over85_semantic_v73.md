# Over85% accuracy with a meaningful semantic rubric

The active target is **at least235/276 correct** on the established source-held
development comparison, while retaining the original99 cases,144 local slots
and upstream bound-evidence coverage. The original reference is v72 at
223/276 (80.8%). A later [optional independent-expert replay](calitree_independent_semantic_v87.md)
reaches225/276 (81.5%) with15 valid cached Sol views. The >85% target has not been achieved.

## Completed offline work

V73 adds explicit same-requirement rubric definitions instead of combining an
endpoint from one requirement with identity/collateral evidence from another.
Every grading-rule search begins with an affirmative No/Partial/Yes warrant;
every regular-judge routing search begins with an uncertainty, contradiction or
review reason. Distinct semantic predicates are kept even when fitting columns
coincide. Model support is labelled as a judge-view cue, never factual certainty.

The second version canonicalizes exact duplicate bound checks and treats their
disagreement as unknown. An unknown outcome cannot establish Yes or serve as an
explicit failure witness for No. Positive witnesses remain instruction-bound,
including negative-polarity absence/removal checks.

Eight configurations per version compare semantic, grounded and auxiliary-vision
vocabularies, grading versus review routing, and two error costs. All use the
same five outer source folds and30 inner source-excluded teacher caches. All
original99 remain correct and upstream evidence coverage remains273/276.

| Study | Best correct /276 | Gains/losses versus v69 | Status |
|---|---:|---:|---|
| Verified v72 |223|1/0|Reference retained|
| V73 initial seeded search |222|5/5|Not promoted|
| V73 canonical physical witnesses |223|5/4|Ties accuracy with more churn; not promoted|

V74 additionally tests small readable judge-selection trees inside the same
explicit review regions. Their best composition with v72 reaches221/276, so
they are not promoted either. These results do not justify broadening the
regular-judge fallback on the current evidence.

The existing v71 grading warrants could, with perfect decisions, correct only
14 of v69's54 errors. Adding perfect selection of the independent regular view
raises this descriptive oracle count to26. Neither is an achieved result. This
motivates collecting a genuinely new semantic image judgment instead of only
searching more clauses over the same noisy observations.

## Prepared training-only image-judge pilot

The exact prepared run is
`logs/exps/261023-contrastive-judge-v75-pilot-r2`. Earlier preparation directories
are superseded and have made no model calls.

The pilot contains24 original training queries from24 distinct sources:8 per
reference class, with3 known cached regular errors and5 correct controls per
class. This deliberate training diagnostic is not an overall accuracy estimate.
All query sources are excluded globally from contrast retrieval. The pool uses
only other original training sources and their matched editing-model outputs;
all84 development sources and80 reserved sources are excluded.

For each semantic request, two other-source matched contrasts show the
No/Partial and Partial/Yes boundaries. Each contrast is one source image plus
two edits of the same instruction with different human labels. Identical edited
pixels with conflicting labels cannot form a contrast. Retrieval uses fixed
operation types and task-intent cues; the query reference is never passed to
the model or used for retrieving its contrasts.

The judge receives the query instruction, authorization contract and bound
checks, two contrasts, and the query images. It returns a compact evidence
certificate: target correspondence, endpoint, progress, collateral status,
grading criterion, bound check witnesses, label and a short visible rationale.
Validation rejects unsupported No/Partial/Yes claims, wrong check IDs and
cross-requirement Yes claims. Unknown outcomes do not become failed outcomes.
Rejected responses remain failed slots and are never repaired or resampled.

The three paired arms are:

| Arm | Model/profile | Requests | Output cap/request | Images/request |
|---|---|---:|---:|---:|
| Fresh regular |GPT-6 Luna, temperature0, wire reasoning none|24|2,048|2|
| Semantic contrastive |GPT-6 Luna, same profile|24|4,096|8|
| Semantic contrastive |GPT-6.1 Sol, medium reasoning|24|8,192|8|

Caps are **72 requests and344,064 completion tokens**, with no transport retries,
certificate repairs, fitting, new compiler/extractor calls or reserved-source
evaluation. Expected cost is **$0.50–$2.00**. The complete output allowance costs
**$2.039808 plus input charges**, using current Standard
[official pricing](https://developers.openai.com/api/docs/pricing): Luna
$0.10/$0.50 and Sol $2/$10 per million input/output tokens. The forecast is not
a hard input-token or invoice cap. Cache discounts are not assumed.

The semantic expert differs from the earlier v38 failed visual-example
diagnostic: it uses within-task matched contrasts, the compiled query contract,
operation-specific judging principles and an executable evidence certificate.
The original v38 Sol comparison did not improve training accuracy; a stronger
model alone is not assumed to solve the problem.

## Verification and next step

The 72-slot mock rehearsal exercises both model routes, response validation,
budgets and sticky resume; resume adds zero requests.67 focused tests pass.
No paid request has been made. The existing serving path is unchanged.

Review `critical/core/prompts/templates/semantic_contrastive_v75/judge.txt` and
the prepared `jobs.json`, `protocol.json`, `manifest.json` and
`sample_semantic_request.json`. Paid collection requires separate authorization
and `--live`. Earlier approvals covered different capped experiments.

```bash
PYTHONPATH=/tmp/calitree-catboost-v62:. /path/to/python -m run.calitree_contrastive_pilot_v75 \
  --verify --output-dir logs/exps/261023-contrastive-judge-v75-pilot-r2
# Only after approval:
PYTHONPATH=/tmp/calitree-catboost-v62:. /path/to/python -m run.calitree_contrastive_pilot_v75 \
  --live --output-dir logs/exps/261023-contrastive-judge-v75-pilot-r2
```

After collection, compare fresh paired accuracy, evidence-certificate validity
and disagreement corrections. A promising training result can justify a
separately frozen broader comparison; even a pilot above85% does not satisfy
the276-case goal. The existing development cases have been reviewed during
prior research and prompt design; no untouched-test claim is made.

## Independent local grounding probe

While paid approval is pending, v76 repairs the cached GroundingDINO postprocess
call to use the installed `threshold` keyword and runs four local detections on
one original fitting source. The fixed checkpoint and all asset hashes are
recorded; inference is offline with native safetensors. The selected purple
sphere is localized in the source and edit, but other objects also receive
false-positive phrase labels. This is evidence that the local tool runs, not
an accuracy result or a claim that detection scores certify target identity.
Any future region-based rubric must retain ambiguity and correspondence guards.


## Completed approved pilot (v88)

The separately approved72-request pilot is complete. Fresh regular Luna scores15/24, semantic contrastive Luna14/24 and semantic Sol13/24, counting three rejected Luna certificates and one failed Sol transport slot as incorrect. No retries, repairs, fitting or reserved-source evaluation occurred. The independent accounting audit passes; neither semantic arm is promoted. See [the final diagnostic report](calitree_contrastive_pilot_v88.md) for paired comparisons, failure attribution and usage. Earlier pending-approval descriptions above are historical. The broad225/276 result and over85% target remain unchanged.


## Offline controls after the pilot (v89–v92)

Ten calibration-scope controls score221–224/276. Twelve ordered-visual/continuous-score controls reach at best225/276; the tied warranted variants make no changes to primary predictions. No method is promoted. The independent24-native-model/132-equation audit passes and explicitly rejects two controls that lose original-case accuracy. A counterfactual collateral-cap audit shows that a blanket cap removal would incorrectly admit four original Partial cases as Yes. See [the calibration/control report](calitree_calibration_controls_v91.md) and [pilot diagnosis](calitree_contrastive_pilot_v88.md). The current225/276 policy,99/99 originals,144/144 slots and273/276 bound-evidence coverage remain unchanged;235/276 is still unmet.
