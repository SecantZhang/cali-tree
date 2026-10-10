# Twelve-case saved-data analysis

Twelve previously observed local fitting cases. Four per reference class. No cross-case feedback, atomic correctness or held-out generalization claim.

Status: completed

| Case / reference | Arm | Seed → selected matches / 5 | Usable / 5 | Completed rounds | Checks | Status |
|---|---|---:|---:|---:|---:|---|
| transform the black DVD into a white DVD / no | criterion-only | pending | pending | unavailable | 0 | unresolved |
| transform the black DVD into a white DVD / no | nested-required | pending | pending | unavailable | 0 | unresolved |
| Make her close her jacket fully / yes | criterion-only | 0 → 0 | 5 | 7 | 3 | unconfirmed |
| Make her close her jacket fully / yes | nested-required | 0 → 0 | 5 | 15 | 3 | structural_failure |
| Change the image into pencil drawing / partial | criterion-only | 0 → 5 | 5 | 2 | 3 | locally_robust |
| Change the image into pencil drawing / partial | nested-required | 0 → 1 | 4 | 10 | 4 | unconfirmed |
| Give the woman a helmet / yes | criterion-only | 5 → 4 | 4 | 4 | 3 | unresolved |
| Give the woman a helmet / yes | nested-required | 5 → 4 | 4 | 15 | 3 | structural_failure |
| Change the background into a basketball court / yes | criterion-only | 5 → 4 | 5 | 6 | 3 | unconfirmed |
| Change the background into a basketball court / yes | nested-required | 3 → 0 | 2 | 12 | 4 | unconfirmed |
| Move the mug to the right of the headphones / partial | criterion-only | 0 → 0 | 5 | 12 | 3 | unconfirmed |
| Move the mug to the right of the headphones / partial | nested-required | 0 → 0 | 0 | 12 | 4 | unconfirmed |
| Move the book behind the flower / no | criterion-only | 5 → 3 | 3 | 6 | 3 | unconfirmed |
| Move the book behind the flower / no | nested-required | 5 → 5 | 5 | 15 | 3 | structural_failure |
| Stuffing the paper into the cup / no | criterion-only | 2 → 5 | 5 | 2 | 3 | locally_robust |
| Stuffing the paper into the cup / no | nested-required | 3 → 4 | 5 | 15 | 3 | structural_failure |
| Make this look like a comic book photo / no | criterion-only | 0 → 5 | 5 | 1 | 3 | locally_robust |
| Make this look like a comic book photo / no | nested-required | 0 → 5 | 5 | 14 | 4 | unconfirmed |
| Turn the image into a drawing made from chalk / partial | criterion-only | 0 → 5 | 5 | 1 | 3 | locally_robust |
| Turn the image into a drawing made from chalk / partial | nested-required | 0 → 5 | 5 | 15 | 4 | unconfirmed |
| Put a frog in the toilet / partial | criterion-only | 0 → 0 | 5 | 15 | 3 | unconfirmed |
| Put a frog in the toilet / partial | nested-required | 0 → 0 | 4 | 15 | 3 | structural_failure |
| the small gray rubber cylinder becomes brown / yes | criterion-only | pending | pending | unavailable | 0 | unresolved |
| the small gray rubber cylinder becomes brown / yes | nested-required | pending | pending | unavailable | 0 | unresolved |

Pending final measurements are unavailable, not zero accuracy. Missing/invalid cases will remain in the full denominator of a completed comparison. Five repeats are measurements within cases, not independent cases. Confidence is self-report and atomic consistency is not correctness.

## Class metrics

{
  "criterion-only": {
    "yes": {
      "cases": 4,
      "mean_selected_agreement": 0.4,
      "mean_selected_coverage": 0.7,
      "locally_robust": 0,
      "finalized_cases": 3
    },
    "partial": {
      "cases": 4,
      "mean_selected_agreement": 0.5,
      "mean_selected_coverage": 1.0,
      "locally_robust": 2,
      "finalized_cases": 4
    },
    "no": {
      "cases": 4,
      "mean_selected_agreement": 0.65,
      "mean_selected_coverage": 0.65,
      "locally_robust": 2,
      "finalized_cases": 3
    }
  },
  "nested-required": {
    "yes": {
      "cases": 4,
      "mean_selected_agreement": 0.2,
      "mean_selected_coverage": 0.55,
      "locally_robust": 0,
      "finalized_cases": 3
    },
    "partial": {
      "cases": 4,
      "mean_selected_agreement": 0.3,
      "mean_selected_coverage": 0.65,
      "locally_robust": 0,
      "finalized_cases": 4
    },
    "no": {
      "cases": 4,
      "mean_selected_agreement": 0.7,
      "mean_selected_coverage": 0.75,
      "locally_robust": 0,
      "finalized_cases": 3
    }
  }
}

## Usage

{
  "calls": 2364,
  "completion_tokens_charged": 420200,
  "completion_tokens_reported": 306536,
  "input_tokens": 7288931,
  "outcomes": {
    "completed": 2292,
    "transport_error": 72
  },
  "stages": {
    "gradient": 586,
    "propose_typed": 206,
    "audit": 148,
    "check": 1210,
    "visual_discovery": 202,
    "compile_typed": 12
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

Acceptance: {"qualified": false, "reasons": ["target_mismatch", "confirmation_missing_or_unqualified"], "policy": {"repeats": 5, "agreement": 0.8, "consistency": 0.8, "confidence": 0.8, "minimum_eligible": 3}, "reference_conflict_suspected": true}
Stop: budget_exhausted: Case criterion-only/aurora-task-4d9932789529604a30e8::finetune_magicbrush_ag_something_kubric_15-15-1-1_init-magic_first_epoch=02-step=41999 search allowance exhausted
Audit: {"accepted": true, "reason": "The program preserves the request to close the jacket fully. Its support checks separately assess visible progress and the complete-closure endpoint, and the readout correctly maps complete closure to complete, evidenced progress with incomplete closure to partial, no progress to absent, and insufficient evidence to unknown. The nested check is active for every parent result and independently examines the finer condition; the readout uses both observations without treating support checks as completion credit. No unrelated constraints or unsupported inferences are added.", "execution_ref": "cb71d7bff8c54eea2618b12aff2e45aff3ec547adf51e0bd8dae30d33c390462"}
| Check | Question | Evidence context | Final states | Consistency |
|---|---|---|---|---:|
| s1 | Is the woman's jacket visibly closed more than in the input image, with its front panels brought together at least in part? | [] | {"fail": 5} | 1.0 |
| s2 | Is the woman's jacket fully closed, with no visible opening remaining along its closure? | ['s1'] | {"fail": 5} | 1.0 |
| fulfillment | Is the woman's jacket fully closed? | ['s1', 's2'] | {"absent": 5} | 1.0 |

## aurora-task-4d9932789529604a30e8::finetune_magicbrush_ag_something_kubric_15-15-1-1_init-magic_first_epoch=02-step=41999 / nested-required

Acceptance: {"qualified": false, "reasons": ["target_mismatch", "confirmation_missing_or_unqualified", "no_eligible_executed_nested_check"], "policy": {"repeats": 5, "agreement": 0.8, "consistency": 0.8, "confidence": 0.8, "minimum_eligible": 3}, "reference_conflict_suspected": true}
Stop: round_limit
Audit: {"accepted": true, "reason": "The program preserves the request to close the jacket fully. Its support checks separately assess visible progress and the complete-closure endpoint, and the readout correctly maps complete closure to complete, evidenced progress with incomplete closure to partial, no progress to absent, and insufficient evidence to unknown. The nested check is active for every parent result and independently examines the finer condition; the readout uses both observations without treating support checks as completion credit. No unrelated constraints or unsupported inferences are added.", "execution_ref": "cb71d7bff8c54eea2618b12aff2e45aff3ec547adf51e0bd8dae30d33c390462"}
| Check | Question | Evidence context | Final states | Consistency |
|---|---|---|---|---:|
| s1 | Is the woman's jacket visibly closed more than in the input image, with its front panels brought together at least in part? | [] | {"fail": 5} | 1.0 |
| s2 | Is the woman's jacket fully closed, with no visible opening remaining along its closure? | ['s1'] | {"fail": 5} | 1.0 |
| fulfillment | Is the woman's jacket fully closed? | ['s1', 's2'] | {"absent": 5} | 1.0 |

## aurora-task-52fd3fa52d915723d12d::mgie / criterion-only

Acceptance: {"qualified": true, "reasons": [], "policy": {"repeats": 5, "agreement": 0.8, "consistency": 0.8, "confidence": 0.8, "minimum_eligible": 3}}
Stop: confirmation_qualified
Audit: {"accepted": true, "reason": "The program preserves the instruction and rubric. Its support checks separately assess overall pencil-drawing completion and image-grounded progress, without making monochrome or a particular technique mandatory. The fulfillment readout composes both observations correctly: completion requires the overall rendering check to pass; partial requires evidenced progress without completion; and no requires evidence of neither. Unresolved evidence remains unknown, and unrelated edits do not count. The nested check can use its parent observation as context while independently assessing progress. No unsupported inference, contradictory composition rule, or unjustified non-applicability is present.", "execution_ref": "44eb5d95548dbf6faf44f89acbf1044585f1ba07eb1e0942fdd484e5e253bc2a"}
| Check | Question | Evidence context | Final states | Consistency |
|---|---|---|---|---:|
| s1 | Does the edited image show the original scene rendered overall as a pencil drawing, rather than merely receiving muted color, grain, or softened photographic shading? | [] | {"fail": 5} | 1.0 |
| s2 | Is there image-grounded evidence of any relevant progress toward rendering the content as a pencil drawing, even if the overall transformation is incomplete? | [] | {"pass": 5} | 1.0 |
| fulfillment | Does the image visibly appear as a completed pencil drawing? | ['s1', 's2'] | {"partial": 5} | 1.0 |

## aurora-task-52fd3fa52d915723d12d::mgie / nested-required

Acceptance: {"qualified": false, "reasons": ["unresolved", "target_mismatch", "requirement_instability", "node_instability:s3", "node_instability:fulfillment", "confidence", "confirmation_missing_or_unqualified"], "policy": {"repeats": 5, "agreement": 0.8, "consistency": 0.8, "confidence": 0.8, "minimum_eligible": 3}}
Stop: budget_exhausted: Case nested-required/aurora-task-52fd3fa52d915723d12d::mgie search allowance exhausted
Audit: {"accepted": true, "reason": "The program preserves the request to render the image as a pencil drawing without imposing a particular technique. Its supports separately assess visible progress and whole-image completion; the fulfillment readout correctly distinguishes complete, partial, absent, and unresolved evidence, and does not treat support passes alone as completion. The nested checks can assess their own propositions using ancestor observations as context, and the composition rules are consistent.", "execution_ref": "1ca7ac5ccfced4b83e3eeb5347023929241a8e19262edb217011446b9e34e013"}
| Check | Question | Evidence context | Final states | Consistency |
|---|---|---|---|---:|
| s1 | Does the image show the original visual content rendered in a pencil-drawn style? | [] | {"pass": 5} | 1.0 |
| s2 | Is there image-grounded evidence of any progress toward rendering the content as a pencil drawing, even if the transformation is incomplete? | [] | {"pass": 5} | 1.0 |
| s3 | Does the edited image, considered as a whole, visibly read as a pencil drawing of its content rather than an image with only limited pencil-style treatment? | ['s2'] | {"pass": 3, "unknown": 1, "fail": 1} | 0.6 |
| fulfillment | Does the image visibly appear as a completed pencil drawing? | ['s1', 's2', 's3'] | {"complete": 3, "partial": 1} | 0.75 |

## aurora-task-538ef5e1e9d068bbfe6d::magic_reproduce_epoch=47-step=12999 / criterion-only

Acceptance: {"qualified": false, "reasons": ["unresolved", "confidence"], "policy": {"repeats": 5, "agreement": 0.8, "consistency": 0.8, "confidence": 0.8, "minimum_eligible": 3}}
Stop: confirmation_qualified
Audit: {"accepted": true, "reason": "The program preserves the request to give the source woman a helmet. Its support checks separately assess visible completion and visible, incomplete helmet-placement progress; the nested check does not treat a coarse pass as proof of a finer condition. The fulfillment readout uses those observations consistently: completion takes precedence, evidenced incomplete progress is partial, no progress is absent, and insufficient evidence remains unknown. The checks add no unrelated constraints or mandatory techniques, and the composition rules do not conflict.", "execution_ref": "209aee965374c28432b3e8b6b0784108817148f428d3825c35198209037730ac"}
| Check | Question | Evidence context | Final states | Consistency |
|---|---|---|---|---:|
| s1 | Does the image show a helmet visibly on the woman’s head? | [] | {"pass": 5} | 1.0 |
| s2 | Does the edited image show the source woman with a helmet-related change that is visibly incomplete—for example, a helmet being placed but not yet on her head? | [] | {"fail": 4, "unknown": 1} | 0.8 |
| fulfillment | Is a helmet visibly present on the woman’s head? | ['s1', 's2'] | {"complete": 4} | 1.0 |

## aurora-task-538ef5e1e9d068bbfe6d::magic_reproduce_epoch=47-step=12999 / nested-required

Acceptance: {"qualified": false, "reasons": ["semantic_audit", "unresolved", "confidence", "confirmation_missing_or_unqualified", "no_eligible_executed_nested_check"], "policy": {"repeats": 5, "agreement": 0.8, "consistency": 0.8, "confidence": 0.8, "minimum_eligible": 3}}
Stop: round_limit
Audit: {"accepted": false, "reason": "The fulfillment readout cannot faithfully distinguish a complete result from partial progress. s2 is defined to pass only when it shows progress but does not establish the complete result in s1, yet the readout says partial if s1 does not pass and s2 passes. If s1 is unknown while s2 passes, this can label the result partial without establishing incompleteness; if s1 fails, the checks may also conflict about whether a helmet is present. The composition should require evidenced incompleteness before assigning partial and resolve contradictory support observations rather than treating them as a valid outcome.", "execution_ref": "13d9d8e7d18bdb5b958b9091838d54563dd9c83726f282579de23f34834008da"}
| Check | Question | Evidence context | Final states | Consistency |
|---|---|---|---|---:|
| s1 | Does the image show a helmet visibly on the woman’s head? | [] | {"pass": 5} | 1.0 |
| s2 | Is there image evidence that a helmet has been added to the woman, even if the requested result is not complete? | [] | {"pass": 4, "unknown": 1} | 0.8 |
| fulfillment | Is a helmet visibly present on the woman’s head? | ['s1', 's2'] | {"complete": 4} | 1.0 |

## aurora-task-65581617ad341fa398cb::magic_reproduce_epoch=47-step=12999 / criterion-only

Acceptance: {"qualified": false, "reasons": ["confidence", "confirmation_missing_or_unqualified"], "policy": {"repeats": 5, "agreement": 0.8, "consistency": 0.8, "confidence": 0.8, "minimum_eligible": 3}}
Stop: budget_exhausted: Case criterion-only/aurora-task-65581617ad341fa398cb::magic_reproduce_epoch=47-step=12999 search allowance exhausted
Audit: {"accepted": true, "reason": "The program preserves the requested background change and rubric. Its two supports separately assess a playing surface and court markings or basketball equipment; the nested check is active for every parent result and must inspect its own proposition rather than inherit the parent\u2019s conclusion. The image-free fulfillment readout uses both observations, requires both kinds of evidence for completion, allows either to support partial progress without treating it as sufficient for completion, and keeps insufficient evidence unresolved. It does not add unrelated constraints or unsupported inferences.", "execution_ref": "1e232385b0848736aa8c786f7e8738e40a1cdf7be1d368eb1bdc546608c805d1"}
| Check | Question | Evidence context | Final states | Consistency |
|---|---|---|---|---:|
| s1 | Does the image show a basketball playing surface as part of the background? | [] | {"fail": 4, "pass": 1} | 0.8 |
| s2 | Does the background show recognizable basketball-court markings or basketball equipment? | [] | {"pass": 5} | 1.0 |
| fulfillment | Does the image show the background changed into a recognizable basketball court? | ['s1', 's2'] | {"partial": 1, "complete": 4} | 0.8 |

## aurora-task-65581617ad341fa398cb::magic_reproduce_epoch=47-step=12999 / nested-required

Acceptance: {"qualified": false, "reasons": ["unresolved", "target_mismatch", "requirement_instability", "node_instability:s1", "node_instability:s3", "insufficient_activation:fulfillment", "confidence", "confirmation_missing_or_unqualified"], "policy": {"repeats": 5, "agreement": 0.8, "consistency": 0.8, "confidence": 0.8, "minimum_eligible": 3}}
Stop: budget_exhausted: Case nested-required/aurora-task-65581617ad341fa398cb::magic_reproduce_epoch=47-step=12999 search allowance exhausted
Audit: {"accepted": true, "reason": "The program preserves the requested background change and rubric. Its supports separately assess a basketball playing surface, court markings or equipment, and whether those features form a coherent court; the nested checks do not treat a broad pass as proof of a finer condition. The fulfillment readout uses only support evidence, distinguishes completion from progress and absence, and leaves necessary unknowns unresolved. The equipment-or-markings support can establish progress without being treated as completion, and the coherence check appropriately tests the requested whole-background result. No unrelated constraints, unsupported inferences, or contradictory composition rules are apparent.", "execution_ref": "0f776eb206cedb688401b6bc13d53ee1677f3bfc10c1b2afa1bbe1871564dc2d"}
| Check | Question | Evidence context | Final states | Consistency |
|---|---|---|---|---:|
| s1 | Does the image show a basketball playing surface as part of the background? | [] | {"fail": 3, "unknown": 1, "pass": 1} | 0.6 |
| s2 | Does the background show recognizable basketball-court markings or basketball equipment? | [] | {"pass": 4, "unknown": 1} | 0.8 |
| s3 | Do the visible court markings and playing surface together make the background read as a coherent basketball court, rather than isolated court features against a predominantly featureless backdrop? | ['s1', 's2'] | {"unknown": 1, "fail": 2} | 0.6666666666666666 |
| fulfillment | Does the image show the background changed into a recognizable basketball court? | ['s1', 's2', 's3'] | {"partial": 2} | 1.0 |

## aurora-task-7b78f1229d9bb014bcc5::finetune_magicbrush_ag_something_kubric_15-15-1-1_init-magic_first_epoch=02-step=41999 / criterion-only

Acceptance: {"qualified": false, "reasons": ["target_mismatch", "confirmation_missing_or_unqualified"], "policy": {"repeats": 5, "agreement": 0.8, "consistency": 0.8, "confidence": 0.8, "minimum_eligible": 3}, "reference_conflict_suspected": true}
Stop: budget_exhausted: Case criterion-only/aurora-task-7b78f1229d9bb014bcc5::finetune_magicbrush_ag_something_kubric_15-15-1-1_init-magic_first_epoch=02-step=41999 search allowance exhausted
Audit: {"accepted": true, "reason": "The program preserves the sole requested change and its spatial relation. The broad support check assesses whether the objects and comparison are observable; the nested check independently assesses whether the mug is to the right, without treating the parent pass as fulfillment. The readout uses both support observations and correctly distinguishes completion, evidenced progress, no progress, and unresolved evidence. It adds no editing technique or unrelated constraint, and the composition is consistent with the original rubric.", "execution_ref": "f73a9dbfafeb8becbc3981783ebeb85c831248996fef2f6bd2eeedc7cafab443"}
| Check | Question | Evidence context | Final states | Consistency |
|---|---|---|---|---:|
| s1 | Are both the mug and the headphones visible enough to compare their positions? | [] | {"pass": 5} | 1.0 |
| s2 | Is the mug positioned to the right of the headphones? | ['s1'] | {"pass": 5} | 1.0 |
| fulfillment | Is the mug visibly positioned to the right of the headphones? | ['s1', 's2'] | {"complete": 5} | 1.0 |

## aurora-task-7b78f1229d9bb014bcc5::finetune_magicbrush_ag_something_kubric_15-15-1-1_init-magic_first_epoch=02-step=41999 / nested-required

Acceptance: {"qualified": false, "reasons": ["unresolved", "target_mismatch", "requirement_instability", "node_instability:s3", "confidence", "confirmation_missing_or_unqualified"], "policy": {"repeats": 5, "agreement": 0.8, "consistency": 0.8, "confidence": 0.8, "minimum_eligible": 3}}
Stop: budget_exhausted: Case nested-required/aurora-task-7b78f1229d9bb014bcc5::finetune_magicbrush_ag_something_kubric_15-15-1-1_init-magic_first_epoch=02-step=41999 search allowance exhausted
Audit: {"accepted": true, "reason": "The program preserves the requested mug-to-the-right-of-headphones relation without adding editing techniques or unrelated constraints. Its support checks separately establish whether the comparison is observable, whether the final relation holds, and whether there is evidence of movement when the final relation is absent. The fulfillment readout uses those observations appropriately: completion does not require uncertain identity continuity, partial requires evidence of progress, no progress requires clear negative evidence, and unresolved evidence remains unknown. The checks do not themselves award completion credit, and the composition rules are consistent.", "execution_ref": "17ae77c9174b1658ffaed8390cd02dd337e0e6267987cb5271ffd5b84814749b"}
| Check | Question | Evidence context | Final states | Consistency |
|---|---|---|---|---:|
| s1 | Are both the mug and the headphones visible enough to compare their positions? | [] | {"pass": 5} | 1.0 |
| s2 | Is the mug positioned to the right of the headphones? | ['s1'] | {"pass": 4, "unknown": 1} | 0.8 |
| s3 | Comparing the source and edited images, what evidence indicates whether the source mug moved toward the right of the headphones, and whether a mug at the target is instead additional while the source mug remains elsewhere? | ['s1', 's2'] | {"unknown": 4} | 0.0 |
| fulfillment | Is the mug visibly positioned to the right of the headphones? | ['s1', 's2', 's3'] | {} | None |

## aurora-task-88caae46533b0440f452::finetune_magicbrush_ag_something_kubric_15-15-1-1_init-magic_first_epoch=02-step=41999 / criterion-only

Acceptance: {"qualified": false, "reasons": ["unresolved", "target_mismatch", "requirement_instability", "node_instability:fulfillment", "confirmation_missing_or_unqualified"], "policy": {"repeats": 5, "agreement": 0.8, "consistency": 0.8, "confidence": 0.8, "minimum_eligible": 3}}
Stop: budget_exhausted: Case criterion-only/aurora-task-88caae46533b0440f452::finetune_magicbrush_ag_something_kubric_15-15-1-1_init-magic_first_epoch=02-step=41999 search allowance exhausted
Audit: {"accepted": true, "reason": "The program preserves the requested book-behind-flower relation and the original yes/no/partial rubric. The completion support checks the same source objects and allows clear depth cues without making occlusion mandatory; the nested progress check separately looks for incomplete movement toward the relation. The readout uses both supports, awards completion only on the completion check\u2019s pass, and treats unknown evidence as unresolved rather than as failure. It does not count unrelated edits or add unrelated requirements. The nested check\u2019s activation on every parent status is appropriate for gathering separate progress evidence, and the program is within the apparent budget.", "execution_ref": "0e142691b3590e3bc9bc9c744dfd2a8bc80053bb6b93e4f454f3553506126033"}
| Check | Question | Evidence context | Final states | Consistency |
|---|---|---|---|---:|
| s1 | In the edited image, is the same blue-covered book from the source visibly behind the same rose from the source, with the rose in front, as shown by relative depth or occlusion? | [] | {"fail": 5} | 1.0 |
| s2 | Does the edited image show genuine progress toward placing the same source book behind the same source rose, even if the requested placement is incomplete? | [] | {"fail": 5} | 1.0 |
| fulfillment | Is the book visibly positioned behind the flower? | ['s1', 's2'] | {"unknown": 2, "absent": 3} | 0.6 |

## aurora-task-88caae46533b0440f452::finetune_magicbrush_ag_something_kubric_15-15-1-1_init-magic_first_epoch=02-step=41999 / nested-required

Acceptance: {"qualified": false, "reasons": ["confirmation_missing_or_unqualified", "no_eligible_executed_nested_check"], "policy": {"repeats": 5, "agreement": 0.8, "consistency": 0.8, "confidence": 0.8, "minimum_eligible": 3}}
Stop: round_limit
Audit: {"accepted": true, "reason": "The program preserves the sole requested change: placing the book behind the flower. s1 checks the requested relative depth and occlusion, while s2 separately checks for partial progress without treating unrelated edits as progress. The fulfillment readout correctly maps complete evidence to yes, progress without completion to partial, no progress to no, and insufficient evidence to unknown. Its dependencies and activation are consistent, and it adds no unrelated constraints or mandatory techniques.", "execution_ref": "07b4e4bdf886d02c76c58539c55ff4e0eca88099718dd6bd9874312e418d5e5c"}
| Check | Question | Evidence context | Final states | Consistency |
|---|---|---|---|---:|
| s1 | Is the book visibly positioned behind the flower, with the flower in front of it? | [] | {"fail": 5} | 1.0 |
| s2 | Does the image show any progress toward moving the book behind the flower, even if the requested placement is not complete? | [] | {"fail": 5} | 1.0 |
| fulfillment | Is the book visibly positioned behind the flower? | ['s1', 's2'] | {"absent": 5} | 1.0 |

## aurora-task-9a1ea55edac097679512::mgie / criterion-only

Acceptance: {"qualified": true, "reasons": [], "policy": {"repeats": 5, "agreement": 0.8, "consistency": 0.8, "confidence": 0.8, "minimum_eligible": 3}}
Stop: confirmation_qualified
Audit: {"accepted": true, "reason": "The program preserves the sole requested change: stuffing the paper into the cup. Its progress check distinguishes an attempt from mere proximity or rim contact, and the nested completion check independently requires visible evidence of completed stuffing. The readout uses both observations consistently: completion is complete, evidenced progress without established completion is partial, clear absence of progress is absent, and unknown progress remains unresolved. It adds no unrelated constraints or mandatory techniques, and the support checks do not themselves award completion credit.", "execution_ref": "c34f49f3a18a9d2e6ebb517bd6a878b9b0ffb5be6e6d9433e0693ade94f245b3"}
| Check | Question | Evidence context | Final states | Consistency |
|---|---|---|---|---:|
| s1 | Does the edited image show any visible progress toward stuffing the paper into the cup, such as the paper entering or being positioned within the cup opening? | [] | {"fail": 5} | 1.0 |
| s2 | Does the edited image clearly show the paper stuffed inside the cup, rather than merely near or on its rim? | [] | {"fail": 5} | 1.0 |
| fulfillment | Does the image show the paper stuffed inside the cup? | ['s1', 's2'] | {"absent": 5} | 1.0 |

## aurora-task-9a1ea55edac097679512::mgie / nested-required

Acceptance: {"qualified": false, "reasons": ["semantic_audit", "node_instability:s2", "confidence", "confirmation_missing_or_unqualified", "no_eligible_executed_nested_check"], "policy": {"repeats": 5, "agreement": 0.8, "consistency": 0.8, "confidence": 0.8, "minimum_eligible": 3}}
Stop: round_limit
Audit: {"accepted": false, "reason": "The support checks do not provide sufficient evidence for the requested distinction between paper stuffed inside the cup and paper merely placed inside it. s1 asks for visible evidence of stuffing, but its criteria treat placement inside plus visible stuffing as a pass without defining what evidence establishes stuffing; s2 repeats that same ambiguity rather than checking a distinct, finer condition. The fulfillment readout then relies on those supports to decide completion, partial progress, or absence, so it cannot faithfully distinguish incomplete progress from no progress. The program also makes the fulfillment node active on every s2 status, including unknown, despite its parent being a support check; this is not itself a valid basis for resolving the missing evidence.", "execution_ref": "a91b87bdb4605c95c64126a9a41aad4faa109cdebfc60a2db4a429e66049444b"}
| Check | Question | Evidence context | Final states | Consistency |
|---|---|---|---|---:|
| s1 | Is the paper visibly inside the cup, with evidence it has been stuffed into it rather than merely resting nearby or on the rim? | [] | {"fail": 5} | 1.0 |
| s2 | Does the image provide enough evidence to determine whether the paper has been stuffed into the cup? | ['s1'] | {"fail": 3, "pass": 2} | 0.6 |
| fulfillment | Does the image show the paper stuffed inside the cup? | ['s1', 's2'] | {"absent": 4, "partial": 1} | 0.8 |

## aurora-task-bfa82afe32a86d47dfdf::finetune_magicbrush_ag_something_kubric_15-15-1-1_init-magic_first_epoch=02-step=41999 / criterion-only

Acceptance: {"qualified": true, "reasons": [], "policy": {"repeats": 5, "agreement": 0.8, "consistency": 0.8, "confidence": 0.8, "minimum_eligible": 3}}
Stop: confirmation_qualified
Audit: {"accepted": true, "reason": "The program preserves the original request and rubric. It checks both requested aspects\u2014comic-book styling and photographic appearance\u2014without mandating a particular technique. The nested support check independently assesses photographic appearance, and the fulfillment rules correctly distinguish complete, partial, absent, and unknown using only support evidence. No unrelated constraint, unsupported inference, or composition conflict is apparent.", "execution_ref": "97faed3a037069e1d944f00695ce8618624db4fb9d4d2241c61c666ffe2cbbb6"}
| Check | Question | Evidence context | Final states | Consistency |
|---|---|---|---|---:|
| s1 | Does the edited image visibly have comic-book styling? | [] | {"fail": 5} | 1.0 |
| s2 | Does the edited image retain photographic subject matter and appearance? | [] | {"pass": 5} | 1.0 |
| fulfillment | Does the edited image fully look like a comic-book photo? | ['s1', 's2'] | {"absent": 5} | 1.0 |

## aurora-task-bfa82afe32a86d47dfdf::finetune_magicbrush_ag_something_kubric_15-15-1-1_init-magic_first_epoch=02-step=41999 / nested-required

Acceptance: {"qualified": false, "reasons": ["confirmation_missing_or_unqualified"], "policy": {"repeats": 5, "agreement": 0.8, "consistency": 0.8, "confidence": 0.8, "minimum_eligible": 3}}
Stop: budget_exhausted: Case nested-required/aurora-task-bfa82afe32a86d47dfdf::finetune_magicbrush_ag_something_kubric_15-15-1-1_init-magic_first_epoch=02-step=41999 search allowance exhausted
Audit: {"accepted": true, "reason": "The program preserves the request and rubric. Its support checks separately assess comic-book styling, photographic appearance, and attributable progress relative to the source; the nested checks do not treat a broad pass as proof of a finer condition. The fulfillment rule requires both styling and progress for completion, allows partial only when progress is established and incompleteness is evidenced, and leaves unresolved evidence unknown. It does not impose a particular technique or unrelated constraint, and the composition rules are consistent.", "execution_ref": "05c3d9a517f83ece2c7b7ba3e62cff6c7365af88f6d013be49f073805478ce8d"}
| Check | Question | Evidence context | Final states | Consistency |
|---|---|---|---|---:|
| s1 | Does the edited image visibly have comic-book styling? | [] | {"fail": 5} | 1.0 |
| s2 | Does the edited image retain recognizable photographic subject matter and appearance? | [] | {"pass": 5} | 1.0 |
| s3 | Compared with the supplied source, does the edited image show a visible change toward a comic-book-photo appearance? | ['s1', 's2'] | {"fail": 5} | 1.0 |
| fulfillment | Does the edited image fully look like a comic-book photo? | ['s1', 's2', 's3'] | {"absent": 5} | 1.0 |

## aurora-task-ce641cb29939011016cc::mgie / criterion-only

Acceptance: {"qualified": true, "reasons": [], "policy": {"repeats": 5, "agreement": 0.8, "consistency": 0.8, "confidence": 0.8, "minimum_eligible": 3}}
Stop: confirmation_qualified
Audit: {"accepted": true, "reason": "The program preserves the request to make the image a chalk drawing. Its support checks distinguish genuine drawing-like progress from convincing whole-image chalk fulfillment, and the readout maps those observations to complete, partial, absent, or unknown without treating uncertainty as failure or support checks as completion credit. The nested check is active for every parent result and independently assesses the finer condition. No unrelated constraints or unsupported inferences are added.", "execution_ref": "dfdeac464b8f44735b45baea24ddbde3c26338d0d94a2d2c18d31ddcc1bf6fea"}
| Check | Question | Evidence context | Final states | Consistency |
|---|---|---|---|---:|
| s1 | Does the edited image show visible progress toward a chalk drawing compared with the source, rather than only unrelated changes? | [] | {"pass": 5} | 1.0 |
| s2 | Does the image as a whole convincingly read as a drawing made from chalk, rather than mainly as a softened or blurred photograph with a grainy overlay? | [] | {"fail": 5} | 1.0 |
| fulfillment | Does the edited image visibly fulfill the request to turn the image into a drawing made from chalk? | ['s1', 's2'] | {"partial": 5} | 1.0 |

## aurora-task-ce641cb29939011016cc::mgie / nested-required

Acceptance: {"qualified": false, "reasons": ["confirmation_missing_or_unqualified"], "policy": {"repeats": 5, "agreement": 0.8, "consistency": 0.8, "confidence": 0.8, "minimum_eligible": 3}}
Stop: round_limit
Audit: {"accepted": true, "reason": "The program preserves the request to make the image a chalk drawing and distinguishes drawing-like rendering from mere texture, then checks whether that rendering covers the image as a whole. The fulfillment readout uses the separate findings to distinguish completion, partial progress, absence, and unresolved evidence; it does not treat support passes as completion credit or infer unsupported facts. The nested checks are active for all parent statuses, and their evidence dependencies are explicit. No unrelated constraint or mandatory technique is added.", "execution_ref": "b808df3ccd0fd1a8a910551648177b7a6da99f50a2063e2559b20c0b51ee5456"}
| Check | Question | Evidence context | Final states | Consistency |
|---|---|---|---|---:|
| s1 | Does the edited image show visual evidence of a chalk-like drawing treatment applied to the input image? | [] | {"pass": 5} | 1.0 |
| s3 | Does the edited image read as a chalk drawing, rather than mainly as a softened or blurred image with grain? | ['s1'] | {"fail": 5} | 1.0 |
| s2 | Does the chalk-like drawing treatment transform the image as a whole, rather than appearing only as a partial effect? | ['s1'] | {"pass": 5} | 1.0 |
| fulfillment | Does the edited image visibly fulfill the request to turn the image into a drawing made from chalk? | ['s1', 's3', 's2'] | {"partial": 5} | 1.0 |

## aurora-task-e0f9b97dc3bc00415cf2::mgie / criterion-only

Acceptance: {"qualified": false, "reasons": ["target_mismatch", "confirmation_missing_or_unqualified"], "policy": {"repeats": 5, "agreement": 0.8, "consistency": 0.8, "confidence": 0.8, "minimum_eligible": 3}, "reference_conflict_suspected": true}
Stop: round_limit
Audit: {"accepted": true, "reason": "The program preserves the request to put a frog in the toilet and defines the requested placement as a recognizable frog visibly inside the bowl. Its support checks separately assess placement and visibility, allow unknown when evidence is insufficient, and do not treat support results as completion credit. The fulfillment readout uses both support observations, distinguishes complete placement from partial progress and no progress, and leaves unresolved evidence unknown. The nested checks do not impose extra mandatory techniques or unrelated constraints, and their composition is consistent.", "execution_ref": "78b293b241f8ea6d6588db229719709aca5f74dbf7546240112bd0b5d039e0e1"}
| Check | Question | Evidence context | Final states | Consistency |
|---|---|---|---|---:|
| s1 | Is a recognizable frog visibly situated within the toilet bowl, rather than merely on the lid, tank, rim, or floor? | [] | {"pass": 5} | 1.0 |
| s2 | Are the toilet bowl and its contents sufficiently visible to assess frog placement, and what frog locations are visibly distinguishable? | ['s1'] | {"pass": 5} | 1.0 |
| fulfillment | Is a frog visibly placed inside the toilet bowl? | ['s1', 's2'] | {"complete": 5} | 1.0 |

## aurora-task-e0f9b97dc3bc00415cf2::mgie / nested-required

Acceptance: {"qualified": false, "reasons": ["semantic_audit", "unresolved", "target_mismatch", "confidence", "confirmation_missing_or_unqualified", "no_eligible_executed_nested_check"], "policy": {"repeats": 5, "agreement": 0.8, "consistency": 0.8, "confidence": 0.8, "minimum_eligible": 3}}
Stop: round_limit
Audit: {"accepted": false, "reason": "The support checks do not provide separate evidence for partial progress. s1 only distinguishes a frog visibly inside the bowl from its absence or uncertainty, and s2 repeats that same visibility assessment. The fulfillment rule nevertheless allows partial when there is some progress toward placing a frog inside without a frog clearly within the bowl. With no support observation capable of establishing that progress, the readout cannot faithfully distinguish partial from no progress or unknown.", "execution_ref": "97d15227ba30d18240f8d7d78ae3ee94ad5446bd92e5e95db33754324b01952a"}
| Check | Question | Evidence context | Final states | Consistency |
|---|---|---|---|---:|
| s1 | Is a frog visibly present inside the toilet bowl? | [] | {"pass": 4, "unknown": 1} | 0.8 |
| s2 | Does the image provide sufficient evidence to determine whether the requested frog-in-toilet edit was made? | ['s1'] | {"pass": 4} | 1.0 |
| fulfillment | Is a frog visibly placed inside the toilet bowl? | ['s1', 's2'] | {"complete": 4} | 1.0 |

## aurora-task-f335b1c6c0f2062b2cfd::finetune_magicbrush_ag_something_kubric_15-15-1-1_init-magic_first_epoch=02-step=41999 / criterion-only

Acceptance: {}
Stop: GraphValidationError: s2 may reference only earlier support indices
Audit: {}
| Check | Question | Evidence context | Final states | Consistency |
|---|---|---|---|---:|

## aurora-task-f335b1c6c0f2062b2cfd::finetune_magicbrush_ag_something_kubric_15-15-1-1_init-magic_first_epoch=02-step=41999 / nested-required

Acceptance: {}
Stop: GraphValidationError: s2 may reference only earlier support indices
Audit: {}
| Check | Question | Evidence context | Final states | Consistency |
|---|---|---|---|---:|
