# Local evidence and semantic rubric development (v77–v83)

The active accuracy target is235/276 on the existing source-held development
comparison. The independently verified reference remains v72 at223/276 (80.8%).
These experiments add independently computed evidence and clearer semantic
concepts; they are research candidates, with no serving change or85% claim.

The subsequent [v87 optional independent-expert replay](calitree_independent_semantic_v87.md)
improves to225/276 using15 valid cached Sol views. The unchanged no-extra-expert
baseline remains223/276; the original >85% objective remains unmet.

## Object-region evidence and explicit physical rules

V77 binds a target in the source image using frozen GroundingDINO and SigLIP2
crop/text comparisons, then matches its edited counterpart. Attribute changes
favor correspondence in position and appearance; requested movement favors
appearance. Relative-reference tasks also bind the named reference object.
The checkpoint identities, code, image bytes, preprocessing and each resulting
program/image-pair binding are hashed.

The915-case extraction makes440 local detector queries. It produces comparisons
for227 cases;235 have a supported plan. Attribute plans cover requested color,
finish, material or size; spatial plans cover explicit image-plane order and
proximity. Unsupported tasks and failed detections stay unavailable. Raw boxes
remain diagnostic traces; only input-relative comparisons reach learners.

V78's physical expert has this explicit policy:

1. Abstain if scope is incomplete or target/reference correspondence is weak.
2. Check the requested endpoint, using the localized expected color fraction,
   relative size change, finish contrast or requested geometric relation.
3. Credit Yes only when the endpoint and known acceptable identity/collateral
   conditions agree. An endpoint with an explicit material shortfall is Partial.
4. Credit Partial for positive goal-directed physical progress that falls short
   of the endpoint. Mere visible change and uncertainty do not establish progress.
5. Credit No only for qualified failure evidence or loss of an essential original
   instance. Otherwise abstain. A missing detection does not prove absence.

Four fixed profiles compare two correspondence guards and two endpoint extents.
The broad/substantial profile corrects4 v69 errors but introduces6 regressions:
220/276 after fallback. The strict/substantial profile reaches221/276. Direct
overrides also retain only91/99 originals for the broad profiles and96/99 for
the strict profiles. None is promoted. The explicit color rule distinguishes changing most of a target
from changing only part of it; finish and proximity remain fallible proxies.

Only11 of v69's54 errors have a bound region comparison. Region reasoning alone
therefore has limited recovery scope. Plural-target correspondence, articulated
pose, grasp/contact, occlusion and depth remain substantial gaps. Detectors can
also confidently label the wrong object. Their scores are binding cues, not
certificates of physical identity.

## Visual audit of semantic descriptions

V79 reuses the pinned14-view image vectors and locally encodes bound questions
and source/edited visible descriptions. It never encodes human grades,
interpreter states or regular-judge labels as image captions. The915 cases
require9,810 distinct text encodings and no new image inference.

The audit compares each description with its own image and the opposite image.
It also checks whether the direction of claimed descriptive change aligns with
the direction of image-vector change. Outcome, intermediate, identity and
collateral roles remain separate. Missing roles remain unavailable. A high
affinity is an independent model opinion, not proof that the caption is true.

V80 compares shallow histogram boosting and the unchanged depth8/1200 CatBoost
recipe with these scalar audits, optionally including region measurements.
The same276 cases and five source folds include failures through the original
bound-evidence fallback. No raw embeddings, case/source/editor identifiers,
requested object/color identity or raw coordinates enter grade fitting.

## Language-level rubric concepts

V81 uses the pinned local
[cross-encoder NLI model](https://huggingface.co/cross-encoder/nli-deberta-v3-small)
to interpret existing explanations against16 fixed semantic claims. These cover
endpoint completion, useful progress, wrong target, retained/replaced identity,
authorized differences, collateral effects, visibility, uncertainty and implied
action without a visible outcome. The model reads regular explanations and raw
bound source/edited descriptions separately. Observer answer states and human
grades are excluded. All inference is local with native safetensors; downloading
the public checkpoint does not send project text or images to the model host.

Contradiction, entailment and neutral supports describe what the text claims.
They cannot fix a hallucinated observation by themselves. They also do not
replace an image-grounded grading warrant. This stage improves the declared
semantic vocabulary rather than treating fixed keyword matches as equivalent
to semantic interpretation.

## Compact semantic score correction

V82 learns at most24 named semantic/view terms in an explicit three-class score
equation. The original boosted score stays visible as an offset; this does not
claim to reconstruct it as a standalone prose rubric. At prediction time the
published means, scales, coefficients, clipping, temperature and correction
strength completely specify the additive layer.

All correction fitting uses the30 cached inner source-excluded teacher views.
Residual feature selection, imputation, normalization and correction strength
use fitting rows only. Each source has equal fitting weight. A strength that
changes any protected original prediction is vetoed; strength0 exactly retains
the teacher. The outer held-source siblings never enter teacher or correction
fitting. Initial semantic/caption variants top out at222/276, with99/99 retained
and unchanged273/276 upstream coverage, so none supersedes v72.

## Completed comparison and verification

| Candidate family | Best correct /276 | Decision |
|---|---:|---|
| Existing verified v72 |223|Retain|
| Region-augmented learners (v78) |222|Do not promote|
| Caption/pixel-audited learners (v80) |211|Do not promote|
| Compact semantic/caption score correction (v82 r1) |222|Do not promote|
| NLI-augmented score correction (v82 r2) |221|Do not promote|
| Fixed evidence pools with v72 priority (v83) |223|Tie with more complexity; do not promote|

V83 uses fixed equal arithmetic averages, with No/Partial/Yes tie order, and
tests a semantic root route that includes the region learner only when complete
scope and comparative correspondence guards hold. The existing v72 correction
keeps its original teacher context and priority. Pool weights are not selected
against held labels. The best pool changes three previously correct cases to
wrong and three wrong cases to correct, tying v72; it adds no net accuracy.

The independent auditor replays all28 new native CatBoost models on all915
inputs,54 explicit score-equation artifacts, and the actual144 original slots
for every checked fit. It confirms all fitted candidates retain99/99 originals
and273/276 upstream coverage. Failed histogram candidates receive saved-support,
membership and metric checks, without a second histogram fit.59 focused tests
pass. The first score audit had a NumPy integer reporting error after its
assertions; that incomplete report is marked superseded, and the corrected r2
audit completes successfully.

These experiments improve the available semantic definitions and diagnostics,
but they do not demonstrate an accuracy improvement. The target remains unmet:
v72 needs12 additional correct cases to reach235/276. New independent visual
judgments remain the next prepared test; language interpretation and local
similarity cues have not supplied that gain here.

## Reproducibility and status

Experiment roots:

- `logs/exps/261023-grounded-regions-v77-r2`
- `logs/exps/261023-region-policy-v78-r1`
- `logs/exps/261023-caption-audit-v79-r1`
- `logs/exps/261023-caption-policy-v80-r1`
- `logs/exps/261023-nli-rubric-v81-r2`
- `logs/exps/261023-rubric-score-v82-r1`
- `logs/exps/261023-rubric-score-v82-r2`
- `logs/exps/261023-evidence-pool-v83-r2`

Independent audits are saved in the v78/v80 study roots with `-audit`,
`261023-rubric-score-v82-r1-audit`, and
`261023-rubric-score-v82-r2-audit-r2`. Pool r2 adds an explicit original teacher
contract check; its predictions match r1.

V77 r1 was superseded before inference to strengthen cache provenance. The first
v77 r2 attempt failed before inference because the sandbox hid Metal; the offline
GPU retry completed440 detector queries. V81 r1 failed before inference on an
unrelated optional provider import; r2 moves the pure concept vocabulary into
the dependency-light decision package. No failure incurred API charges.

The24-query contrastive image-judge pilot remains frozen at
`logs/exps/261023-contrastive-judge-v75-pilot-r2`, separately awaiting human
approval for72 paid requests and344,064 completion tokens. Its request/code/
image hashes still verify. No real API calls or reserved-source judging have
been performed during this goal. All scores here are reviewed development
results after repeated method selection, not untouched final-test estimates.
