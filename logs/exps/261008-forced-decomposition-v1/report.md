# Forced decomposition versus broad checking

Previously observed local fitting cases. Fresh observations compare saved label-free broad seeds with mandatory two/three-evidence-check decomposition and greedy repairs. Repeated draws are not additional cases. No generalization or atomic semantic correctness claim; evidence-only readout also changes the information flow.

Status: completed

| Method | Seed → selected reference agreement | Selected usable answers | Robust cases | Mean selected checks |
|---|---:|---:|---:|---:|
| broad-greedy | 26.7% → 60.0% | 100.0% | 2/3 | 1.00 |
| decomposed-greedy | 20.0% → 33.3% | 100.0% | 1/3 | 3.00 |

Agreement = matching the reference; coverage = usable final answers, including incorrect ones. Consistency = most common usable answer frequency. Confidence = model self-report. Each case uses five fresh final draws per program. A robust case passes every original acceptance gate. Failed/missing draws remain nonmatches.

| Case | Method | Seed matches / 5 | Selected matches / 5 | Selected usable / 5 | Lowest available confidence | Check consistency | Status / reasons |
|---|---|---:|---:|---:|---:|---|---|
| Change the background into a basketball court | broad-greedy | 4 | 4 | 5 | 0.94 | {"n1": 0.8} | locally_robust; none |
| Change the background into a basketball court | decomposed-greedy | 3 | 5 | 5 | 0.99 | {"n1": 1.0, "n2": 1.0, "n3": 1.0} | locally_robust; none |
| Turn the image into a drawing made from chalk | broad-greedy | 0 | 5 | 5 | 0.94 | {"n1": 1.0} | locally_robust; none |
| Turn the image into a drawing made from chalk | decomposed-greedy | 0 | 0 | 5 | 0.94 | {"n1": 1.0, "n2": 1.0, "n3": 1.0} | unresolved; semantic_audit, target_mismatch |
| Put a frog in the toilet | broad-greedy | 0 | 0 | 5 | 0.99 | {"n1": 1.0} | stable_but_mismatched; target_mismatch |
| Put a frog in the toilet | decomposed-greedy | 0 | 0 | 5 | 0.99 | {"n1": 1.0, "n2": 1.0, "n3": 1.0} | unresolved; semantic_audit, target_mismatch |

## Broad versus decomposed scoring fidelity

{
  "seed": {
    "agreement": 0.8666666666666667,
    "both_resolved": 0.8666666666666667,
    "per_case": [
      {
        "case_id": "aurora-task-65581617ad341fa398cb::magic_reproduce_epoch=47-step=12999",
        "same_index_matches": 3,
        "both_resolved": 3,
        "draw_pairs": 5
      },
      {
        "case_id": "aurora-task-ce641cb29939011016cc::mgie",
        "same_index_matches": 5,
        "both_resolved": 5,
        "draw_pairs": 5
      },
      {
        "case_id": "aurora-task-e0f9b97dc3bc00415cf2::mgie",
        "same_index_matches": 5,
        "both_resolved": 5,
        "draw_pairs": 5
      }
    ],
    "interpretation": "Descriptive same-index comparison of stochastic executions, not an independent sample of cases."
  },
  "selected": {
    "agreement": 0.6,
    "both_resolved": 1.0,
    "per_case": [
      {
        "case_id": "aurora-task-65581617ad341fa398cb::magic_reproduce_epoch=47-step=12999",
        "same_index_matches": 4,
        "both_resolved": 5,
        "draw_pairs": 5
      },
      {
        "case_id": "aurora-task-ce641cb29939011016cc::mgie",
        "same_index_matches": 0,
        "both_resolved": 5,
        "draw_pairs": 5
      },
      {
        "case_id": "aurora-task-e0f9b97dc3bc00415cf2::mgie",
        "same_index_matches": 5,
        "both_resolved": 5,
        "draw_pairs": 5
      }
    ],
    "interpretation": "Descriptive same-index comparison of stochastic executions, not an independent sample of cases."
  }
}

The evidence checks inspect images independently. The decomposed readout receives no images and must acknowledge every saved dependency. Known negative support evidence remains usable. Unknown necessary evidence blocks the readout. This first experiment tests an ordered evidence chain, not conditional shortcutting. Structural guards and semantic audits do not prove atomic reasoning or semantic equivalence.

Budget: {"max_calls": 900, "max_completion_tokens": 1152000, "reserve_calls": 240, "reserve_tokens": 245760, "identity": {"model": "gpt-6-luna", "provider": "openai", "temperature": 0, "reasoning_effort": "none"}, "scope_limits": {"search": 109, "final": 40}}
Usage: {"calls": 242, "completion_tokens_or_reserved": 26479, "input_tokens": 480903, "consecutive_errors": 0, "stopped": null, "final_calls": 118, "final_tokens": 9072}
Returned models: ["gpt-6-luna"]
