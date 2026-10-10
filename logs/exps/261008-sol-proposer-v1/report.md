# Luna versus Sol 6.1 proposal comparison

Three previously observed local fitting cases: jacket, paper/cup and frog. Only proposer model/configuration varies; no generalization claim.

Status: completed

Both arms retain the forced-added-check policy, transaction format, Luna semantic audit, Luna feedback and Luna image judging. Sol uses medium reasoning without temperature; Luna uses temperature zero and reasoning none. Both proposal responses are capped at 4,096 completion tokens, including reasoning tokens.

Matches means reference-label agreement across five fresh executions. Resolved means a usable answer, including wrong answers. Confidence is self-report; robustness requires approved audit plus qualifying confirmation and final verification.

| Case | Proposer | Seed → selected matches / 5 | Selected resolved / 5 | Robustness result |
|---|---|---:|---:|---|
| Make her close her jacket fully | luna-proposer | 0 → 0 | 4 | structural_failure |
| Make her close her jacket fully | sol-proposer | 0 → 0 | 0 | structural_failure |
| Stuffing the paper into the cup | luna-proposer | 4 → 0 | 0 | unconfirmed |
| Stuffing the paper into the cup | sol-proposer | 5 → 1 | 1 | unconfirmed |
| Put a frog in the toilet | luna-proposer | 0 → 0 | 4 | structural_failure |
| Put a frog in the toilet | sol-proposer | 0 → 0 | 5 | unconfirmed |

Usage: {"limits": {"max_calls": 900, "max_completion_tokens": 1152000, "reserve_calls": 240, "reserve_tokens": 245760, "identity": {"model": "gpt-6-luna", "provider": "openai", "temperature": 0, "reasoning_effort": "none"}, "routes": {"sol-proposer": {"model": "gpt-6.1-sol", "provider": "openai", "temperature": null, "reasoning_effort": "medium"}}, "scope_limits": {"search": 109, "final": 40}}, "calls": 739, "completion_tokens_or_reserved": 152625, "input_tokens": 3327286, "consecutive_errors": 0, "stopped": null, "final_calls": 173, "final_tokens": 14039}
Returned models: ["gpt-6-luna", "gpt-6.1-sol"]
Error: none

No final outcome can reopen search. Failed slots are not retried; three consecutive transport errors stop the whole run.
