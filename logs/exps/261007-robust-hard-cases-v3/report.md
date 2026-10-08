# Robust CaliTree leaf pilot

Three failure-selected, previously observed local fitting cases outside the prior six-case v3 pilot. Selected before new calls by lowest mean saved seed agreement across custom, GEPA and TextGrad. This intentionally difficult subset is not class-balanced or a held-out generalization evaluation. Repetitions measure behavior within cases, not independent cases.

Status: completed

| Arm | Robust / 3 | Seed agreement | Selected agreement | Selected coverage |
|---|---:|---:|---:|---:|
| flat-greedy | 1 | 20.0% | 73.3% | 93.3% |
| flat-pareto | 1 | 13.3% | 40.0% | 100.0% |
| tree-greedy | 2 | 26.7% | 66.7% | 100.0% |
| tree-pareto | 0 | 13.3% | 33.3% | 93.3% |

Missing/unresolved draws count as nonmatches. Arm means retain all 3 cases.

| Case / target | Arm | Seed / selected agreement | Seed / selected coverage | Seed / selected consistency | Checks seed / selected | Tokens seed / selected | Status |
|---|---|---|---|---|---|---|---|
| aurora-task-65581617ad341fa398cb::magic_reproduce_epoch=47-step=12999 / yes | flat-greedy | 0.60 / 1.00 | 1.00 / 1.00 | 0.60 / 1.00 | 1.00 / 1.00 | 51.80 / 47.40 | locally_robust |

flat-greedy, aurora-task-65581617ad341fa398cb::magic_reproduce_epoch=47-step=12999: {"acceptance": {"qualified": true, "reasons": [], "policy": {"repeats": 5, "agreement": 0.8, "consistency": 0.8, "confidence": 0.8, "minimum_eligible": 3}}, "error": null, "search_status": "confirmed_local", "stop_reason": "round_limit", "usage": {"search": 26, "final": 10, "completion_tokens_or_reserved": 2564, "input_tokens": 54370}}
| aurora-task-65581617ad341fa398cb::magic_reproduce_epoch=47-step=12999 / yes | flat-pareto | 0.20 / 1.00 | 1.00 / 1.00 | 0.80 / 1.00 | 1.00 / 1.00 | 54.60 / 51.60 | locally_robust |

flat-pareto, aurora-task-65581617ad341fa398cb::magic_reproduce_epoch=47-step=12999: {"acceptance": {"qualified": true, "reasons": [], "policy": {"repeats": 5, "agreement": 0.8, "consistency": 0.8, "confidence": 0.8, "minimum_eligible": 3}}, "error": null, "search_status": "confirmed_local", "stop_reason": "round_limit", "usage": {"search": 21, "final": 10, "completion_tokens_or_reserved": 4602, "input_tokens": 45004}}
| aurora-task-65581617ad341fa398cb::magic_reproduce_epoch=47-step=12999 / yes | tree-greedy | 0.60 / 1.00 | 1.00 / 1.00 | 0.60 / 1.00 | 1.00 / 1.00 | 51.00 / 52.60 | locally_robust |

tree-greedy, aurora-task-65581617ad341fa398cb::magic_reproduce_epoch=47-step=12999: {"acceptance": {"qualified": true, "reasons": [], "policy": {"repeats": 5, "agreement": 0.8, "consistency": 0.8, "confidence": 0.8, "minimum_eligible": 3}}, "error": null, "search_status": "confirmed_local", "stop_reason": "round_limit", "usage": {"search": 28, "final": 10, "completion_tokens_or_reserved": 4221, "input_tokens": 56729}}
| aurora-task-65581617ad341fa398cb::magic_reproduce_epoch=47-step=12999 / yes | tree-pareto | 0.20 / 0.20 | 1.00 / 1.00 | 0.80 / 0.80 | 1.00 / 1.00 | 57.60 / 62.00 | unstable_and_mismatched |

tree-pareto, aurora-task-65581617ad341fa398cb::magic_reproduce_epoch=47-step=12999: {"acceptance": {"qualified": false, "reasons": ["target_mismatch"], "policy": {"repeats": 5, "agreement": 0.8, "consistency": 0.8, "confidence": 0.8, "minimum_eligible": 3}}, "error": null, "search_status": "unresolved", "stop_reason": "round_limit", "usage": {"search": 28, "final": 10, "completion_tokens_or_reserved": 5110, "input_tokens": 54062}}
| aurora-task-ce641cb29939011016cc::mgie / partial | flat-pareto | 0.00 / 0.00 | 1.00 / 1.00 | 1.00 / 1.00 | 1.00 / 1.00 | 51.00 / 50.00 | stable_but_mismatched |

flat-pareto, aurora-task-ce641cb29939011016cc::mgie: {"acceptance": {"qualified": false, "reasons": ["target_mismatch"], "policy": {"repeats": 5, "agreement": 0.8, "consistency": 0.8, "confidence": 0.8, "minimum_eligible": 3}, "reference_conflict_suspected": true}, "error": null, "search_status": "stable_but_mismatched", "stop_reason": "round_limit", "usage": {"search": 22, "final": 10, "completion_tokens_or_reserved": 2904, "input_tokens": 49697}}
| aurora-task-ce641cb29939011016cc::mgie / partial | tree-greedy | 0.00 / 1.00 | 0.80 / 1.00 | 0.80 / 1.00 | 1.00 / 1.00 | 246.40 / 56.40 | locally_robust |

tree-greedy, aurora-task-ce641cb29939011016cc::mgie: {"acceptance": {"qualified": true, "reasons": [], "policy": {"repeats": 5, "agreement": 0.8, "consistency": 0.8, "confidence": 0.8, "minimum_eligible": 3}}, "error": null, "search_status": "confirmed_local", "stop_reason": "round_limit", "usage": {"search": 22, "final": 10, "completion_tokens_or_reserved": 3897, "input_tokens": 48763}}
| aurora-task-ce641cb29939011016cc::mgie / partial | tree-pareto | 0.20 / 0.80 | 1.00 / 0.80 | 0.80 / 0.80 | 1.00 / 1.00 | 54.20 / 251.20 | unresolved |

tree-pareto, aurora-task-ce641cb29939011016cc::mgie: {"acceptance": {"qualified": false, "reasons": ["unresolved", "confidence"], "policy": {"repeats": 5, "agreement": 0.8, "consistency": 0.8, "confidence": 0.8, "minimum_eligible": 3}}, "error": null, "search_status": "confirmed_local", "stop_reason": "round_limit", "usage": {"search": 22, "final": 10, "completion_tokens_or_reserved": 3723, "input_tokens": 48054}}
| aurora-task-ce641cb29939011016cc::mgie / partial | flat-greedy | 0.00 / 0.80 | 1.00 / 0.80 | 1.00 / 0.80 | 1.00 / 1.00 | 53.20 / 253.60 | unresolved |

flat-greedy, aurora-task-ce641cb29939011016cc::mgie: {"acceptance": {"qualified": false, "reasons": ["unresolved", "confidence"], "policy": {"repeats": 5, "agreement": 0.8, "consistency": 0.8, "confidence": 0.8, "minimum_eligible": 3}}, "error": null, "search_status": "confirmed_local", "stop_reason": "round_limit", "usage": {"search": 19, "final": 10, "completion_tokens_or_reserved": 5136, "input_tokens": 42135}}
| aurora-task-e0f9b97dc3bc00415cf2::mgie / partial | tree-greedy | 0.20 / 0.00 | 0.80 / 1.00 | 0.60 / 1.00 | 1.00 / 1.00 | 240.40 / 59.00 | stable_but_mismatched |

tree-greedy, aurora-task-e0f9b97dc3bc00415cf2::mgie: {"acceptance": {"qualified": false, "reasons": ["target_mismatch"], "policy": {"repeats": 5, "agreement": 0.8, "consistency": 0.8, "confidence": 0.8, "minimum_eligible": 3}, "reference_conflict_suspected": true}, "error": null, "search_status": "stable_but_mismatched", "stop_reason": "round_limit", "usage": {"search": 19, "final": 10, "completion_tokens_or_reserved": 5032, "input_tokens": 89890}}
| aurora-task-e0f9b97dc3bc00415cf2::mgie / partial | tree-pareto | 0.00 / 0.00 | 1.00 / 1.00 | 1.00 / 1.00 | 1.00 / 1.00 | 41.20 / 41.80 | stable_but_mismatched |

tree-pareto, aurora-task-e0f9b97dc3bc00415cf2::mgie: {"acceptance": {"qualified": false, "reasons": ["target_mismatch"], "policy": {"repeats": 5, "agreement": 0.8, "consistency": 0.8, "confidence": 0.8, "minimum_eligible": 3}, "reference_conflict_suspected": true}, "error": null, "search_status": "stable_but_mismatched", "stop_reason": "round_limit", "usage": {"search": 21, "final": 10, "completion_tokens_or_reserved": 4112, "input_tokens": 94868}}
| aurora-task-e0f9b97dc3bc00415cf2::mgie / partial | flat-greedy | 0.00 / 0.40 | 1.00 / 1.00 | 1.00 / 0.60 | 1.00 / 1.00 | 41.20 / 48.40 | unstable_and_mismatched |

flat-greedy, aurora-task-e0f9b97dc3bc00415cf2::mgie: {"acceptance": {"qualified": false, "reasons": ["target_mismatch", "requirement_instability", "node_instability:n1"], "policy": {"repeats": 5, "agreement": 0.8, "consistency": 0.8, "confidence": 0.8, "minimum_eligible": 3}}, "error": null, "search_status": "stable_but_mismatched", "stop_reason": "round_limit", "usage": {"search": 20, "final": 10, "completion_tokens_or_reserved": 2222, "input_tokens": 97947}}
| aurora-task-e0f9b97dc3bc00415cf2::mgie / partial | flat-pareto | 0.20 / 0.20 | 1.00 / 1.00 | 0.80 / 0.80 | 1.00 / 1.00 | 46.00 / 41.20 | unstable_and_mismatched |

flat-pareto, aurora-task-e0f9b97dc3bc00415cf2::mgie: {"acceptance": {"qualified": false, "reasons": ["target_mismatch"], "policy": {"repeats": 5, "agreement": 0.8, "consistency": 0.8, "confidence": 0.8, "minimum_eligible": 3}}, "error": null, "search_status": "unstable_and_mismatched", "stop_reason": "round_limit", "usage": {"search": 18, "final": 10, "completion_tokens_or_reserved": 4750, "input_tokens": 84202}}

Confidence is generated self-report, not calibrated correctness. Atomic consistency is reported separately in results.json.
Unvisited branches are untested. All selections were frozen before final verification; final traces never guide repair.
Tree and flat views may coincide when compilation finds no useful conditional gate. Inspect topology counts before interpreting an arm difference.

Returned model identities: ["gpt-6-luna"]
Budget: {"limits": {"max_calls": 1800, "max_completion_tokens": 2304000, "reserve_calls": 480, "reserve_tokens": 491520, "identity": {"model": "gpt-6-luna", "temperature": 0, "reasoning_effort": "none", "provider": "openai"}, "scope_limits": {"search": 109, "final": 40}}, "calls": 392, "completion_tokens_or_reserved": 49178, "input_tokens": 771885, "consecutive_errors": 0, "stopped": null, "final_calls": 120, "final_tokens": 10019}
Error: none
