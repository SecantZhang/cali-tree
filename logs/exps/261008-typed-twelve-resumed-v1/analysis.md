# Twelve-case saved-data analysis

Twelve previously observed local fitting cases. Four per reference class. No cross-case feedback, atomic correctness or held-out generalization claim.

Status: stopped

| Case / reference | Arm | Seed → selected matches / 5 | Usable / 5 | Completed rounds | Checks | Status |
|---|---|---:|---:|---:|---:|---|
| transform the black DVD into a white DVD / no | criterion-only | pending | pending | unavailable | 0 | preparation_failed |
| transform the black DVD into a white DVD / no | nested-required | pending | pending | unavailable | 0 | preparation_failed |
| Make her close her jacket fully / yes | criterion-only | pending | pending | 7 | 3 | budget_exhausted |
| Make her close her jacket fully / yes | nested-required | pending | pending | 15 | 3 | structural_failure |
| Change the image into pencil drawing / partial | criterion-only | pending | pending | 2 | 3 | confirmed_local |
| Change the image into pencil drawing / partial | nested-required | pending | pending | 10 | 4 | budget_exhausted |
| Give the woman a helmet / yes | criterion-only | pending | pending | 4 | 3 | confirmed_local |
| Give the woman a helmet / yes | nested-required | pending | pending | 15 | 3 | structural_failure |
| Change the background into a basketball court / yes | criterion-only | pending | pending | 6 | 3 | budget_exhausted |
| Change the background into a basketball court / yes | nested-required | pending | pending | 12 | 4 | budget_exhausted |
| Move the mug to the right of the headphones / partial | criterion-only | pending | pending | 12 | 3 | budget_exhausted |
| Move the mug to the right of the headphones / partial | nested-required | pending | pending | 12 | 4 | budget_exhausted |
| Move the book behind the flower / no | criterion-only | pending | pending | 6 | 3 | budget_exhausted |
| Move the book behind the flower / no | nested-required | pending | pending | 15 | 3 | structural_failure |
| Stuffing the paper into the cup / no | criterion-only | pending | pending | 2 | 3 | confirmed_local |
| Stuffing the paper into the cup / no | nested-required | pending | pending | 15 | 3 | structural_failure |
| Make this look like a comic book photo / no | criterion-only | pending | pending | 1 | 3 | confirmed_local |
| Make this look like a comic book photo / no | nested-required | pending | pending | unavailable | 0 | unattempted |
| Turn the image into a drawing made from chalk / partial | criterion-only | pending | pending | unavailable | 0 | unattempted |
| Turn the image into a drawing made from chalk / partial | nested-required | pending | pending | unavailable | 0 | unattempted |
| Put a frog in the toilet / partial | criterion-only | pending | pending | unavailable | 0 | unattempted |
| Put a frog in the toilet / partial | nested-required | pending | pending | unavailable | 0 | unattempted |
| the small gray rubber cylinder becomes brown / yes | criterion-only | pending | pending | unavailable | 0 | unattempted |
| the small gray rubber cylinder becomes brown / yes | nested-required | pending | pending | unavailable | 0 | unattempted |

Pending final measurements are unavailable, not zero accuracy. Missing/invalid cases will remain in the full denominator of a completed comparison. Five repeats are measurements within cases, not independent cases. Confidence is self-report and atomic consistency is not correctness.

## Class metrics

{
  "criterion-only": {
    "yes": {
      "cases": 4,
      "mean_selected_agreement": null,
      "mean_selected_coverage": null,
      "locally_robust": null,
      "finalized_cases": 0
    },
    "partial": {
      "cases": 4,
      "mean_selected_agreement": null,
      "mean_selected_coverage": null,
      "locally_robust": null,
      "finalized_cases": 0
    },
    "no": {
      "cases": 4,
      "mean_selected_agreement": null,
      "mean_selected_coverage": null,
      "locally_robust": null,
      "finalized_cases": 0
    }
  },
  "nested-required": {
    "yes": {
      "cases": 4,
      "mean_selected_agreement": null,
      "mean_selected_coverage": null,
      "locally_robust": null,
      "finalized_cases": 0
    },
    "partial": {
      "cases": 4,
      "mean_selected_agreement": null,
      "mean_selected_coverage": null,
      "locally_robust": null,
      "finalized_cases": 0
    },
    "no": {
      "cases": 4,
      "mean_selected_agreement": null,
      "mean_selected_coverage": null,
      "locally_robust": null,
      "finalized_cases": 0
    }
  }
}

## Usage

{
  "calls": 1413,
  "completion_tokens_charged": 293366,
  "completion_tokens_reported": 214518,
  "input_tokens": 4715746,
  "outcomes": {
    "completed": 1364,
    "transport_error": 49
  },
  "stages": {
    "gradient": 442,
    "propose_typed": 161,
    "check": 521,
    "audit": 122,
    "visual_discovery": 157,
    "compile_typed": 10
  },
  "returned_models": [
    "gpt-6-luna"
  ]
}

## aurora-task-49616ac011dcfc46a053::magic_reproduce_epoch=47-step=12999 / criterion-only

Acceptance: {}
Stop: ValueError: Evidence questions must be distinct from each other and fulfillment
Audit: {}
| Check | Question | Evidence context | Final states | Consistency |
|---|---|---|---|---:|

## aurora-task-49616ac011dcfc46a053::magic_reproduce_epoch=47-step=12999 / nested-required

Acceptance: {}
Stop: ValueError: Evidence questions must be distinct from each other and fulfillment
Audit: {}
| Check | Question | Evidence context | Final states | Consistency |
|---|---|---|---|---:|

## aurora-task-4d9932789529604a30e8::finetune_magicbrush_ag_something_kubric_15-15-1-1_init-magic_first_epoch=02-step=41999 / criterion-only

Acceptance: {}
Stop: budget_exhausted: Case criterion-only/aurora-task-4d9932789529604a30e8::finetune_magicbrush_ag_something_kubric_15-15-1-1_init-magic_first_epoch=02-step=41999 search allowance exhausted
Audit: {"accepted": true, "reason": "The program preserves the request to close the jacket fully. Its support checks separately assess visible progress and the complete-closure endpoint, and the readout correctly maps complete closure to complete, evidenced progress with incomplete closure to partial, no progress to absent, and insufficient evidence to unknown. The nested check is active for every parent result and independently examines the finer condition; the readout uses both observations without treating support checks as completion credit. No unrelated constraints or unsupported inferences are added.", "execution_ref": "cb71d7bff8c54eea2618b12aff2e45aff3ec547adf51e0bd8dae30d33c390462"}
| Check | Question | Evidence context | Final states | Consistency |
|---|---|---|---|---:|
| s1 | Is the woman's jacket visibly closed more than in the input image, with its front panels brought together at least in part? | [] | {} | None |
| s2 | Is the woman's jacket fully closed, with no visible opening remaining along its closure? | ['s1'] | {} | None |
| fulfillment | Is the woman's jacket fully closed? | ['s1', 's2'] | {} | None |

## aurora-task-4d9932789529604a30e8::finetune_magicbrush_ag_something_kubric_15-15-1-1_init-magic_first_epoch=02-step=41999 / nested-required

Acceptance: {}
Stop: round_limit
Audit: {"accepted": true, "reason": "The program preserves the request to close the jacket fully. Its support checks separately assess visible progress and the complete-closure endpoint, and the readout correctly maps complete closure to complete, evidenced progress with incomplete closure to partial, no progress to absent, and insufficient evidence to unknown. The nested check is active for every parent result and independently examines the finer condition; the readout uses both observations without treating support checks as completion credit. No unrelated constraints or unsupported inferences are added.", "execution_ref": "cb71d7bff8c54eea2618b12aff2e45aff3ec547adf51e0bd8dae30d33c390462"}
| Check | Question | Evidence context | Final states | Consistency |
|---|---|---|---|---:|
| s1 | Is the woman's jacket visibly closed more than in the input image, with its front panels brought together at least in part? | [] | {} | None |
| s2 | Is the woman's jacket fully closed, with no visible opening remaining along its closure? | ['s1'] | {} | None |
| fulfillment | Is the woman's jacket fully closed? | ['s1', 's2'] | {} | None |

## aurora-task-52fd3fa52d915723d12d::mgie / criterion-only

Acceptance: {}
Stop: confirmation_qualified
Audit: {"accepted": true, "reason": "The program preserves the instruction and rubric. Its support checks separately assess overall pencil-drawing completion and image-grounded progress, without making monochrome or a particular technique mandatory. The fulfillment readout composes both observations correctly: completion requires the overall rendering check to pass; partial requires evidenced progress without completion; and no requires evidence of neither. Unresolved evidence remains unknown, and unrelated edits do not count. The nested check can use its parent observation as context while independently assessing progress. No unsupported inference, contradictory composition rule, or unjustified non-applicability is present.", "execution_ref": "44eb5d95548dbf6faf44f89acbf1044585f1ba07eb1e0942fdd484e5e253bc2a"}
| Check | Question | Evidence context | Final states | Consistency |
|---|---|---|---|---:|
| s1 | Does the edited image show the original scene rendered overall as a pencil drawing, rather than merely receiving muted color, grain, or softened photographic shading? | [] | {} | None |
| s2 | Is there image-grounded evidence of any relevant progress toward rendering the content as a pencil drawing, even if the overall transformation is incomplete? | [] | {} | None |
| fulfillment | Does the image visibly appear as a completed pencil drawing? | ['s1', 's2'] | {} | None |

## aurora-task-52fd3fa52d915723d12d::mgie / nested-required

Acceptance: {}
Stop: budget_exhausted: Case nested-required/aurora-task-52fd3fa52d915723d12d::mgie search allowance exhausted
Audit: {"accepted": true, "reason": "The program preserves the request to render the image as a pencil drawing without imposing a particular technique. Its supports separately assess visible progress and whole-image completion; the fulfillment readout correctly distinguishes complete, partial, absent, and unresolved evidence, and does not treat support passes alone as completion. The nested checks can assess their own propositions using ancestor observations as context, and the composition rules are consistent.", "execution_ref": "1ca7ac5ccfced4b83e3eeb5347023929241a8e19262edb217011446b9e34e013"}
| Check | Question | Evidence context | Final states | Consistency |
|---|---|---|---|---:|
| s1 | Does the image show the original visual content rendered in a pencil-drawn style? | [] | {} | None |
| s2 | Is there image-grounded evidence of any progress toward rendering the content as a pencil drawing, even if the transformation is incomplete? | [] | {} | None |
| s3 | Does the edited image, considered as a whole, visibly read as a pencil drawing of its content rather than an image with only limited pencil-style treatment? | ['s2'] | {} | None |
| fulfillment | Does the image visibly appear as a completed pencil drawing? | ['s1', 's2', 's3'] | {} | None |

## aurora-task-538ef5e1e9d068bbfe6d::magic_reproduce_epoch=47-step=12999 / criterion-only

Acceptance: {}
Stop: confirmation_qualified
Audit: {"accepted": true, "reason": "The program preserves the request to give the source woman a helmet. Its support checks separately assess visible completion and visible, incomplete helmet-placement progress; the nested check does not treat a coarse pass as proof of a finer condition. The fulfillment readout uses those observations consistently: completion takes precedence, evidenced incomplete progress is partial, no progress is absent, and insufficient evidence remains unknown. The checks add no unrelated constraints or mandatory techniques, and the composition rules do not conflict.", "execution_ref": "209aee965374c28432b3e8b6b0784108817148f428d3825c35198209037730ac"}
| Check | Question | Evidence context | Final states | Consistency |
|---|---|---|---|---:|
| s1 | Does the image show a helmet visibly on the woman’s head? | [] | {} | None |
| s2 | Does the edited image show the source woman with a helmet-related change that is visibly incomplete—for example, a helmet being placed but not yet on her head? | [] | {} | None |
| fulfillment | Is a helmet visibly present on the woman’s head? | ['s1', 's2'] | {} | None |

## aurora-task-538ef5e1e9d068bbfe6d::magic_reproduce_epoch=47-step=12999 / nested-required

Acceptance: {}
Stop: round_limit
Audit: {"accepted": false, "reason": "The fulfillment readout cannot faithfully distinguish a complete result from partial progress. s2 is defined to pass only when it shows progress but does not establish the complete result in s1, yet the readout says partial if s1 does not pass and s2 passes. If s1 is unknown while s2 passes, this can label the result partial without establishing incompleteness; if s1 fails, the checks may also conflict about whether a helmet is present. The composition should require evidenced incompleteness before assigning partial and resolve contradictory support observations rather than treating them as a valid outcome.", "execution_ref": "13d9d8e7d18bdb5b958b9091838d54563dd9c83726f282579de23f34834008da"}
| Check | Question | Evidence context | Final states | Consistency |
|---|---|---|---|---:|
| s1 | Does the image show a helmet visibly on the woman’s head? | [] | {} | None |
| s2 | Is there image evidence that a helmet has been added to the woman, even if the requested result is not complete? | [] | {} | None |
| fulfillment | Is a helmet visibly present on the woman’s head? | ['s1', 's2'] | {} | None |

## aurora-task-65581617ad341fa398cb::magic_reproduce_epoch=47-step=12999 / criterion-only

Acceptance: {}
Stop: budget_exhausted: Case criterion-only/aurora-task-65581617ad341fa398cb::magic_reproduce_epoch=47-step=12999 search allowance exhausted
Audit: {"accepted": true, "reason": "The program preserves the requested background change and rubric. Its two supports separately assess a playing surface and court markings or basketball equipment; the nested check is active for every parent result and must inspect its own proposition rather than inherit the parent\u2019s conclusion. The image-free fulfillment readout uses both observations, requires both kinds of evidence for completion, allows either to support partial progress without treating it as sufficient for completion, and keeps insufficient evidence unresolved. It does not add unrelated constraints or unsupported inferences.", "execution_ref": "1e232385b0848736aa8c786f7e8738e40a1cdf7be1d368eb1bdc546608c805d1"}
| Check | Question | Evidence context | Final states | Consistency |
|---|---|---|---|---:|
| s1 | Does the image show a basketball playing surface as part of the background? | [] | {} | None |
| s2 | Does the background show recognizable basketball-court markings or basketball equipment? | [] | {} | None |
| fulfillment | Does the image show the background changed into a recognizable basketball court? | ['s1', 's2'] | {} | None |

## aurora-task-65581617ad341fa398cb::magic_reproduce_epoch=47-step=12999 / nested-required

Acceptance: {}
Stop: budget_exhausted: Case nested-required/aurora-task-65581617ad341fa398cb::magic_reproduce_epoch=47-step=12999 search allowance exhausted
Audit: {"accepted": true, "reason": "The program preserves the requested background change and rubric. Its supports separately assess a basketball playing surface, court markings or equipment, and whether those features form a coherent court; the nested checks do not treat a broad pass as proof of a finer condition. The fulfillment readout uses only support evidence, distinguishes completion from progress and absence, and leaves necessary unknowns unresolved. The equipment-or-markings support can establish progress without being treated as completion, and the coherence check appropriately tests the requested whole-background result. No unrelated constraints, unsupported inferences, or contradictory composition rules are apparent.", "execution_ref": "0f776eb206cedb688401b6bc13d53ee1677f3bfc10c1b2afa1bbe1871564dc2d"}
| Check | Question | Evidence context | Final states | Consistency |
|---|---|---|---|---:|
| s1 | Does the image show a basketball playing surface as part of the background? | [] | {} | None |
| s2 | Does the background show recognizable basketball-court markings or basketball equipment? | [] | {} | None |
| s3 | Do the visible court markings and playing surface together make the background read as a coherent basketball court, rather than isolated court features against a predominantly featureless backdrop? | ['s1', 's2'] | {} | None |
| fulfillment | Does the image show the background changed into a recognizable basketball court? | ['s1', 's2', 's3'] | {} | None |

## aurora-task-7b78f1229d9bb014bcc5::finetune_magicbrush_ag_something_kubric_15-15-1-1_init-magic_first_epoch=02-step=41999 / criterion-only

Acceptance: {}
Stop: budget_exhausted: Case criterion-only/aurora-task-7b78f1229d9bb014bcc5::finetune_magicbrush_ag_something_kubric_15-15-1-1_init-magic_first_epoch=02-step=41999 search allowance exhausted
Audit: {"accepted": true, "reason": "The program preserves the sole requested change and its spatial relation. The broad support check assesses whether the objects and comparison are observable; the nested check independently assesses whether the mug is to the right, without treating the parent pass as fulfillment. The readout uses both support observations and correctly distinguishes completion, evidenced progress, no progress, and unresolved evidence. It adds no editing technique or unrelated constraint, and the composition is consistent with the original rubric.", "execution_ref": "f73a9dbfafeb8becbc3981783ebeb85c831248996fef2f6bd2eeedc7cafab443"}
| Check | Question | Evidence context | Final states | Consistency |
|---|---|---|---|---:|
| s1 | Are both the mug and the headphones visible enough to compare their positions? | [] | {} | None |
| s2 | Is the mug positioned to the right of the headphones? | ['s1'] | {} | None |
| fulfillment | Is the mug visibly positioned to the right of the headphones? | ['s1', 's2'] | {} | None |

## aurora-task-7b78f1229d9bb014bcc5::finetune_magicbrush_ag_something_kubric_15-15-1-1_init-magic_first_epoch=02-step=41999 / nested-required

Acceptance: {}
Stop: budget_exhausted: Case nested-required/aurora-task-7b78f1229d9bb014bcc5::finetune_magicbrush_ag_something_kubric_15-15-1-1_init-magic_first_epoch=02-step=41999 search allowance exhausted
Audit: {"accepted": true, "reason": "The program preserves the requested mug-to-the-right-of-headphones relation without adding editing techniques or unrelated constraints. Its support checks separately establish whether the comparison is observable, whether the final relation holds, and whether there is evidence of movement when the final relation is absent. The fulfillment readout uses those observations appropriately: completion does not require uncertain identity continuity, partial requires evidence of progress, no progress requires clear negative evidence, and unresolved evidence remains unknown. The checks do not themselves award completion credit, and the composition rules are consistent.", "execution_ref": "17ae77c9174b1658ffaed8390cd02dd337e0e6267987cb5271ffd5b84814749b"}
| Check | Question | Evidence context | Final states | Consistency |
|---|---|---|---|---:|
| s1 | Are both the mug and the headphones visible enough to compare their positions? | [] | {} | None |
| s2 | Is the mug positioned to the right of the headphones? | ['s1'] | {} | None |
| s3 | Comparing the source and edited images, what evidence indicates whether the source mug moved toward the right of the headphones, and whether a mug at the target is instead additional while the source mug remains elsewhere? | ['s1', 's2'] | {} | None |
| fulfillment | Is the mug visibly positioned to the right of the headphones? | ['s1', 's2', 's3'] | {} | None |

## aurora-task-88caae46533b0440f452::finetune_magicbrush_ag_something_kubric_15-15-1-1_init-magic_first_epoch=02-step=41999 / criterion-only

Acceptance: {}
Stop: budget_exhausted: Case criterion-only/aurora-task-88caae46533b0440f452::finetune_magicbrush_ag_something_kubric_15-15-1-1_init-magic_first_epoch=02-step=41999 search allowance exhausted
Audit: {"accepted": true, "reason": "The program preserves the requested book-behind-flower relation and the original yes/no/partial rubric. The completion support checks the same source objects and allows clear depth cues without making occlusion mandatory; the nested progress check separately looks for incomplete movement toward the relation. The readout uses both supports, awards completion only on the completion check\u2019s pass, and treats unknown evidence as unresolved rather than as failure. It does not count unrelated edits or add unrelated requirements. The nested check\u2019s activation on every parent status is appropriate for gathering separate progress evidence, and the program is within the apparent budget.", "execution_ref": "0e142691b3590e3bc9bc9c744dfd2a8bc80053bb6b93e4f454f3553506126033"}
| Check | Question | Evidence context | Final states | Consistency |
|---|---|---|---|---:|
| s1 | In the edited image, is the same blue-covered book from the source visibly behind the same rose from the source, with the rose in front, as shown by relative depth or occlusion? | [] | {} | None |
| s2 | Does the edited image show genuine progress toward placing the same source book behind the same source rose, even if the requested placement is incomplete? | [] | {} | None |
| fulfillment | Is the book visibly positioned behind the flower? | ['s1', 's2'] | {} | None |

## aurora-task-88caae46533b0440f452::finetune_magicbrush_ag_something_kubric_15-15-1-1_init-magic_first_epoch=02-step=41999 / nested-required

Acceptance: {}
Stop: round_limit
Audit: {"accepted": true, "reason": "The program preserves the sole requested change: placing the book behind the flower. s1 checks the requested relative depth and occlusion, while s2 separately checks for partial progress without treating unrelated edits as progress. The fulfillment readout correctly maps complete evidence to yes, progress without completion to partial, no progress to no, and insufficient evidence to unknown. Its dependencies and activation are consistent, and it adds no unrelated constraints or mandatory techniques.", "execution_ref": "07b4e4bdf886d02c76c58539c55ff4e0eca88099718dd6bd9874312e418d5e5c"}
| Check | Question | Evidence context | Final states | Consistency |
|---|---|---|---|---:|
| s1 | Is the book visibly positioned behind the flower, with the flower in front of it? | [] | {} | None |
| s2 | Does the image show any progress toward moving the book behind the flower, even if the requested placement is not complete? | [] | {} | None |
| fulfillment | Is the book visibly positioned behind the flower? | ['s1', 's2'] | {} | None |

## aurora-task-9a1ea55edac097679512::mgie / criterion-only

Acceptance: {}
Stop: confirmation_qualified
Audit: {"accepted": true, "reason": "The program preserves the sole requested change: stuffing the paper into the cup. Its progress check distinguishes an attempt from mere proximity or rim contact, and the nested completion check independently requires visible evidence of completed stuffing. The readout uses both observations consistently: completion is complete, evidenced progress without established completion is partial, clear absence of progress is absent, and unknown progress remains unresolved. It adds no unrelated constraints or mandatory techniques, and the support checks do not themselves award completion credit.", "execution_ref": "c34f49f3a18a9d2e6ebb517bd6a878b9b0ffb5be6e6d9433e0693ade94f245b3"}
| Check | Question | Evidence context | Final states | Consistency |
|---|---|---|---|---:|
| s1 | Does the edited image show any visible progress toward stuffing the paper into the cup, such as the paper entering or being positioned within the cup opening? | [] | {} | None |
| s2 | Does the edited image clearly show the paper stuffed inside the cup, rather than merely near or on its rim? | [] | {} | None |
| fulfillment | Does the image show the paper stuffed inside the cup? | ['s1', 's2'] | {} | None |

## aurora-task-9a1ea55edac097679512::mgie / nested-required

Acceptance: {}
Stop: round_limit
Audit: {"accepted": false, "reason": "The support checks do not provide sufficient evidence for the requested distinction between paper stuffed inside the cup and paper merely placed inside it. s1 asks for visible evidence of stuffing, but its criteria treat placement inside plus visible stuffing as a pass without defining what evidence establishes stuffing; s2 repeats that same ambiguity rather than checking a distinct, finer condition. The fulfillment readout then relies on those supports to decide completion, partial progress, or absence, so it cannot faithfully distinguish incomplete progress from no progress. The program also makes the fulfillment node active on every s2 status, including unknown, despite its parent being a support check; this is not itself a valid basis for resolving the missing evidence.", "execution_ref": "a91b87bdb4605c95c64126a9a41aad4faa109cdebfc60a2db4a429e66049444b"}
| Check | Question | Evidence context | Final states | Consistency |
|---|---|---|---|---:|
| s1 | Is the paper visibly inside the cup, with evidence it has been stuffed into it rather than merely resting nearby or on the rim? | [] | {} | None |
| s2 | Does the image provide enough evidence to determine whether the paper has been stuffed into the cup? | ['s1'] | {} | None |
| fulfillment | Does the image show the paper stuffed inside the cup? | ['s1', 's2'] | {} | None |

## aurora-task-bfa82afe32a86d47dfdf::finetune_magicbrush_ag_something_kubric_15-15-1-1_init-magic_first_epoch=02-step=41999 / criterion-only

Acceptance: {}
Stop: confirmation_qualified
Audit: {"accepted": true, "reason": "The program preserves the original request and rubric. It checks both requested aspects\u2014comic-book styling and photographic appearance\u2014without mandating a particular technique. The nested support check independently assesses photographic appearance, and the fulfillment rules correctly distinguish complete, partial, absent, and unknown using only support evidence. No unrelated constraint, unsupported inference, or composition conflict is apparent.", "execution_ref": "97faed3a037069e1d944f00695ce8618624db4fb9d4d2241c61c666ffe2cbbb6"}
| Check | Question | Evidence context | Final states | Consistency |
|---|---|---|---|---:|
| s1 | Does the edited image visibly have comic-book styling? | [] | {} | None |
| s2 | Does the edited image retain photographic subject matter and appearance? | [] | {} | None |
| fulfillment | Does the edited image fully look like a comic-book photo? | ['s1', 's2'] | {} | None |

## aurora-task-bfa82afe32a86d47dfdf::finetune_magicbrush_ag_something_kubric_15-15-1-1_init-magic_first_epoch=02-step=41999 / nested-required

Acceptance: {}
Stop: None
Audit: {}
| Check | Question | Evidence context | Final states | Consistency |
|---|---|---|---|---:|

## aurora-task-ce641cb29939011016cc::mgie / criterion-only

Acceptance: {}
Stop: None
Audit: {}
| Check | Question | Evidence context | Final states | Consistency |
|---|---|---|---|---:|

## aurora-task-ce641cb29939011016cc::mgie / nested-required

Acceptance: {}
Stop: None
Audit: {}
| Check | Question | Evidence context | Final states | Consistency |
|---|---|---|---|---:|

## aurora-task-e0f9b97dc3bc00415cf2::mgie / criterion-only

Acceptance: {}
Stop: None
Audit: {}
| Check | Question | Evidence context | Final states | Consistency |
|---|---|---|---|---:|

## aurora-task-e0f9b97dc3bc00415cf2::mgie / nested-required

Acceptance: {}
Stop: None
Audit: {}
| Check | Question | Evidence context | Final states | Consistency |
|---|---|---|---|---:|

## aurora-task-f335b1c6c0f2062b2cfd::finetune_magicbrush_ag_something_kubric_15-15-1-1_init-magic_first_epoch=02-step=41999 / criterion-only

Acceptance: {}
Stop: None
Audit: {}
| Check | Question | Evidence context | Final states | Consistency |
|---|---|---|---|---:|

## aurora-task-f335b1c6c0f2062b2cfd::finetune_magicbrush_ag_something_kubric_15-15-1-1_init-magic_first_epoch=02-step=41999 / nested-required

Acceptance: {}
Stop: None
Audit: {}
| Check | Question | Evidence context | Final states | Consistency |
|---|---|---|---|---:|
