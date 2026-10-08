# Nested evidence repair versus broad checking

Previously observed local cases: broad versus nested evidence repair with diagnostic-only execution of audit-rejected seeds. Fresh final draws cannot guide repair.

Status: completed

| Method | Seed → selected reference agreement | Selected usable answers | Robust cases | Mean selected checks |
|---|---:|---:|---:|---:|
| broad-greedy | 0.0% → 100.0% | 100.0% | 1/1 | 1.00 |
| decomposed-greedy | 0.0% → 0.0% | 0.0% | 0/1 | 0.00 |

Agreement = matching the reference; coverage = usable final answers, including incorrect ones. Consistency = most common usable answer frequency. Confidence = model self-report. Each case uses five fresh final draws per program. A robust case passes every original acceptance gate. Failed/missing draws remain nonmatches.

| Case | Method | Seed matches / 5 | Selected matches / 5 | Selected usable / 5 | Lowest available confidence | Check consistency | Status / reasons |
|---|---|---:|---:|---:|---:|---|---|
| Turn the image into a drawing made from chalk | broad-greedy | 0 | 5 | 5 | 0.94 | {"n1": 1.0} | locally_robust; none |
| Turn the image into a drawing made from chalk | decomposed-greedy | 0 | 0 | 0 | missing | {} | unresolved; ValueError: Only ancestor evidence references and depth <= four are supported |

## Broad versus decomposed scoring fidelity

{
  "seed": {
    "agreement": 0.0,
    "both_resolved": 0.0,
    "per_case": [
      {
        "case_id": "aurora-task-ce641cb29939011016cc::mgie",
        "same_index_matches": 0,
        "both_resolved": 0,
        "draw_pairs": 5
      }
    ],
    "interpretation": "Descriptive same-index comparison of stochastic executions, not an independent sample of cases."
  },
  "selected": {
    "agreement": 0.0,
    "both_resolved": 0.0,
    "per_case": [
      {
        "case_id": "aurora-task-ce641cb29939011016cc::mgie",
        "same_index_matches": 0,
        "both_resolved": 0,
        "draw_pairs": 5
      }
    ],
    "interpretation": "Descriptive same-index comparison of stochastic executions, not an independent sample of cases."
  }
}

Supports may inspect images with ancestor evidence in the nested repair contract. The decomposed readout receives no images and must acknowledge every saved dependency. Known negative support evidence remains usable. Unknown necessary evidence blocks the readout. Nested supports may refine ancestor findings; skipped necessary evidence stays unresolved. Structural guards and semantic audits do not prove atomic reasoning or semantic equivalence.

Budget: {"max_calls": 150, "max_completion_tokens": 192000, "reserve_calls": 50, "reserve_tokens": 51200, "identity": {"model": "gpt-6-luna", "provider": "openai", "temperature": 0, "reasoning_effort": "none"}, "scope_limits": {"search": 109, "final": 40}}
Usage: {"calls": 38, "completion_tokens_or_reserved": 3210, "input_tokens": 57101, "consecutive_errors": 0, "stopped": null, "final_calls": 10, "final_tokens": 533}
Returned models: ["gpt-6-luna"]
