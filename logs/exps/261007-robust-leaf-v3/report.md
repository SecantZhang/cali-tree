# Robust CaliTree leaf pilot

Six previously observed cases, independently fitted in four arms. Repetitions are measurements within cases, not independent cases. No held-out generalization claim.

Status: stopped

| Arm | Robust / 6 | Seed agreement | Selected agreement | Selected coverage |
|---|---:|---:|---:|---:|
| flat-greedy | 0 | 0.0% | 0.0% | 0.0% |
| flat-pareto | 0 | 0.0% | 0.0% | 0.0% |
| tree-greedy | 0 | 0.0% | 0.0% | 0.0% |
| tree-pareto | 0 | 0.0% | 0.0% | 0.0% |

Missing/unresolved draws count as nonmatches. Arm means retain all six cases.

| Case / target | Arm | Seed / selected agreement | Seed / selected coverage | Seed / selected consistency | Checks seed / selected | Tokens seed / selected | Status |
|---|---|---|---|---|---|---|---|

Confidence is generated self-report, not calibrated correctness. Atomic consistency is reported separately in results.json.
Unvisited branches are untested. All selections were frozen before final verification; final traces never guide repair.
Tree and flat views may coincide when compilation finds no useful conditional gate. Inspect topology counts before interpreting an arm difference.

Returned model identities: []
Budget: {"limits": {"max_calls": 3600, "max_completion_tokens": 4608000, "reserve_calls": 960, "reserve_tokens": 983040, "identity": {"model": "gpt-6-luna", "temperature": 0, "reasoning_effort": "none", "provider": "openai"}, "scope_limits": {"search": 109, "final": 40}}, "calls": 3, "completion_tokens_or_reserved": 6144, "input_tokens": 0, "consecutive_errors": 3, "stopped": "Three consecutive transport failures"}
Error: ProviderStopped: Three consecutive transport failures
