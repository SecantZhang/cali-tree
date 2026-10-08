# Nested evidence repair versus broad checking

Previously observed local cases: broad versus nested evidence repair with diagnostic-only execution of audit-rejected seeds. Fresh final draws cannot guide repair.

Status: completed

| Method | Seed → selected reference agreement | Selected usable answers | Robust cases | Mean selected checks |
|---|---:|---:|---:|---:|
| broad-greedy | 0.0% → 80.0% | 100.0% | 1/1 | 1.00 |
| decomposed-greedy | 0.0% → 40.0% | 100.0% | 0/1 | 3.00 |

Agreement = matching the reference; coverage = usable final answers, including incorrect ones. Consistency = most common usable answer frequency. Confidence = model self-report. Each case uses five fresh final draws per program. A robust case passes every original acceptance gate. Failed/missing draws remain nonmatches.

| Case | Method | Seed matches / 5 | Selected matches / 5 | Selected usable / 5 | Lowest available confidence | Check consistency | Status / reasons |
|---|---|---:|---:|---:|---:|---|---|
| Turn the image into a drawing made from chalk | broad-greedy | 0 | 4 | 5 | 0.94 | {"n1": 0.8} | locally_robust; none |
| Turn the image into a drawing made from chalk | decomposed-greedy | 0 | 2 | 5 | 0.91 | {"n1": 1.0, "n2": 0.6, "n3": 0.6} | unstable_and_mismatched; target_mismatch, requirement_instability, node_instability:n2, node_instability:n3 |

## Broad versus decomposed scoring fidelity

{
  "seed": {
    "agreement": 0.8,
    "both_resolved": 0.8,
    "per_case": [
      {
        "case_id": "aurora-task-ce641cb29939011016cc::mgie",
        "same_index_matches": 4,
        "both_resolved": 4,
        "draw_pairs": 5
      }
    ],
    "interpretation": "Descriptive same-index comparison of stochastic executions, not an independent sample of cases."
  },
  "selected": {
    "agreement": 0.2,
    "both_resolved": 1.0,
    "per_case": [
      {
        "case_id": "aurora-task-ce641cb29939011016cc::mgie",
        "same_index_matches": 1,
        "both_resolved": 5,
        "draw_pairs": 5
      }
    ],
    "interpretation": "Descriptive same-index comparison of stochastic executions, not an independent sample of cases."
  }
}

Supports may inspect images with ancestor evidence in the nested repair contract. The decomposed readout receives no images and must acknowledge every saved dependency. Known negative support evidence remains usable. Unknown necessary evidence blocks the readout. Nested supports may refine ancestor findings; skipped necessary evidence stays unresolved. Structural guards and semantic audits do not prove atomic reasoning or semantic equivalence.

Budget: {"max_calls": 112, "max_completion_tokens": 188790, "reserve_calls": 50, "reserve_tokens": 51200, "identity": {"model": "gpt-6-luna", "provider": "openai", "temperature": 0, "reasoning_effort": "none"}, "scope_limits": {"search": 109, "final": 40}}
Usage: {"calls": 101, "completion_tokens_or_reserved": 10917, "input_tokens": 159350, "consecutive_errors": 0, "stopped": null, "final_calls": 39, "final_tokens": 3295}
Returned models: ["gpt-6-luna"]
