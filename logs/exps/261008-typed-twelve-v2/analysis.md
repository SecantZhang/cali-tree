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
| Change the background into a basketball court / yes | nested-required | pending | pending | unavailable | 0 | unattempted |
| Move the mug to the right of the headphones / partial | criterion-only | pending | pending | unavailable | 0 | unattempted |
| Move the mug to the right of the headphones / partial | nested-required | pending | pending | unavailable | 0 | unattempted |
| Move the book behind the flower / no | criterion-only | pending | pending | unavailable | 0 | unattempted |
| Move the book behind the flower / no | nested-required | pending | pending | unavailable | 0 | unattempted |
| Stuffing the paper into the cup / no | criterion-only | pending | pending | unavailable | 0 | unattempted |
| Stuffing the paper into the cup / no | nested-required | pending | pending | unavailable | 0 | unattempted |
| Make this look like a comic book photo / no | criterion-only | pending | pending | unavailable | 0 | unattempted |
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
  "calls": 684,
  "completion_tokens_charged": 133385,
  "completion_tokens_reported": 96521,
  "input_tokens": 2055093,
  "outcomes": {
    "completed": 659,
    "transport_error": 25
  },
  "stages": {
    "gradient": 210,
    "propose_typed": 71,
    "check": 268,
    "audit": 57,
    "visual_discovery": 72,
    "compile_typed": 6
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
Stop: None
Audit: {}
| Check | Question | Evidence context | Final states | Consistency |
|---|---|---|---|---:|

## aurora-task-7b78f1229d9bb014bcc5::finetune_magicbrush_ag_something_kubric_15-15-1-1_init-magic_first_epoch=02-step=41999 / criterion-only

Acceptance: {}
Stop: None
Audit: {}
| Check | Question | Evidence context | Final states | Consistency |
|---|---|---|---|---:|

## aurora-task-7b78f1229d9bb014bcc5::finetune_magicbrush_ag_something_kubric_15-15-1-1_init-magic_first_epoch=02-step=41999 / nested-required

Acceptance: {}
Stop: None
Audit: {}
| Check | Question | Evidence context | Final states | Consistency |
|---|---|---|---|---:|

## aurora-task-88caae46533b0440f452::finetune_magicbrush_ag_something_kubric_15-15-1-1_init-magic_first_epoch=02-step=41999 / criterion-only

Acceptance: {}
Stop: None
Audit: {}
| Check | Question | Evidence context | Final states | Consistency |
|---|---|---|---|---:|

## aurora-task-88caae46533b0440f452::finetune_magicbrush_ag_something_kubric_15-15-1-1_init-magic_first_epoch=02-step=41999 / nested-required

Acceptance: {}
Stop: None
Audit: {}
| Check | Question | Evidence context | Final states | Consistency |
|---|---|---|---|---:|

## aurora-task-9a1ea55edac097679512::mgie / criterion-only

Acceptance: {}
Stop: None
Audit: {}
| Check | Question | Evidence context | Final states | Consistency |
|---|---|---|---|---:|

## aurora-task-9a1ea55edac097679512::mgie / nested-required

Acceptance: {}
Stop: None
Audit: {}
| Check | Question | Evidence context | Final states | Consistency |
|---|---|---|---|---:|

## aurora-task-bfa82afe32a86d47dfdf::finetune_magicbrush_ag_something_kubric_15-15-1-1_init-magic_first_epoch=02-step=41999 / criterion-only

Acceptance: {}
Stop: None
Audit: {}
| Check | Question | Evidence context | Final states | Consistency |
|---|---|---|---|---:|

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
