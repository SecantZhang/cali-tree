# Typed evidence chalk pilot: saved-data analysis

One previously observed chalk case fitted locally. Repeats are within-case measurements. No atomic correctness or generalization claim.

Checkpoint: a3b80472e88be94bb4f3be4597c16cb3b67b2be1
Reference: `partial`. Status: completed

| Arm | Seed → selected matches / 5 | Selected usable / 5 | Minimum reported confidence | Checks | Inserted nested checks | Status |
|---|---:|---:|---:|---:|---|---|
| criterion-only | 0 → 2 | 2 | 0.88 | 3 | none | unconfirmed |
| nested-required | 0 → 0 | 5 | 0.91 | 4 | n4 | unconfirmed |

Matches mean reference-label agreement; usable answers include wrong labels. Confidence is generated self-report. Five repeats are measurements within one previously observed case, not independent cases. Actual added-check execution and accuracy are separate outcomes.

## criterion-only

Acceptance: {"qualified": false, "reasons": ["unresolved", "target_mismatch", "requirement_instability", "node_instability:n1", "insufficient_activation:n3", "confirmation_missing_or_unqualified"], "policy": {"repeats": 5, "agreement": 0.8, "consistency": 0.8, "confidence": 0.8, "minimum_eligible": 3}}
Selected audit: {"accepted": true, "reason": "The program preserves the request to convert the image into a chalk drawing. Its independent support checks require visible evidence of both chalk-like medium and drawing conversion across the depicted content; the requested readout combines only those observations and distinguishes completion, evidenced partial progress, absence, and uncertainty. The nested activation and dependencies do not let a broad pass substitute for the finer check, and no unrelated constraints or unsupported inferences are added.", "execution_ref": "4095e354756201e07a757a8efb42eaee4961373b0977822e878aa11ef0423eee"}
Complete confirmation: {"draws": 5, "agreement": 0.2, "coverage": 0.2, "confidence_pass": false}

| Check | Role / evidence context | Question | Final states | Consistency |
|---|---|---|---|---:|
| n1 | support / [] | Does the edited image visibly use a chalk-like drawing medium, rather than merely having grain, blur, or smudging? | {"unknown": 3, "pass": 2} | 0.4 |
| n2 | support / [] | Does the edited image visibly present its depicted content as a drawing rather than as a photograph with effects? | {"fail": 5} | 1.0 |
| n3 | requested / ['n1', 'n2'] | Has the image been transformed into a drawing made from chalk? | {"partial": 2} | 1.0 |

### Typed edit history

- The existing checks conflate suggestive surface texture with chalk medium and allow outlines/texture to establish drawing conversion despite photographic-looking subject detail. Tighten both criteria to require affirmative evidence, preserving unknown for ambiguity; keep the readout unresolved when the supports do not establish progress or its absence. Criterion-only profile permits these revisions.
  Operations: revise_support, revise_support, revise_readout
  Result: {"round": 0, "batch": 0, "index": 0, "program_ref": "a65a2ac59a1bc4f5333cc4960548530e425956474d0c00505004b72d08b28b4d", "structural_valid": true, "audit": {"accepted": true, "reason": "The program preserves the request to convert the image into a chalk drawing. Its independent support checks require visible evidence of both chalk-like medium and drawing conversion across the depicted content; the requested readout combines only those observations and distinguishes completion, evidenced partial progress, absence, and uncertainty. The nested activation and dependencies do not let a broad pass substitute for the finer check, and no unrelated constraints or unsupported inferences are added.", "execution_ref": "4095e354756201e07a757a8efb42eaee4961373b0977822e878aa11ef0423eee"}}
  Constructed hashes: {"parent_ref": "5a2c20cd33d74218dffc09bf1abdf7c6c49e72bd3993510f50b2ce275ee89abd", "child_ref": "a65a2ac59a1bc4f5333cc4960548530e425956474d0c00505004b72d08b28b4d"}
- The saved readout already handles unresolved evidence faithfully, and the visual-discovery hypothesis is useful as a narrower investigation of the drawing-conversion check. Clarify that check’s criterion and binding so a failure requires affirmative photo-like rendering, while preserving unknown for inconclusive evidence. This is criterion-only; no new check is warranted.
  Operations: revise_support
  Result: {"round": 1, "batch": 0, "index": 0, "program_ref": "bbef323656d5b02122ad6f6767579f9b32d66ec1ea10275cd538302294118815", "structural_valid": true, "audit": {"accepted": false, "reason": "The program adds an unsupported scene-specific constraint: n2 refers to giraffes, although the instruction and rubric specify no such subject. This can make the drawing-conversion check judge content not established by the request. The remaining checks separate chalk medium from drawing conversion and compose their evidence, but this unrelated constraint prevents faithful preservation.", "execution_ref": "f46d96a22331708405425f7a4a147e997e087d8053e59c558e30660788f8613c"}}
  Constructed hashes: {"parent_ref": "a65a2ac59a1bc4f5333cc4960548530e425956474d0c00505004b72d08b28b4d", "child_ref": "bbef323656d5b02122ad6f6767579f9b32d66ec1ea10275cd538302294118815"}
## nested-required

Acceptance: {"qualified": false, "reasons": ["target_mismatch", "confirmation_missing_or_unqualified"], "policy": {"repeats": 5, "agreement": 0.8, "consistency": 0.8, "confidence": 0.8, "minimum_eligible": 3}, "reference_conflict_suspected": true}
Selected audit: {"accepted": true, "reason": "The program preserves the request to make the image a chalk drawing. Its independent supports check chalk treatment, drawing conversion, and whether that conversion covers the whole image; the nested checks do not treat a coarse pass as proof of finer extent. The requested readout uses only those observations and distinguishes complete, partial, absent, and unresolved evidence without adding unrelated constraints or mandatory techniques. No contradictory composition rules or unsupported inferences are apparent.", "execution_ref": "78c08635bdbff47ea6cbb4a8b6a0ffb68c82edf18c0546f8c4a889a415425b49"}
Complete confirmation: {"draws": 5, "agreement": 0.0, "coverage": 1.0, "confidence_pass": true}

| Check | Role / evidence context | Question | Final states | Consistency |
|---|---|---|---|---:|
| n1 | support / [] | Does the edited image visibly have a chalk-like drawing medium or surface treatment? | {"pass": 5} | 1.0 |
| n2 | support / [] | Does the edited image visibly present its depicted content as a drawing rather than as an unchanged photograph? | {"pass": 5} | 1.0 |
| n4 | support / ['n2'] | Does drawing-like rendering extend across the whole image, including the giraffes and background, rather than leaving substantial areas photographic or applying only a localized chalk-like treatment? | {"pass": 5} | 1.0 |
| n3 | requested / ['n1', 'n2', 'n4'] | Has the image been transformed into a drawing made from chalk? | {"complete": 5} | 1.0 |

### Typed edit history

- The visual-discovery hypothesis identifies a useful nested extent check: the edit has chalk-like texture and sketch rendering, but the background and peripheral details may not be consistently converted. Add this as evidence under the drawing-form check, without treating the hypothesis or reference label as a predetermined result.
  Operations: insert_support, revise_readout
  Result: {"round": 0, "batch": 0, "index": 0, "error": "Insertion needs explicit readout criteria", "accepted": false}
  Constructed hashes: {"parent_ref": null, "child_ref": null}
- A nested whole-image conversion check is justified: the edit has visible chalk-like grain and softened, drawn surroundings, while the giraffes retain substantial photographic detail. This check investigates extent without assuming the visual hypothesis or reference label is decisive. The readout must treat the new evidence as qualifying completion, not as automatic proof of progress or absence.
  Operations: insert_support, revise_readout
  Result: {"round": 1, "batch": 0, "index": 0, "program_ref": "52af82ed063efecd567320c6ded9305d1b46022be8c9870f8b8d43de83faf619", "structural_valid": true, "audit": {"accepted": false, "reason": "The requested readout does not define a sound partial/absent composition for the independent chalk-medium and drawing-form requirements. It allows partial when there is evidence of some requested change and the whole-image chalk drawing is incomplete, but the supports do not establish that incompleteness: n1 or n2 failing only negates its own proposition, and n4 only assesses drawing extent. For example, n1 pass, n2 fail, n4 pass establishes chalk treatment and no drawing conversion, but does not establish whether the requested chalk drawing has progressed partially or is absent. The criteria correctly forbid treating a support failure alone as evidence of absence, leaving this case unresolved rather than composing all available evidence into the rubric\u2019s required outcome.", "execution_ref": "de8dec01fc0354ee159d0c60353a032f646b682f1f33b09f4dd4877f6f95e1d6"}}
  Constructed hashes: {"parent_ref": "5a2c20cd33d74218dffc09bf1abdf7c6c49e72bd3993510f50b2ce275ee89abd", "child_ref": "52af82ed063efecd567320c6ded9305d1b46022be8c9870f8b8d43de83faf619"}
- The nested visual hypothesis is worth testing: the giraffes have sketch-like outlines, while the background is heavily blurred and streaked, so the existing broad drawing check may not establish conversion across the whole image. This is an investigation, not a presumed failure or label-driven conclusion.
  Operations: insert_support
  Result: {"round": 1, "batch": 1, "index": 0, "program_ref": "fce888f56e52ba8398cb1c80c2aa7ca5e3a647b160a9e670be2ccef22edc83dd", "structural_valid": true, "audit": {"accepted": true, "reason": "The program preserves the request to make the image a chalk drawing. Its independent supports check chalk treatment, drawing conversion, and whether that conversion covers the whole image; the nested checks do not treat a coarse pass as proof of finer extent. The requested readout uses only those observations and distinguishes complete, partial, absent, and unresolved evidence without adding unrelated constraints or mandatory techniques. No contradictory composition rules or unsupported inferences are apparent.", "execution_ref": "78c08635bdbff47ea6cbb4a8b6a0ffb68c82edf18c0546f8c4a889a415425b49"}}
  Constructed hashes: {"parent_ref": "5a2c20cd33d74218dffc09bf1abdf7c6c49e72bd3993510f50b2ce275ee89abd", "child_ref": "fce888f56e52ba8398cb1c80c2aa7ca5e3a647b160a9e670be2ccef22edc83dd"}

## Preparation

{
  "probe_error": {
    "error": "Need two or three support specifications; never truncate",
    "failure": "ValueError"
  },
  "seed_audit": {
    "accepted": false,
    "reason": "The requested readout is not faithful to the rubric\u2019s unresolved-evidence rule. It labels the case partial whenever one support passes and the other fails, but a failed support does not necessarily establish that the whole requested transformation is incomplete: n1 only checks for visible chalk treatment, and n2 only checks whether the content is a drawing. Their criteria allow failures based on absence of visible evidence, not necessarily evidence that the image was not transformed. The readout therefore overstates partial fulfillment. It also treats both supports failing as absent, although those failures may not establish that no requested change progressed.",
    "execution_ref": "5c0636801a2976f30653db47ccfddadfc1b8f95922d0cddb3e7d601314e140a6"
  }
}

## Usage

{
  "calls": 140,
  "charged_completion_tokens": 15697,
  "reported_completion_tokens": 13649,
  "input_tokens": 246155,
  "outcomes": {
    "completed": 138,
    "transport_error": 2
  },
  "stages": {
    "check": 104,
    "visual_discovery": 6,
    "gradient": 18,
    "compile_typed": 1,
    "audit": 5,
    "propose_typed": 6
  },
  "returned_models": [
    "gpt-6-luna"
  ]
}

Semantic audit is evidence, not proof. Supporting observations do not earn completion credit. Final outcomes never trigger further optimization. Unvisited/unresolved checks and failure slots remain explicit.
