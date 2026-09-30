# Case-by-case CaliTree decomposition exploration — 2026-09-26

The user clarified that the goal is accuracy for each individual case, rather than generalization. This exploration restarts from the real AURORA image pair and the cached original/optimized prompts for each of the 32 J cases. It reaches **32/32 matching human labels after case-specific refinement**. Known labels are explicit fitting feedback and determine which cases receive further revisions. They are not supplied to individual condition checkers. These are fitted results on the named cases.

## Comparison

| Prediction | Matches human label |
| --- | --- |
| Cached original prompt | 26/32 |
| Cached optimized prompt | 26/32 |
| New individual condition checks, before feedback | 27/32 |
| After standard per-case feedback | 28/32 |
| After focused criterion repairs | 30/32 |
| After independent evidence on the final two failures | 32/32 |

All 32 final decisions are valid. Baselines are the exact cached predictions on these same pixel-verified image pairs; they were not rerun or selected across draws. The previous joint calibrated decomposition scored 28/32, but this restarted algorithm uses individually evaluated conditions and a Python reducer, with no training-reference image pairs.

## Algorithm

1. Compile the cached optimized rubric and edit instruction into explicit conditions. The initial compiler is text-only and label-blind. Each condition includes SOURCE target binding and observable criteria for complete, partial, absent and unknown. Scene preservation is checked separately.
2. Evaluate each condition in a separate real-model call on SOURCE then EDITED. The checker receives only the instruction, that condition and the images. It returns two observations, a status and a rationale; it does not predict the final label.
3. Reduce statuses in Python: any absent/unknown gives no; otherwise any partial gives partial; all complete gives yes.
4. Compare that prediction with the known human label. On a valid mismatch, give the compiler the human training label, prior observations and images to revise evidence-dependent criteria. Keep conflicts with the optimized rubric explicit. Do not give that feedback record to the checker.
5. Where criteria revisions still cannot resolve contradictory visual observations, add independent neutral measurements of each image. These observers received fixed property questions and one image without the editing instruction, rubric, role or annotation. The checker receives only their measurement reports, never their earlier final grade.

The initial run allowed one initial plan and two feedback revisions per case. Focused repairs then allowed up to three more revisions on the four unresolved cases. The last two cases received one additional condition-checking pass with already cached neutral measurements. Successful cases stopped when their label matched; failed attempts remain in the source artifacts. This selection is part of case-specific fitting. No case-label lookup or unconditional output rule was used.

Calls used gpt-4.1, temperature zero, 4,096 maximum output tokens and native strict JSON Schema, with at most one format repair per stage. Meaningful strings, status enums and unique condition IDs are validated locally. Images were rechecked against earlier public AURORA ZIP provenance hashes. Full histories/configurations are linked to logs/exps/ via each artifact’s log_directory.json.

## Every case

| Case | Instruction | Human | Original | Optimized | Initial decomposition | Fitted decomposition | Label feedback used |
| --- | --- | --- | --- | --- | --- | --- | --- |
| J01 | Make them close the curtains | no | partial | partial | partial | no | yes |
| J02 | Make her grab the book from the shelf | no | no | no | no | no | no |
| J03 | Close the laundry machine door | no | no | no | no | no | no |
| J04 | Make them stand up fully upright looking at their hands | no | no | no | no | no | no |
| J05 | the tiny yellow cylinder turns brown | no | no | no | no | no | no |
| J06 | make the purple sphere smaller | no | no | no | no | no | no |
| J07 | remove the green shiny block | no | no | no | no | no | no |
| J08 | the tiny yellow object turns purple | no | no | no | no | no | no |
| J09 | I want this as a watercolor | partial | no | no | no | partial | yes |
| J10 | Make the image look like a cartoon | partial | no | no | partial | partial | no |
| J11 | turn this photo into a picasso painting | partial | partial | partial | partial | partial | no |
| J12 | Change the style to Cubism | no | no | no | no | no | no |
| J13 | Pick up the egg with the right hand | yes | yes | partial | yes | yes | no |
| J14 | Lift the frying pan up | no | no | no | no | no | no |
| J15 | Let the paper towel fall down | no | no | no | no | no | no |
| J16 | The fork pulls one piece of fish out of the can | partial | yes | yes | yes | partial | yes |
| J17 | shift the position of the vintage metal alarm clock above the toy squirrel | no | no | no | no | no | no |
| J18 | add 2 white square saucer to the scene | no | no | no | no | no | no |
| J19 | remove 2 shark from the image | no | no | no | no | no | no |
| J20 | place the CARSII on the right of the green-purple pencil case | no | no | no | no | no | no |
| J21 | Put a dragonfly on the dog's ear | no | no | no | no | no | no |
| J22 | make the catcher laugh | partial | yes | partial | yes | partial | yes |
| J23 | Let the toilet bowl have a lid | no | no | no | no | no | no |
| J24 | Put down the seat | no | no | no | no | no | no |
| J25 | Flip the bottle upside down | no | no | no | no | no | no |
| J26 | Drop the glass on top of the pills | no | no | no | no | no | no |
| J27 | Unfold cloth | no | no | no | no | no | no |
| J28 | Moving cup away from pen | no | no | no | no | no | no |
| J29 | Move the bowl to the left of the flower | partial | no | no | no | partial | yes |
| J30 | Move the can to the right of the knife | no | no | no | no | no | no |
| J31 | Move the bowl on the armchair | no | no | no | no | no | no |
| J32 | Move the sunglasses under the chair | no | no | no | no | no | no |

## What changed in the difficult cases

- **J10/J11, cartoon/Picasso:** the initial explicit status criteria recognized a localized style transformation as partial accomplishment. The earlier joint grader had treated some such cases as no.
- **J13:** individual checking produced yes immediately, matching the human label and correcting the cached optimized prompt’s partial judgment.
- **J22, catcher laugh:** the initial preservation checker described extra faces being edited yet returned complete. The feedback revision explicitly classified editing additional faces as a minor semantic discrepancy, making preservation partial and the final result partial.
- **J09, watercolor:** the focused repair distinguished loss of fine detail caused by the requested painting style from full scene replacement. Watercolor progress and recognizable scene structure received partial credit instead of an absent preservation condition.
- **J29, bowl left of flower:** the focused repair retained imperfect object identity/count while recognizing that the edited bowls were placed to the left. The remaining semantic discrepancy became partial rather than complete absence.
- **J01, curtains:** repeated condition checks claimed the curtains were mostly closed. Independent neutral observations identified exposed window areas and no person-curtain contact. The final curtain-state check still returned partial, but the separate person-action condition became absent because the person’s hands were occupied with another object, producing no.
- **J16, fork/fish:** repeated checks claimed a fully separated piece was lifted by the fork. Neutral measurements made the contact/separation ambiguity explicit. The final action condition became partial, producing the human partial label.

The human data supplies scalar scores rather than explanations. These learned interpretations are inferred from the images and score feedback; they do not establish the actual raters’ reasons. These corrections involve both observation grounding and the meaning of partial credit. Decomposition is useful when it turns those assumptions into inspectable condition-level decisions; splitting the prompt alone does not guarantee correctness.

## Artifacts and verification

- Reusable opt-in runner: `tests/unit/calitree/casewise_fitting.py`; versioned templates under `tests/unit/calitree/templates/casefit_v1/`.
- First attempt: `.cache/calitree-tests/vision-casewise-fitting32-20260926/`. It compiled 32 valid label-blind plans but failed before visual judgment because recorded provenance entries lacked LM media types. The original record is preserved; an exact source snapshot was reconstructed and checked against its original manifest hash.
- Corrected main run: `.cache/calitree-tests/vision-casewise-fitting32-v2-20260926/`. It reuses only those initial text-only plans, with unchanged request identities. No earlier visual prediction existed to select.
- Focused repairs: `.cache/calitree-tests/vision-casewise-targeted-repair4-20260926/`.
- Independent evidence for J01/J16: `.cache/calitree-tests/vision-casewise-neutral-evidence2-20260926/`, reusing measurements from `.cache/calitree-tests/vision-neutral-property-strict-development32-20260926/`.
- Consolidated learned criteria/checks: main run’s `fitted_cases.json`; independently reduced statuses and checker input audit: `final_case_verification.json`.
- Offline tests: **921 passed, 23 skipped**, with 52 existing warnings. The new tests cover label-feedback separation, stopping, bounded failures, deterministic reduction, recorded-image input conversion and cache replay. Offline tests establish code contracts; the real-model records establish these named cases’ fitted accuracy.

The core default decomposition strategy is unchanged. The current per-case fitting loop is an experiment runner; focused repair and neutral-evidence follow-ups are preserved as research snapshots rather than a production automatic escalation policy.
