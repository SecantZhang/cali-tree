# One-case nested evidence repair: saved results

Instruction: Turn the image into a drawing made from chalk
Reference: `partial`.
One previously observed local fitting case; five fresh final draws per seed and selected program. All compilation, checking, auditing and visual discovery are label-blind; backward/proposal requests may use the label. Discovery uses GPT-6 Luna only, so this test does not measure diversity benefits from other model families.

Status: completed

| Method | Seed → selected reference matches / 5 | Selected usable / 5 | Minimum reported confidence | Selected checks | Program changed? | Final status |
|---|---:|---:|---:|---:|---|---|
| broad-greedy | 0 → 5 | 5 | 0.94 | 1 | True | locally_robust |
| decomposed-greedy | 0 → 0 | 0 | unavailable | unavailable | unavailable | unresolved |

Reference matches measure agreement with the saved partial label. Usable answers include incorrect answers. Confidence is model self-report; check consistency is modal repeat agreement. Matching the label does not certify atomic correctness.

## broad-greedy

Final acceptance: {"qualified": true, "reasons": [], "policy": {"repeats": 5, "agreement": 0.8, "consistency": 0.8, "confidence": 0.8, "minimum_eligible": 3}}
Selected audit: {"accepted": true, "reason": "The single applicable outcome preserves the requested chalk-drawing transformation, binds it to the image and chalk-drawing reference, and provides complete, partial, absent, and unknown criteria consistent with the rubric. No outcomes are skipped, dependencies or routing inferences are absent, and the check does not encode an expected answer or add unrelated requirements.", "execution_ref": "84244d6038ac1341f845ca1def6d932049e5231e8ab9f39ae005a77fd0d0efc1"}
Added supports: []
Nested support dependencies: []
Diagnostic-only parent candidates: []

| Component | Role / evidence inputs | Question | Final states | Repeat consistency |
|---|---|---|---|---:|
| n1 | requested / images | Has the image been transformed into a drawing made from chalk? | {"partial": 5} | 1.0 |

### Repair history

- Round 1, batch 1: The existing check equates grain and smudging with a completed chalk drawing. Refine its completion boundary to require a coherent, image-wide chalk-drawing appearance; retain partial for a visible but incomplete stylization and unknown only for insufficient evidence.
  Result: {"round": 0, "batch": 0, "index": 0, "program_ref": "f053062c6b338bb0b6e76cf12d94c64176ec75c4ecb410b02c5e0c37ee6c1d1d", "structural_valid": true, "audit": {"accepted": true, "reason": "The single applicable outcome preserves the requested chalk-drawing transformation, binds it to the image and chalk-drawing reference, and provides complete, partial, absent, and unknown criteria consistent with the rubric. No outcomes are skipped, dependencies or routing inferences are absent, and the check does not encode an expected answer or add unrelated requirements.", "execution_ref": "84244d6038ac1341f845ca1def6d932049e5231e8ab9f39ae005a77fd0d0efc1"}}
- Round 2, batch 2: Make the comparison target explicit while preserving the existing whole-image completion and partial-progress distinctions; the observed edit shows partial chalk-like treatment, not full conversion.
  Result: {"round": 1, "batch": 1, "index": 0, "program_ref": "248f43543e546c4b33a6c1e8082e54dd173fb5e8462c3cf6daae6b45f52966a5", "structural_valid": true, "audit": {"accepted": true, "reason": "The single requested outcome preserves the instruction, target, and chalk-drawing reference. Its criteria distinguish complete, partial, absent, and unknown without adding unrelated requirements; applicability and evidence binding are justified, and there are no dependencies, gates, or inferences to distort coverage.", "execution_ref": "6104d581d2e3ff309fc4dbef356c15ea0676af2c6c629ca0edc7ccb2d7652544"}}

### Visual discovery hypotheses

## decomposed-greedy

Final acceptance: {}
Selected audit: {}
Added supports: []
Nested support dependencies: []
Diagnostic-only parent candidates: []

| Component | Role / evidence inputs | Question | Final states | Repeat consistency |
|---|---|---|---|---:|

### Repair history

No repair transactions recorded.

### Visual discovery hypotheses


## Usage

{
  "calls": 38,
  "completion_tokens_charged": 3210,
  "completion_tokens_reported": 3210,
  "input_tokens": 57101,
  "outcomes": {
    "completed": 38
  },
  "stages": {
    "check": 28,
    "audit": 2,
    "compile_refinement": 1,
    "gradient": 3,
    "propose": 3,
    "audit_pair": 1
  },
  "returned_models": [
    "gpt-6-luna"
  ]
}

Search/confirmation is globally bounded to 100 calls; 50 calls and 51,200 tokens remain reserved for final comparison. Budget-limited search is an explicit outcome. Final draws never trigger more optimization. A single failure-selected case cannot establish generalization.
