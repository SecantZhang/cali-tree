# Fifteen-round typed evidence chalk pilot: saved-data analysis

One previously observed chalk case fitted locally. Repeats are within-case measurements. No atomic correctness or generalization claim.

Checkpoint: a3b80472e88be94bb4f3be4597c16cb3b67b2be1
Reference: `partial`. Status: completed

| Arm | Seed → selected matches / 5 | Selected usable / 5 | Completed repair rounds | Minimum reported confidence | Checks | Inserted nested checks | Status |
|---|---:|---:|---:|---:|---:|---|---|
| criterion-only | 0 → 0 | 3 | 11 | 0.88 | 3 | none | unconfirmed |
| nested-required | 0 → 5 | 5 | 4 | 0.94 | 4 | n4 | locally_robust |

Matches mean reference-label agreement; usable answers include wrong labels. Confidence is generated self-report. Five repeats are measurements within one previously observed case, not independent cases. Actual added-check execution and accuracy are separate outcomes.

## criterion-only

Acceptance: {"qualified": false, "reasons": ["unresolved", "target_mismatch", "requirement_instability", "node_instability:n1", "confidence", "confirmation_missing_or_unqualified"], "policy": {"repeats": 5, "agreement": 0.8, "consistency": 0.8, "confidence": 0.8, "minimum_eligible": 3}}
Search schedule: {"round_batches": [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1], "rounds_started": 12, "rounds_completed": 11, "stop_on_confirmation": true, "repair_failed_candidate": true}
Failed-confirmation follow-up rounds: [7, 8, 9, 10, 11, 12]
Selected audit: {"accepted": true, "reason": "The program preserves the request to convert the image into a chalk drawing. Its independent support checks assess chalk-like treatment and drawing form without treating either alone as sufficient; the requested readout requires both supports to establish a complete conversion across the image, allows partial only with affirmative evidence of progress, and keeps unsupported or ambiguous cases unresolved. The checks add no unrelated constraints or mandatory techniques, and the composition rules are consistent.", "execution_ref": "a3c6c0921226ff4b37278730ff7377353a40f7c76968ab0298a6abb497c4adbb"}
Complete confirmation: {"draws": 5, "agreement": 0.4, "coverage": 1.0, "confidence_pass": true}

| Check | Role / evidence context | Question | Final states | Consistency |
|---|---|---|---|---:|
| n1 | support / [] | Does the edited image visibly use a chalk-like medium or treatment, rather than merely showing generic blur, grain, or softened photographic detail? | {"pass": 3, "unknown": 2} | 0.6 |
| n2 | support / [] | Does the edited image visibly present its content as a drawing rather than as a photograph with blur or texture overlays? | {"pass": 4, "unknown": 1} | 0.8 |
| n3 | requested / ['n1', 'n2'] | Has the image been transformed into a drawing made from chalk? | {"complete": 3} | 1.0 |

### Typed edit history

- The existing supports are criterion-only and their traces show that texture and softened contours were over-read as proof of a chalk drawing. Tighten both thresholds to distinguish convincing drawn rendering from a photographic image with a chalk-like filter, and make the readout preserve partial progress without treating support failures as proof of absence.
  Operations: revise_support, revise_support, revise_readout
  Result: {"round": 0, "batch": 0, "index": 0, "program_ref": "51cbd86e2144a6b175a67a1b328822813858aa58ea2526300e39b6ea4097abf7", "structural_valid": true, "audit": {"accepted": false, "reason": "The requested readout is nested under n2, so it is activated only when n2 returns pass, fail, or unknown\u2014which covers all allowed support statuses. However, its composition rules are contradictory: partial requires at least one support to pass, while unknown applies when no support passes and at least one is unknown; these conditions overlap when one support is unknown and the other fails. The program therefore does not define a unique readout for that evidence combination.", "execution_ref": "4ff1e63ebbf9ee2a97e9eb00586f6767b467296fb59c81c68a248ea7540571c0"}}
  Constructed hashes: {"parent_ref": "5a2c20cd33d74218dffc09bf1abdf7c6c49e72bd3993510f50b2ce275ee89abd", "child_ref": "51cbd86e2144a6b175a67a1b328822813858aa58ea2526300e39b6ea4097abf7"}
- The existing checks capture real chalk-like and drawn treatment, but their broad pass criteria let localized or uneven styling imply full conversion. Refine both supports to preserve mixed coverage evidence, then make the readout distinguish evidenced progress from complete whole-image conversion without treating a support failure as proof of absence. This is criterion-only and retains the three checks.
  Operations: revise_support, revise_support, revise_readout
  Result: {"round": 1, "batch": 0, "index": 0, "program_ref": "5459a190d1bbea213f0ebf7e683880e57697e9f7087af08f698bb5aeecea0621", "structural_valid": true, "audit": {"accepted": false, "reason": "The support checks do not establish the requested extent reliably. n1 treats broad coverage of the main depicted content as evidence of progress but does not determine whether the whole image has been converted; n2 likewise allows a pass for drawing treatment across depicted content without defining or checking substantial unconverted areas consistently. The readout then permits complete when both supports pass and their evidence establishes broad treatment, so it can infer full-image conversion from coarse coverage. This fails the requirement that a coarse support pass not imply an unexamined finer condition.", "execution_ref": "5db6434cead3c8c0e79acb016ec3738a8e6365887012fd9f4f578742d58b2d1b"}}
  Constructed hashes: {"parent_ref": "5a2c20cd33d74218dffc09bf1abdf7c6c49e72bd3993510f50b2ce275ee89abd", "child_ref": "5459a190d1bbea213f0ebf7e683880e57697e9f7087af08f698bb5aeecea0621"}
- The existing observations establish chalk-like treatment and some drawing-like rendering, but do not establish that the whole scene is converted. Revise the readout to treat those passes as evidence of progress, not completion; retain unknown when evidence does not resolve progress and avoid treating support failures as proof of absence.
  Operations: revise_readout
  Result: {"round": 2, "batch": 0, "index": 0, "program_ref": "8dae971c381fbcc1df7080e8c466db90b770fd332ca90252472d8399c6323c6c", "structural_valid": true, "audit": {"accepted": false, "reason": "The support checks cover chalk-like treatment and drawing form, but neither establishes whether the conversion applies to the image as a whole. The requested readout requires both supports to pass and their evidence to explicitly establish whole-image conversion, yet the supports do not collect that extent evidence. This leaves complete fulfillment unprovable even when both pass, so the program does not preserve the requested property and extent.", "execution_ref": "d335d02a3535c7509598ac3e031b2f2d6e296b183c7bae2401e95d2a39b20b31"}}
  Constructed hashes: {"parent_ref": "5a2c20cd33d74218dffc09bf1abdf7c6c49e72bd3993510f50b2ce275ee89abd", "child_ref": "8dae971c381fbcc1df7080e8c466db90b770fd332ca90252472d8399c6323c6c"}
- The existing supports establish chalk-like treatment and drawing cues, but not whether the requested conversion is complete across the image. Refine the readout to treat those cues as evidence of progress only; completion requires explicit evidence of whole-image conversion, and support failures alone do not prove absence.
  Operations: revise_readout
  Result: {"round": 3, "batch": 0, "index": 0, "program_ref": "7ea15301f1a1af99a73ce103860d5088814f713acf1df76fa34b25ab0c12aa9b", "structural_valid": true, "audit": {"accepted": false, "reason": "The requested readout requires evidence that the image as a whole was converted into a chalk drawing, but neither support check assesses whole-image coverage or remaining photographic areas. The readout cannot establish those facts from the saved observations, so its complete/partial criteria are unsupported. In addition, n3 treats both supports failing as absence, although failure only establishes that each specific cue was not established; the criteria themselves acknowledge that this does not prove no requested progress. The program therefore risks converting missing evidence into a negative result.", "execution_ref": "f17a33adee7b4136f1cf79e81209dfca1798404674faced860c0b4fc4b6029c0"}}
  Constructed hashes: {"parent_ref": "5a2c20cd33d74218dffc09bf1abdf7c6c49e72bd3993510f50b2ce275ee89abd", "child_ref": "7ea15301f1a1af99a73ce103860d5088814f713acf1df76fa34b25ab0c12aa9b"}
- The existing supports can be made more discriminating without adding checks: the image shows a strong chalk-like treatment, but the giraffes retain detailed photographic markings and the scene’s softened background does not by itself establish a drawing conversion. Keep the readout from treating weak cues as conclusive completion or treating a failed cue as proof of no progress.
  Operations: revise_support, revise_support, revise_readout
  Result: {"round": 5, "batch": 0, "index": 0, "program_ref": "e63119605349e854dbed3bb1b62643e141a835fe68aae29022b202e340192549", "structural_valid": true, "audit": {"accepted": true, "reason": "The program preserves the request to convert the image into a chalk drawing. Its independent support checks assess chalk-like treatment and drawing form without treating either alone as sufficient; the requested readout requires both supports to establish a complete conversion across the image, allows partial only with affirmative evidence of progress, and keeps unsupported or ambiguous cases unresolved. The checks add no unrelated constraints or mandatory techniques, and the composition rules are consistent.", "execution_ref": "a3c6c0921226ff4b37278730ff7377353a40f7c76968ab0298a6abb497c4adbb"}}
  Constructed hashes: {"parent_ref": "5a2c20cd33d74218dffc09bf1abdf7c6c49e72bd3993510f50b2ce275ee89abd", "child_ref": "e63119605349e854dbed3bb1b62643e141a835fe68aae29022b202e340192549"}
- The existing checks do not consistently establish whether the drawing conversion covers the whole scene; the visual-discovery hypothesis identifies background and ground as unresolved. Add a nested extent check under the drawing-form support, then require its affirmative evidence for completion while retaining partial progress from chalk-like treatment. This stays within the four-check cap and does not treat the reference label as atomic truth.
  Operations: insert_support, revise_readout
  Result: {"round": 6, "batch": 0, "index": 0, "error": "Criterion-only arm forbids structural changes", "accepted": false}
  Constructed hashes: {"parent_ref": null, "child_ref": null}
- The profile permits only criterion revisions. Existing traces show chalk-like treatment consistently, but drawing-form judgments vary; the readout should not treat a broad drawing cue as proof of complete conversion or treat a failed cue as proof of no progress. Clarify the existing drawing check and make the readout distinguish evidenced progress from unresolved extent without adding a check.
  Operations: revise_support
  Result: {"round": 7, "batch": 0, "index": 0, "program_ref": "a90cd1a22ab37d2baddb02430c488b804d232182f1d9a08eb2cf35d562103090", "structural_valid": true, "audit": {"accepted": false, "reason": "The requested readout cannot establish complete fulfillment: n1 and n2 assess chalk-like treatment and drawing-specific rendering, but neither checks whether the conversion covers the whole image. The readout explicitly requires evidence that establishes conversion across the image, so even both supports passing can only yield partial, not complete. This leaves the requested yes outcome unreachable despite the instruction requiring the image to be turned into a chalk drawing.", "execution_ref": "1e6f58374b229c4457614c814364b722487a26f3dedd2873b4461491ede6b32d"}}
  Constructed hashes: {"parent_ref": "e63119605349e854dbed3bb1b62643e141a835fe68aae29022b202e340192549", "child_ref": "a90cd1a22ab37d2baddb02430c488b804d232182f1d9a08eb2cf35d562103090"}
- The repeated traces show n1 consistently detects chalk-like treatment, while n2 varies between drawing conversion and retained photographic detail; the image also has a strongly smeared background. Clarify the existing drawing-form check and readout so texture alone cannot establish completion, while preserving evidenced progress and unresolved cases. This criterion-only repair does not treat the reference label as atomic truth.
  Operations: revise_support, revise_readout
  Result: {"round": 8, "batch": 0, "index": 0, "program_ref": "88b020c6342561e13157897da5638a98b5d3ec9e0116933a1c28c11a36b5b56f", "structural_valid": true, "audit": {"accepted": false, "reason": "The readout\u2019s complete rule requires evidence that drawing-form conversion covers the image, but n2 only asks whether drawn forms replace photographic detail across substantial content. Its pass criteria do not establish that other areas are not still photographic or merely smeared. The readout cannot infer that finer whole-image condition from n2\u2019s coarse pass, so the program lacks sufficient support for complete fulfillment.", "execution_ref": "d524503d62d04027aba79928a89d28e3a9e0cc04a979fe06b9321b1319486d29"}}
  Constructed hashes: {"parent_ref": "e63119605349e854dbed3bb1b62643e141a835fe68aae29022b202e340192549", "child_ref": "88b020c6342561e13157897da5638a98b5d3ec9e0116933a1c28c11a36b5b56f"}
- The repeated traces show that chalk-like treatment is consistently observed, while drawing conversion is disputed; the image also retains detailed giraffe forms amid strong smearing. Clarify the existing drawing check and readout so a chalk-like treatment alone supports progress but cannot establish a complete drawing conversion. This criterion-only repair preserves the three-check structure and does not treat disagreement as an atomic label.
  Operations: revise_support, revise_readout
  Result: {"round": 9, "batch": 0, "index": 0, "program_ref": "44503d9e1ae5cecdd7d131062be0060295d0da0a973175dbe77898d40658f692", "structural_valid": true, "audit": {"accepted": false, "reason": "The program adds an unsupported scene-specific requirement: n2 requires examining giraffes, although the instruction only says to turn the image into a chalk drawing and does not establish that giraffes are present. This can make the requested readout depend on evidence about an unrequested subject. Also, n3 permits complete only when the supports establish conversion \u201cacross the image,\u201d but n2\u2019s pass criterion requires drawn rendering across substantial content, not the whole image; the support evidence therefore cannot establish the extent demanded for completion. The readout must not infer that finer coverage from a coarse support pass.", "execution_ref": "a059f7e74d019a6954ae1c1e0c358c340d5ea70f087d351dcaf164d379c34b56"}}
  Constructed hashes: {"parent_ref": "e63119605349e854dbed3bb1b62643e141a835fe68aae29022b202e340192549", "child_ref": "44503d9e1ae5cecdd7d131062be0060295d0da0a973175dbe77898d40658f692"}
- The repeated traces show that n1 can pass for chalk-like treatment while n2 varies between pass and fail on whether photographic detail remains; the readout then inconsistently treats both passes as complete. Preserve the independent checks and make completion depend on explicit saved evidence of whole-image conversion, while retaining partial for evidenced progress without that proof. This is criterion-only and does not force a label.
  Operations: revise_support, revise_readout
  Result: {"round": 10, "batch": 0, "index": 0, "program_ref": "1ab7cf8d30a14630207cb4009a70eced0c90ac4454d3c90f2abaf5cbbb7bcfc0", "structural_valid": true, "audit": {"accepted": true, "reason": "The program preserves the original request and rubric. Its independent support checks examine both chalk-like treatment and drawing conversion across the image, while the requested readout combines only those observations and does not treat a coarse pass as proof of the finer condition. It distinguishes complete fulfillment, affirmative partial progress, evidenced absence, and insufficient evidence without adding unrelated requirements or mandatory techniques.", "execution_ref": "6e6775d6cecf082ccc509904749dd9fd95a5b51b3f4b28c30202947a13ef8a9f"}}
  Constructed hashes: {"parent_ref": "e63119605349e854dbed3bb1b62643e141a835fe68aae29022b202e340192549", "child_ref": "1ab7cf8d30a14630207cb4009a70eced0c90ac4454d3c90f2abaf5cbbb7bcfc0"}
- The existing readout already defines the required aggregation, but n1’s repeated unknowns show its chalk-medium threshold is not reliably distinguishing the visible powdery, smudged treatment from generic filtering. Under the criterion-only profile, revise that check to assess affirmative chalk-like surface behavior without requiring certainty about conversion; preserve unknown for genuinely ambiguous evidence and keep the readout composition unchanged.
  Operations: revise_support
  Result: {"round": 11, "batch": 0, "index": 0, "program_ref": "9866eb69971df1032c16ed960dbc4ec064b2dfe540b29aeaa479843bd6ecae58", "structural_valid": true, "audit": {"accepted": true, "reason": "The program preserves the request to make the image a chalk drawing. Its independent support checks examine chalk-like treatment and drawing conversion across the image, and the nested check does not treat a coarse pass as proof of conversion. The requested readout combines both supports, requires whole-image conversion for completion, and distinguishes partial progress, no progress, and insufficient evidence without adding unrelated constraints or mandatory techniques.", "execution_ref": "41ee17c12c45d831e3fd12db04805eef478828b542fa12f5ea14edf5b46bc702"}}
  Constructed hashes: {"parent_ref": "1ab7cf8d30a14630207cb4009a70eced0c90ac4454d3c90f2abaf5cbbb7bcfc0", "child_ref": "9866eb69971df1032c16ed960dbc4ec064b2dfe540b29aeaa479843bd6ecae58"}
## nested-required

Acceptance: {"qualified": true, "reasons": [], "policy": {"repeats": 5, "agreement": 0.8, "consistency": 0.8, "confidence": 0.8, "minimum_eligible": 3}}
Search schedule: {"round_batches": [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1], "rounds_started": 4, "rounds_completed": 4, "stop_on_confirmation": true, "repair_failed_candidate": true}
Failed-confirmation follow-up rounds: []
Selected audit: {"accepted": true, "reason": "The program preserves the request to turn the image into a chalk drawing. Its support checks separately assess chalk-like treatment, drawing form, and whether the conversion extends across the major content and background; the nested extent check does not treat a coarse pass as sufficient. The requested readout combines those observations without images, gives partial credit for evidenced progress with incomplete conversion, and leaves insufficient evidence unresolved. It adds no unrelated constraints or mandatory techniques, and the composition rules are consistent.", "execution_ref": "78efaf0262a710b81c994abb41fca80a4e9b25f1f0c9c8a351a8d2a07c5f57fa"}
Complete confirmation: {"draws": 5, "agreement": 1.0, "coverage": 1.0, "confidence_pass": true}

| Check | Role / evidence context | Question | Final states | Consistency |
|---|---|---|---|---:|
| n1 | support / [] | Does the edited image visibly have a chalk-like drawing medium or surface treatment? | {"pass": 5} | 1.0 |
| n2 | support / [] | Does the edited image visibly present its depicted content as a drawing rather than as an unchanged photograph? | {"pass": 5} | 1.0 |
| n4 | support / ['n1'] | Does the chalk-like treatment visibly render the scene's major content and background as a drawing, rather than mainly adding chalky texture or outlines to photographic content? | {"fail": 5} | 1.0 |
| n3 | requested / ['n1', 'n2', 'n4'] | Has the image been transformed into a drawing made from chalk? | {"partial": 5} | 1.0 |

### Typed edit history

- The nested visual hypothesis targets a distinct gap: existing checks separately accept chalk-like texture and sketch-like appearance, but do not establish that the chalk treatment renders the scene as a drawing rather than overlaying photographic detail. Add this focused check under the chalk-medium support and make the readout require it for completion while allowing evidenced progress to remain partial.
  Operations: insert_support
  Result: {"round": 0, "batch": 0, "index": 0, "program_ref": "c92d06e7c426797791164531e3bfb6115743d28b2b195a9b31ceecfd13b7a4d8", "structural_valid": true, "audit": {"accepted": false, "reason": "The support checks overlap and can contradict one another: n4 and n2 both assess whether the scene is rendered as a drawing, with different scopes and criteria, yet the readout treats both as independent required aspects. In particular, n2 can fail because content remains photographic even when n4 passes its scene-wide drawing criterion, making the composition ambiguous rather than a faithful combination of distinct evidence. The readout also says complete requires all three supports to pass, but its partial rule allows any support pass without clearly resolving contradictory observations. Revise the checks or composition so each required aspect is distinct and conflicts have an explicit, non-overlapping rule.", "execution_ref": "d7f8bf3b90e78fed4a9e4e1fb5bddb633027f74b817e2266102f05e79ef8c907"}}
  Constructed hashes: {"parent_ref": "5a2c20cd33d74218dffc09bf1abdf7c6c49e72bd3993510f50b2ce275ee89abd", "child_ref": "c92d06e7c426797791164531e3bfb6115743d28b2b195a9b31ceecfd13b7a4d8"}
- The image has a strong chalky, grainy treatment, but the giraffes retain detailed photographic structure; the existing checks can mistake texture and softened outlines for a whole-image chalk drawing. Add a nested, scene-wide rendering check to distinguish actual drawn conversion from a filtered photograph, while keeping the existing chalk-medium evidence separate. The readout must treat this new evidence as necessary for completion and avoid treating support failures alone as proof of no progress.
  Operations: insert_support
  Result: {"round": 2, "batch": 0, "index": 0, "program_ref": "58ac60fbc464f7448cf6b2408cb9e4adf38f01d43b44e80b083c99c8f17acd61", "structural_valid": true, "audit": {"accepted": false, "reason": "The requested readout is activated only under n4, so it cannot run when n4 is unknown or otherwise unavailable; that leaves fulfillment unresolved even if n1 and n2 provide evidence of progress. This is an unjustified activation gate: n4 is evidence for completeness, not a condition for assessing the requested outcome. The readout should be reachable regardless of n4\u2019s status and compose all available support observations.", "execution_ref": "8969100aaf237abba585f0c7e21604a1c4a96121dccc6c9516dfac5405ca1cd0"}}
  Constructed hashes: {"parent_ref": "5a2c20cd33d74218dffc09bf1abdf7c6c49e72bd3993510f50b2ce275ee89abd", "child_ref": "58ac60fbc464f7448cf6b2408cb9e4adf38f01d43b44e80b083c99c8f17acd61"}
- Add a distinct nested extent check: the existing supports detect chalk-like treatment and drawing cues, but do not establish whether the scene is broadly converted rather than textured or outlined. Keep the readout explicit that this extent evidence governs completeness, while the existing checks establish progress; a failed extent check is not by itself proof of no progress.
  Operations: insert_support
  Result: {"round": 3, "batch": 0, "index": 0, "program_ref": "83b0037c892830c71b4799e54b62363ec2b229793876f3522cebed4cd331b61e", "structural_valid": true, "audit": {"accepted": true, "reason": "The program preserves the request to turn the image into a chalk drawing. Its support checks separately assess chalk-like treatment, drawing form, and whether the conversion extends across the major content and background; the nested extent check does not treat a coarse pass as sufficient. The requested readout combines those observations without images, gives partial credit for evidenced progress with incomplete conversion, and leaves insufficient evidence unresolved. It adds no unrelated constraints or mandatory techniques, and the composition rules are consistent.", "execution_ref": "78efaf0262a710b81c994abb41fca80a4e9b25f1f0c9c8a351a8d2a07c5f57fa"}}
  Constructed hashes: {"parent_ref": "5a2c20cd33d74218dffc09bf1abdf7c6c49e72bd3993510f50b2ce275ee89abd", "child_ref": "83b0037c892830c71b4799e54b62363ec2b229793876f3522cebed4cd331b61e"}

## Preparation

{
  "probe_error": {
    "error": "Need two or three support specifications; never truncate",
    "failure": "ValueError"
  },
  "seed_audit": {
    "accepted": false,
    "reason": "The requested readout is not semantically sound. It treats one support failure as evidence that the corresponding requested feature is absent, and both failures as proof of no progress. But n1 and n2 only assess visible evidence under their criteria; a failure may not establish that the image has not been transformed in the requested way. The readout therefore overstates negative evidence and can return absent or partial without sufficient support. It also requires both supports to pass for completion, although their criteria do not establish that the whole image was converted into a chalk drawing. The program needs evidence that supports the requested extent, not merely chalk-like treatment and drawing form in isolation.",
    "execution_ref": "5c0636801a2976f30653db47ccfddadfc1b8f95922d0cddb3e7d601314e140a6"
  }
}

## Usage

{
  "calls": 224,
  "charged_completion_tokens": 35826,
  "reported_completion_tokens": 26610,
  "input_tokens": 490425,
  "outcomes": {
    "completed": 218,
    "transport_error": 6
  },
  "stages": {
    "visual_discovery": 16,
    "check": 132,
    "audit": 14,
    "gradient": 45,
    "propose_typed": 16,
    "compile_typed": 1
  },
  "returned_models": [
    "gpt-6-luna"
  ]
}

Semantic audit is evidence, not proof. Supporting observations do not earn completion credit. Final outcomes never trigger further optimization. Unvisited/unresolved checks and failure slots remain explicit.
