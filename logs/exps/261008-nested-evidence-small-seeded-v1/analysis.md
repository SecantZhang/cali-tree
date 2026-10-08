# One-case nested evidence repair: saved-seed corrective results

Instruction: Turn the image into a drawing made from chalk
Reference: `partial`.
One previously observed local fitting case; five fresh final draws per seed and selected program. All compilation, checking, auditing and visual discovery are label-blind; backward/proposal requests may use the label. Discovery uses GPT-6 Luna only, so this test does not measure diversity benefits from other model families.
The first 38-call attempt had invalid compilation. It is preserved separately; this corrective test explicitly promotes the historical label-free decomposition seed, obtains a fresh audit, and deducts first-attempt usage from the same ceiling. No historical optimization feedback, old audit approval, or final traces enter this search.

Status: completed

| Method | Seed → selected reference matches / 5 | Selected usable / 5 | Minimum reported confidence | Selected checks | Program changed? | Final status |
|---|---:|---:|---:|---:|---|---|
| broad-greedy | 0 → 4 | 5 | 0.94 | 1 | True | locally_robust |
| decomposed-greedy | 0 → 2 | 5 | 0.91 | 3 | True | unstable_and_mismatched |

Reference matches measure agreement with the saved partial label. Usable answers include incorrect answers. Confidence is model self-report; check consistency is modal repeat agreement. Matching the label does not certify atomic correctness.

## broad-greedy

Final acceptance: {"qualified": true, "reasons": [], "policy": {"repeats": 5, "agreement": 0.8, "consistency": 0.8, "confidence": 0.8, "minimum_eligible": 3}}
Selected audit: {"accepted": true, "reason": "The program preserves the original instruction and rubric, binds the requested outcome to the image and chalk-drawing reference, and provides complete/partial/absent/unknown criteria without adding unrelated requirements. The single applicable tree check has no dependencies or routing inferences, and its criteria distinguish full fulfillment, progress, no progress, and insufficient evidence.", "execution_ref": "007086fd84461f8fbe4440da13031ea4a4bc2372b797e15876c1f97c7a60e341"}
Added supports: []
Nested support dependencies: []
Diagnostic-only parent candidates: []

| Component | Role / evidence inputs | Question | Final states | Repeat consistency |
|---|---|---|---|---:|
| n1 | requested / images | Has the image been transformed into a drawing made from chalk? | {"partial": 4, "complete": 1} | 0.8 |

### Repair history

- Round 1, batch 1: The current check treats chalk-like texture as sufficient for completion. The edited image has substantial chalky smudging and sketch-like outlines, but retains photographic detail and does not consistently read as a drawing; refine the completion threshold while preserving partial progress.
  Result: {"round": 0, "batch": 0, "index": 0, "program_ref": "ea82dec60390e1e7c661f4953d282b18182c255ded3bca0e14e0dad1c7ee7554", "structural_valid": true, "audit": {"accepted": true, "reason": "The program preserves the original instruction and rubric, binds the requested outcome to the image and chalk-drawing reference, and provides complete/partial/absent/unknown criteria without adding unrelated requirements. The single applicable tree check has no dependencies or routing inferences, and its criteria distinguish full fulfillment, progress, no progress, and insufficient evidence.", "execution_ref": "007086fd84461f8fbe4440da13031ea4a4bc2372b797e15876c1f97c7a60e341"}}
- Round 2, batch 1: Execution consistently identifies partial chalk-like rendering, and the existing criterion appropriately distinguishes that progress from a scene-wide chalk drawing. Only clarify the truncated binding as requested; do not alter the calibrated check.
  Result: {"round": 1, "batch": 0, "index": 0, "program_ref": "db631c8676b75bb8574136dfad6aa08d7818879c757689230e8d74ac9bec0148", "structural_valid": true, "audit": {"accepted": true, "reason": "The tree program preserves the sole requested outcome and its target/reference binding. Its criteria cover complete, partial, absent, and unknown states; unrelated edits are excluded, and insufficient evidence remains unresolved. The check is directly applicable, has no dependencies or routing inferences, and does not encode an expected answer or add an unsupported constraint.", "execution_ref": "2fbeb86b36d8f82f935c7e42852f47ec1a5fddda697ca786d22a9db02ec02288"}}

### Visual discovery hypotheses

## decomposed-greedy

Final acceptance: {"qualified": false, "reasons": ["target_mismatch", "requirement_instability", "node_instability:n2", "node_instability:n3"], "policy": {"repeats": 5, "agreement": 0.8, "consistency": 0.8, "confidence": 0.8, "minimum_eligible": 3}}
Selected audit: {"accepted": true, "reason": "The program preserves the request to turn the image into a chalk drawing. Its independent support checks assess both chalk-like medium and drawing form, and the image-free readout combines their evidence without treating a coarse pass as proof of the other feature. It distinguishes complete fulfillment, evidenced partial progress, no progress, and unresolved evidence; unrelated edits do not count. No unsupported inference or added mandatory technique is apparent.", "execution_ref": "c8b0d01b304e3234e7b6c6548877ef512ee9fcc4d50b7dbed555ad25b5b3eabf"}
Added supports: []
Nested support dependencies: []
Diagnostic-only parent candidates: ["5a2c20cd33d74218dffc09bf1abdf7c6c49e72bd3993510f50b2ce275ee89abd"]

| Component | Role / evidence inputs | Question | Final states | Repeat consistency |
|---|---|---|---|---:|
| n1 | support / images | Does the edited image visibly have a chalk-like drawing medium or surface treatment? | {"pass": 5} | 1.0 |
| n2 | support / images | Are the depicted forms visibly rendered as a drawing, rather than retaining photographic structure with only chalk-like texture, blur, or softened outlines? | {"fail": 2, "pass": 3} | 0.6 |
| n3 | requested / saved evidence only; dependencies n1, n2 | Has the image been transformed into a drawing made from chalk? | {"partial": 2, "complete": 3} | 0.6 |

### Repair history

- Round 1, batch 1: The image shows chalk-like grain and smudging, but the giraffes retain substantial photographic detail and the background is blurred and streaked rather than clearly rendered as a drawing. The existing drawing-form check is too broad to establish whole-image conversion. Add a nested extent check under that support and require it for completion; preserve partial when chalk treatment is evidenced but drawing conversion is not established. This is a label-blind structural proposal, not proof that any individual observation is wrong; fresh screens and confirmation are needed.
  Result: {"round": 0, "batch": 0, "index": 0, "error": "Only ancestor evidence references and depth <= four are supported", "accepted": false}
- Round 2, batch 1: The execution trace shows n1 and n2 both passing, but the visual evidence and textual gradients disagree about whether the scene is clearly rendered as a drawing: the image has conspicuous chalk-like grain and smudging, while the giraffes retain detailed photographic structure. The broad n2 proposition can therefore over-credit sketch-like outlines or painterly blur. Refine n2 to require clear drawing treatment in the depicted forms, distinct from surface texture, and allow uncertainty when that conversion is not established. Keep the readout’s existing combination rule: a passing chalk-treatment support can evidence partial progress when drawing conversion is not established. This is a label-blind criterion repair, not a claim that the reference label proves n2 wrong; fresh screening and confirmation are needed.
  Result: {"round": 1, "batch": 0, "index": 0, "program_ref": "a820155f32fc911305692004d7c6dc9f49d722e31213c22ac6b6826557c0c4b0", "structural_valid": true, "audit": {"accepted": true, "reason": "The program preserves the request to turn the image into a chalk drawing. Its independent support checks assess both chalk-like medium and drawing form, and the image-free readout combines their evidence without treating a coarse pass as proof of the other feature. It distinguishes complete fulfillment, evidenced partial progress, no progress, and unresolved evidence; unrelated edits do not count. No unsupported inference or added mandatory technique is apparent.", "execution_ref": "c8b0d01b304e3234e7b6c6548877ef512ee9fcc4d50b7dbed555ad25b5b3eabf"}}
- Round 2, batch 2: The existing supports establish chalk-like treatment and a drawn appearance, but their combination does not establish that the requested conversion extends across the image. Add a nested whole-image extent check under the drawing-form support and require it for completion. Preserve partial progress when any requested feature is evidenced but completion is not established, and preserve unknown when no progress is evidenced and evidence is insufficient. This is a label-blind refinement; the supplied image and diagnostics motivate investigation but do not prove an individual check’s status. Fresh screening and confirmation are required.
  Result: {"round": 1, "batch": 1, "index": 0, "error": "Only ancestor evidence references and depth <= four are supported", "accepted": false}

### Visual discovery hypotheses

- Does the drawing conversion visibly extend across the whole image, including the background and scene details, rather than mainly changing the giraffes and adding a chalk-like surface treatment? — The instruction applies to “the image.” The broad n2 pass and n1’s chalk-like texture do not by themselves establish that drawing conversion extends throughout the image; this finer check could clarify the extent without requiring a particular technique.
- Does the drawing-like rendering extend across the whole image, including the giraffes and background, rather than leaving substantial areas photographic or only applying a chalk-like overlay? — The saved checks separately support chalk-like treatment and drawing form, but do not investigate whether the drawing conversion is consistent across the image. This finer check could qualify the complete readout without assuming that the visible texture alone establishes whole-image conversion.

## Usage

{
  "calls": 101,
  "completion_tokens_charged": 10917,
  "completion_tokens_reported": 9893,
  "input_tokens": 159350,
  "outcomes": {
    "completed": 100,
    "transport_error": 1
  },
  "stages": {
    "check": 76,
    "gradient": 12,
    "propose": 6,
    "visual_discovery": 3,
    "audit": 3,
    "audit_pair": 1
  },
  "returned_models": [
    "gpt-6-luna"
  ],
  "cumulative_calls": 139,
  "cumulative_completion_tokens_charged": 14127
}

Search/confirmation has 62 remaining calls; 50 calls and 51,200 tokens remain reserved for final comparison. Budget-limited search is an explicit outcome. Final draws never trigger more optimization. A single failure-selected case cannot establish generalization.
