> **Incomplete follow-up:** stopped after three consecutive TLS failures. Do not use the aggregate columns to rank methods; unattempted work remains in the denominator. The completed comparison is documented in docs/experiments/calitree_forced_decomposition.md.

# Forced decomposition versus broad checking

Previously observed local fitting cases. Fresh observations compare saved label-free broad seeds with mandatory two/three-evidence-check decomposition and greedy repairs. Repeated draws are not additional cases. No generalization or atomic semantic correctness claim; evidence-only readout also changes the information flow.

Status: stopped

| Method | Seed → selected reference agreement | Selected usable answers | Robust cases | Mean selected checks |
|---|---:|---:|---:|---:|
| broad-greedy | 13.3% → 6.7% | 20.0% | 0/3 | 0.33 |
| decomposed-greedy | 0.0% → 0.0% | 0.0% | 0/3 | 0.00 |

Agreement = matching the reference; coverage = usable final answers, including incorrect ones. Consistency = most common usable answer frequency. Confidence = model self-report. Each case uses five fresh final draws per program. A robust case passes every original acceptance gate. Failed/missing draws remain nonmatches.

| Case | Method | Seed matches / 5 | Selected matches / 5 | Selected usable / 5 | Lowest available confidence | Check consistency | Status / reasons |
|---|---|---:|---:|---:|---:|---|---|
| Change the background into a basketball court | broad-greedy | 2 | 1 | 3 | 0.98 | {"n1": 0.4} | unresolved; unresolved, target_mismatch, requirement_instability, node_instability:n1, confidence |
| Change the background into a basketball court | decomposed-greedy | 0 | 0 | 0 | missing | {} | unresolved; none |
| Turn the image into a drawing made from chalk | broad-greedy | 0 | 0 | 0 | missing | {} | unattempted; none |
| Turn the image into a drawing made from chalk | decomposed-greedy | 0 | 0 | 0 | missing | {} | unattempted; none |
| Put a frog in the toilet | broad-greedy | 0 | 0 | 0 | missing | {} | unattempted; none |
| Put a frog in the toilet | decomposed-greedy | 0 | 0 | 0 | missing | {} | unattempted; none |

## Broad versus decomposed scoring fidelity

{
  "seed": {
    "agreement": 0.0,
    "both_resolved": 0.0,
    "per_case": [
      {
        "case_id": "aurora-task-65581617ad341fa398cb::magic_reproduce_epoch=47-step=12999",
        "same_index_matches": 0,
        "both_resolved": 0,
        "draw_pairs": 5
      },
      {
        "case_id": "aurora-task-ce641cb29939011016cc::mgie",
        "same_index_matches": 0,
        "both_resolved": 0,
        "draw_pairs": 5
      },
      {
        "case_id": "aurora-task-e0f9b97dc3bc00415cf2::mgie",
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
        "case_id": "aurora-task-65581617ad341fa398cb::magic_reproduce_epoch=47-step=12999",
        "same_index_matches": 0,
        "both_resolved": 0,
        "draw_pairs": 5
      },
      {
        "case_id": "aurora-task-ce641cb29939011016cc::mgie",
        "same_index_matches": 0,
        "both_resolved": 0,
        "draw_pairs": 5
      },
      {
        "case_id": "aurora-task-e0f9b97dc3bc00415cf2::mgie",
        "same_index_matches": 0,
        "both_resolved": 0,
        "draw_pairs": 5
      }
    ],
    "interpretation": "Descriptive same-index comparison of stochastic executions, not an independent sample of cases."
  }
}

The evidence checks inspect images independently. The decomposed readout receives no images and must acknowledge every saved dependency. Known negative support evidence remains usable. Unknown necessary evidence blocks the readout. This first experiment tests an ordered evidence chain, not conditional shortcutting. Structural guards and semantic audits do not prove atomic reasoning or semantic equivalence.

Budget: {"max_calls": 658, "max_completion_tokens": 1125521, "reserve_calls": 240, "reserve_tokens": 245760, "identity": {"model": "gpt-6-luna", "provider": "openai", "temperature": 0, "reasoning_effort": "none"}, "scope_limits": {"search": 109, "final": 40}}
Usage: {"calls": 124, "completion_tokens_or_reserved": 21579, "input_tokens": 282782, "consecutive_errors": 3, "stopped": "Three consecutive transport failures", "final_calls": 11, "final_tokens": 3504}
Returned models: ["gpt-6-luna"]
