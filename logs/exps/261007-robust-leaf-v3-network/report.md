# Robust CaliTree leaf pilot

Six previously observed cases, independently fitted in four arms. Repetitions are measurements within cases, not independent cases. No held-out generalization claim.

Status: completed

| Arm | Robust / 6 | Seed agreement | Selected agreement | Selected coverage |
|---|---:|---:|---:|---:|
| flat-greedy | 3 | 43.3% | 46.7% | 100.0% |
| flat-pareto | 4 | 36.7% | 66.7% | 100.0% |
| tree-greedy | 4 | 43.3% | 80.0% | 96.7% |
| tree-pareto | 4 | 46.7% | 66.7% | 100.0% |

Missing/unresolved draws count as nonmatches. Arm means retain all six cases.

| Case / target | Arm | Seed / selected agreement | Seed / selected coverage | Seed / selected consistency | Checks seed / selected | Tokens seed / selected | Status |
|---|---|---|---|---|---|---|---|
| aurora-task-49616ac011dcfc46a053::magic_reproduce_epoch=47-step=12999 / no | flat-greedy | 0.00 / 0.00 | 1.00 / 1.00 | 1.00 / 1.00 | 1.00 / 1.00 | 39.20 / 39.00 | stable_but_mismatched |

flat-greedy, aurora-task-49616ac011dcfc46a053::magic_reproduce_epoch=47-step=12999: {"acceptance": {"qualified": false, "reasons": ["target_mismatch"], "policy": {"repeats": 5, "agreement": 0.8, "consistency": 0.8, "confidence": 0.8, "minimum_eligible": 3}, "reference_conflict_suspected": true}, "error": null, "search_status": "stable_but_mismatched", "stop_reason": "round_limit", "usage": {"search": 28, "final": 10, "completion_tokens_or_reserved": 3034, "input_tokens": 55214}}
| aurora-task-49616ac011dcfc46a053::magic_reproduce_epoch=47-step=12999 / no | flat-pareto | 0.00 / 1.00 | 1.00 / 1.00 | 1.00 / 1.00 | 1.00 / 1.00 | 38.60 / 62.60 | locally_robust |

flat-pareto, aurora-task-49616ac011dcfc46a053::magic_reproduce_epoch=47-step=12999: {"acceptance": {"qualified": true, "reasons": [], "policy": {"repeats": 5, "agreement": 0.8, "consistency": 0.8, "confidence": 0.8, "minimum_eligible": 3}}, "error": null, "search_status": "confirmed_local", "stop_reason": "round_limit", "usage": {"search": 26, "final": 10, "completion_tokens_or_reserved": 2806, "input_tokens": 54817}}
| aurora-task-49616ac011dcfc46a053::magic_reproduce_epoch=47-step=12999 / no | tree-greedy | 0.00 / 1.00 | 1.00 / 1.00 | 1.00 / 1.00 | 1.00 / 1.00 | 39.20 / 61.20 | locally_robust |

tree-greedy, aurora-task-49616ac011dcfc46a053::magic_reproduce_epoch=47-step=12999: {"acceptance": {"qualified": true, "reasons": [], "policy": {"repeats": 5, "agreement": 0.8, "consistency": 0.8, "confidence": 0.8, "minimum_eligible": 3}}, "error": null, "search_status": "unresolved", "stop_reason": "round_limit", "usage": {"search": 28, "final": 10, "completion_tokens_or_reserved": 3285, "input_tokens": 57477}}
| aurora-task-49616ac011dcfc46a053::magic_reproduce_epoch=47-step=12999 / no | tree-pareto | 0.00 / 1.00 | 1.00 / 1.00 | 1.00 / 1.00 | 1.00 / 1.00 | 40.80 / 60.60 | locally_robust |

tree-pareto, aurora-task-49616ac011dcfc46a053::magic_reproduce_epoch=47-step=12999: {"acceptance": {"qualified": true, "reasons": [], "policy": {"repeats": 5, "agreement": 0.8, "consistency": 0.8, "confidence": 0.8, "minimum_eligible": 3}}, "error": null, "search_status": "confirmed_local", "stop_reason": "round_limit", "usage": {"search": 28, "final": 10, "completion_tokens_or_reserved": 3312, "input_tokens": 56822}}
| aurora-task-4d9932789529604a30e8::finetune_magicbrush_ag_something_kubric_15-15-1-1_init-magic_first_epoch=02-step=41999 / yes | flat-pareto | 0.00 / 0.00 | 1.00 / 1.00 | 1.00 / 1.00 | 1.00 / 1.00 | 54.20 / 50.60 | stable_but_mismatched |

flat-pareto, aurora-task-4d9932789529604a30e8::finetune_magicbrush_ag_something_kubric_15-15-1-1_init-magic_first_epoch=02-step=41999: {"acceptance": {"qualified": false, "reasons": ["target_mismatch"], "policy": {"repeats": 5, "agreement": 0.8, "consistency": 0.8, "confidence": 0.8, "minimum_eligible": 3}, "reference_conflict_suspected": true}, "error": null, "search_status": "stable_but_mismatched", "stop_reason": "round_limit", "usage": {"search": 28, "final": 10, "completion_tokens_or_reserved": 3131, "input_tokens": 50606}}
| aurora-task-4d9932789529604a30e8::finetune_magicbrush_ag_something_kubric_15-15-1-1_init-magic_first_epoch=02-step=41999 / yes | tree-greedy | 0.00 / 0.00 | 1.00 / 1.00 | 1.00 / 1.00 | 1.00 / 1.00 | 56.40 / 54.20 | stable_but_mismatched |

tree-greedy, aurora-task-4d9932789529604a30e8::finetune_magicbrush_ag_something_kubric_15-15-1-1_init-magic_first_epoch=02-step=41999: {"acceptance": {"qualified": false, "reasons": ["target_mismatch"], "policy": {"repeats": 5, "agreement": 0.8, "consistency": 0.8, "confidence": 0.8, "minimum_eligible": 3}, "reference_conflict_suspected": true}, "error": null, "search_status": "stable_but_mismatched", "stop_reason": "round_limit", "usage": {"search": 19, "final": 10, "completion_tokens_or_reserved": 2156, "input_tokens": 42146}}
| aurora-task-4d9932789529604a30e8::finetune_magicbrush_ag_something_kubric_15-15-1-1_init-magic_first_epoch=02-step=41999 / yes | tree-pareto | 0.00 / 0.00 | 1.00 / 1.00 | 1.00 / 1.00 | 1.00 / 1.00 | 52.00 / 53.80 | stable_but_mismatched |

tree-pareto, aurora-task-4d9932789529604a30e8::finetune_magicbrush_ag_something_kubric_15-15-1-1_init-magic_first_epoch=02-step=41999: {"acceptance": {"qualified": false, "reasons": ["target_mismatch"], "policy": {"repeats": 5, "agreement": 0.8, "consistency": 0.8, "confidence": 0.8, "minimum_eligible": 3}, "reference_conflict_suspected": true}, "error": null, "search_status": "stable_but_mismatched", "stop_reason": "round_limit", "usage": {"search": 19, "final": 10, "completion_tokens_or_reserved": 2150, "input_tokens": 42047}}
| aurora-task-4d9932789529604a30e8::finetune_magicbrush_ag_something_kubric_15-15-1-1_init-magic_first_epoch=02-step=41999 / yes | flat-greedy | 0.00 / 0.00 | 1.00 / 1.00 | 1.00 / 1.00 | 1.00 / 1.00 | 58.60 / 49.80 | stable_but_mismatched |

flat-greedy, aurora-task-4d9932789529604a30e8::finetune_magicbrush_ag_something_kubric_15-15-1-1_init-magic_first_epoch=02-step=41999: {"acceptance": {"qualified": false, "reasons": ["target_mismatch"], "policy": {"repeats": 5, "agreement": 0.8, "consistency": 0.8, "confidence": 0.8, "minimum_eligible": 3}, "reference_conflict_suspected": true}, "error": null, "search_status": "stable_but_mismatched", "stop_reason": "round_limit", "usage": {"search": 28, "final": 10, "completion_tokens_or_reserved": 4056, "input_tokens": 49377}}
| aurora-task-52fd3fa52d915723d12d::mgie / partial | tree-greedy | 0.60 / 1.00 | 1.00 / 1.00 | 0.60 / 1.00 | 1.00 / 1.00 | 53.80 / 61.40 | locally_robust |

tree-greedy, aurora-task-52fd3fa52d915723d12d::mgie: {"acceptance": {"qualified": true, "reasons": [], "policy": {"repeats": 5, "agreement": 0.8, "consistency": 0.8, "confidence": 0.8, "minimum_eligible": 3}}, "error": null, "search_status": "confirmed_local", "stop_reason": "round_limit", "usage": {"search": 20, "final": 10, "completion_tokens_or_reserved": 2495, "input_tokens": 48162}}
| aurora-task-52fd3fa52d915723d12d::mgie / partial | tree-pareto | 0.80 / 1.00 | 1.00 / 1.00 | 0.80 / 1.00 | 1.00 / 1.00 | 54.40 / 60.40 | locally_robust |

tree-pareto, aurora-task-52fd3fa52d915723d12d::mgie: {"acceptance": {"qualified": true, "reasons": [], "policy": {"repeats": 5, "agreement": 0.8, "consistency": 0.8, "confidence": 0.8, "minimum_eligible": 3}}, "error": null, "search_status": "confirmed_local", "stop_reason": "round_limit", "usage": {"search": 19, "final": 10, "completion_tokens_or_reserved": 2124, "input_tokens": 46857}}
| aurora-task-52fd3fa52d915723d12d::mgie / partial | flat-greedy | 0.80 / 1.00 | 1.00 / 1.00 | 0.80 / 1.00 | 1.00 / 1.00 | 52.40 / 59.20 | locally_robust |

flat-greedy, aurora-task-52fd3fa52d915723d12d::mgie: {"acceptance": {"qualified": true, "reasons": [], "policy": {"repeats": 5, "agreement": 0.8, "consistency": 0.8, "confidence": 0.8, "minimum_eligible": 3}}, "error": null, "search_status": "confirmed_local", "stop_reason": "round_limit", "usage": {"search": 25, "final": 10, "completion_tokens_or_reserved": 5634, "input_tokens": 47410}}
| aurora-task-52fd3fa52d915723d12d::mgie / partial | flat-pareto | 0.40 / 1.00 | 0.80 / 1.00 | 0.40 / 1.00 | 1.00 / 1.00 | 247.00 / 58.60 | locally_robust |

flat-pareto, aurora-task-52fd3fa52d915723d12d::mgie: {"acceptance": {"qualified": true, "reasons": [], "policy": {"repeats": 5, "agreement": 0.8, "consistency": 0.8, "confidence": 0.8, "minimum_eligible": 3}}, "error": null, "search_status": "confirmed_local", "stop_reason": "round_limit", "usage": {"search": 28, "final": 10, "completion_tokens_or_reserved": 4261, "input_tokens": 55096}}
| aurora-task-538ef5e1e9d068bbfe6d::magic_reproduce_epoch=47-step=12999 / yes | tree-pareto | 1.00 / 1.00 | 1.00 / 1.00 | 1.00 / 1.00 | 1.00 / 1.00 | 41.00 / 40.80 | locally_robust |

tree-pareto, aurora-task-538ef5e1e9d068bbfe6d::magic_reproduce_epoch=47-step=12999: {"acceptance": {"qualified": true, "reasons": [], "policy": {"repeats": 5, "agreement": 0.8, "consistency": 0.8, "confidence": 0.8, "minimum_eligible": 3}}, "error": null, "search_status": "confirmed_local", "stop_reason": "round_limit", "usage": {"search": 12, "final": 10, "completion_tokens_or_reserved": 1016, "input_tokens": 57391}}
| aurora-task-538ef5e1e9d068bbfe6d::magic_reproduce_epoch=47-step=12999 / yes | flat-greedy | 1.00 / 1.00 | 1.00 / 1.00 | 1.00 / 1.00 | 1.00 / 1.00 | 41.00 / 40.20 | locally_robust |

flat-greedy, aurora-task-538ef5e1e9d068bbfe6d::magic_reproduce_epoch=47-step=12999: {"acceptance": {"qualified": true, "reasons": [], "policy": {"repeats": 5, "agreement": 0.8, "consistency": 0.8, "confidence": 0.8, "minimum_eligible": 3}}, "error": null, "search_status": "confirmed_local", "stop_reason": "round_limit", "usage": {"search": 12, "final": 10, "completion_tokens_or_reserved": 1091, "input_tokens": 57426}}
| aurora-task-538ef5e1e9d068bbfe6d::magic_reproduce_epoch=47-step=12999 / yes | flat-pareto | 1.00 / 1.00 | 1.00 / 1.00 | 1.00 / 1.00 | 1.00 / 1.00 | 40.80 / 40.80 | locally_robust |

flat-pareto, aurora-task-538ef5e1e9d068bbfe6d::magic_reproduce_epoch=47-step=12999: {"acceptance": {"qualified": true, "reasons": [], "policy": {"repeats": 5, "agreement": 0.8, "consistency": 0.8, "confidence": 0.8, "minimum_eligible": 3}}, "error": null, "search_status": "confirmed_local", "stop_reason": "round_limit", "usage": {"search": 12, "final": 10, "completion_tokens_or_reserved": 980, "input_tokens": 57264}}
| aurora-task-538ef5e1e9d068bbfe6d::magic_reproduce_epoch=47-step=12999 / yes | tree-greedy | 1.00 / 0.80 | 1.00 / 0.80 | 1.00 / 0.80 | 1.00 / 1.00 | 41.80 / 239.40 | unresolved |

tree-greedy, aurora-task-538ef5e1e9d068bbfe6d::magic_reproduce_epoch=47-step=12999: {"acceptance": {"qualified": false, "reasons": ["unresolved", "confidence"], "policy": {"repeats": 5, "agreement": 0.8, "consistency": 0.8, "confidence": 0.8, "minimum_eligible": 3}}, "error": null, "search_status": "confirmed_local", "stop_reason": "round_limit", "usage": {"search": 11, "final": 10, "completion_tokens_or_reserved": 3978, "input_tokens": 46864}}
| aurora-task-7b78f1229d9bb014bcc5::finetune_magicbrush_ag_something_kubric_15-15-1-1_init-magic_first_epoch=02-step=41999 / partial | flat-greedy | 0.00 / 0.00 | 1.00 / 1.00 | 1.00 / 1.00 | 1.00 / 1.00 | 53.60 / 45.60 | stable_but_mismatched |

flat-greedy, aurora-task-7b78f1229d9bb014bcc5::finetune_magicbrush_ag_something_kubric_15-15-1-1_init-magic_first_epoch=02-step=41999: {"acceptance": {"qualified": false, "reasons": ["target_mismatch"], "policy": {"repeats": 5, "agreement": 0.8, "consistency": 0.8, "confidence": 0.8, "minimum_eligible": 3}, "reference_conflict_suspected": true}, "error": null, "search_status": "stable_but_mismatched", "stop_reason": "round_limit", "usage": {"search": 20, "final": 10, "completion_tokens_or_reserved": 4659, "input_tokens": 72249}}
| aurora-task-7b78f1229d9bb014bcc5::finetune_magicbrush_ag_something_kubric_15-15-1-1_init-magic_first_epoch=02-step=41999 / partial | flat-pareto | 0.00 / 0.00 | 1.00 / 1.00 | 1.00 / 1.00 | 1.00 / 1.00 | 45.60 / 45.00 | stable_but_mismatched |

flat-pareto, aurora-task-7b78f1229d9bb014bcc5::finetune_magicbrush_ag_something_kubric_15-15-1-1_init-magic_first_epoch=02-step=41999: {"acceptance": {"qualified": false, "reasons": ["target_mismatch"], "policy": {"repeats": 5, "agreement": 0.8, "consistency": 0.8, "confidence": 0.8, "minimum_eligible": 3}, "reference_conflict_suspected": true}, "error": null, "search_status": "stable_but_mismatched", "stop_reason": "round_limit", "usage": {"search": 27, "final": 10, "completion_tokens_or_reserved": 3478, "input_tokens": 91243}}
| aurora-task-7b78f1229d9bb014bcc5::finetune_magicbrush_ag_something_kubric_15-15-1-1_init-magic_first_epoch=02-step=41999 / partial | tree-greedy | 0.00 / 1.00 | 1.00 / 1.00 | 1.00 / 1.00 | 1.00 / 1.00 | 46.40 / 54.60 | locally_robust |

tree-greedy, aurora-task-7b78f1229d9bb014bcc5::finetune_magicbrush_ag_something_kubric_15-15-1-1_init-magic_first_epoch=02-step=41999: {"acceptance": {"qualified": true, "reasons": [], "policy": {"repeats": 5, "agreement": 0.8, "consistency": 0.8, "confidence": 0.8, "minimum_eligible": 3}}, "error": null, "search_status": "confirmed_local", "stop_reason": "round_limit", "usage": {"search": 22, "final": 10, "completion_tokens_or_reserved": 2988, "input_tokens": 80883}}
| aurora-task-7b78f1229d9bb014bcc5::finetune_magicbrush_ag_something_kubric_15-15-1-1_init-magic_first_epoch=02-step=41999 / partial | tree-pareto | 0.00 / 0.00 | 1.00 / 1.00 | 1.00 / 1.00 | 1.00 / 1.00 | 45.40 / 45.20 | stable_but_mismatched |

tree-pareto, aurora-task-7b78f1229d9bb014bcc5::finetune_magicbrush_ag_something_kubric_15-15-1-1_init-magic_first_epoch=02-step=41999: {"acceptance": {"qualified": false, "reasons": ["target_mismatch"], "policy": {"repeats": 5, "agreement": 0.8, "consistency": 0.8, "confidence": 0.8, "minimum_eligible": 3}, "reference_conflict_suspected": true}, "error": null, "search_status": "stable_but_mismatched", "stop_reason": "round_limit", "usage": {"search": 21, "final": 10, "completion_tokens_or_reserved": 2856, "input_tokens": 77799}}
| aurora-task-88caae46533b0440f452::finetune_magicbrush_ag_something_kubric_15-15-1-1_init-magic_first_epoch=02-step=41999 / no | flat-pareto | 0.80 / 1.00 | 1.00 / 1.00 | 0.80 / 1.00 | 1.00 / 1.00 | 57.40 / 62.60 | locally_robust |

flat-pareto, aurora-task-88caae46533b0440f452::finetune_magicbrush_ag_something_kubric_15-15-1-1_init-magic_first_epoch=02-step=41999: {"acceptance": {"qualified": true, "reasons": [], "policy": {"repeats": 5, "agreement": 0.8, "consistency": 0.8, "confidence": 0.8, "minimum_eligible": 3}}, "error": null, "search_status": "confirmed_local", "stop_reason": "round_limit", "usage": {"search": 27, "final": 10, "completion_tokens_or_reserved": 3484, "input_tokens": 92769}}
| aurora-task-88caae46533b0440f452::finetune_magicbrush_ag_something_kubric_15-15-1-1_init-magic_first_epoch=02-step=41999 / no | tree-greedy | 1.00 / 1.00 | 1.00 / 1.00 | 1.00 / 1.00 | 1.00 / 1.00 | 55.60 / 60.60 | locally_robust |

tree-greedy, aurora-task-88caae46533b0440f452::finetune_magicbrush_ag_something_kubric_15-15-1-1_init-magic_first_epoch=02-step=41999: {"acceptance": {"qualified": true, "reasons": [], "policy": {"repeats": 5, "agreement": 0.8, "consistency": 0.8, "confidence": 0.8, "minimum_eligible": 3}}, "error": null, "search_status": "confirmed_local", "stop_reason": "round_limit", "usage": {"search": 21, "final": 10, "completion_tokens_or_reserved": 2475, "input_tokens": 78639}}
| aurora-task-88caae46533b0440f452::finetune_magicbrush_ag_something_kubric_15-15-1-1_init-magic_first_epoch=02-step=41999 / no | tree-pareto | 1.00 / 1.00 | 1.00 / 1.00 | 1.00 / 1.00 | 1.00 / 1.00 | 54.60 / 70.60 | locally_robust |

tree-pareto, aurora-task-88caae46533b0440f452::finetune_magicbrush_ag_something_kubric_15-15-1-1_init-magic_first_epoch=02-step=41999: {"acceptance": {"qualified": true, "reasons": [], "policy": {"repeats": 5, "agreement": 0.8, "consistency": 0.8, "confidence": 0.8, "minimum_eligible": 3}}, "error": null, "search_status": "confirmed_local", "stop_reason": "round_limit", "usage": {"search": 28, "final": 10, "completion_tokens_or_reserved": 3661, "input_tokens": 94999}}
| aurora-task-88caae46533b0440f452::finetune_magicbrush_ag_something_kubric_15-15-1-1_init-magic_first_epoch=02-step=41999 / no | flat-greedy | 0.80 / 0.80 | 1.00 / 1.00 | 0.80 / 0.80 | 1.00 / 1.00 | 57.60 / 56.00 | locally_robust |

flat-greedy, aurora-task-88caae46533b0440f452::finetune_magicbrush_ag_something_kubric_15-15-1-1_init-magic_first_epoch=02-step=41999: {"acceptance": {"qualified": true, "reasons": [], "policy": {"repeats": 5, "agreement": 0.8, "consistency": 0.8, "confidence": 0.8, "minimum_eligible": 3}}, "error": null, "search_status": "confirmed_local", "stop_reason": "round_limit", "usage": {"search": 27, "final": 10, "completion_tokens_or_reserved": 3289, "input_tokens": 91399}}

Confidence is generated self-report, not calibrated correctness. Atomic consistency is reported separately in results.json.
Unvisited branches are untested. All selections were frozen before final verification; final traces never guide repair.
Tree and flat views may coincide when compilation finds no useful conditional gate. Inspect topology counts before interpreting an arm difference.

Returned model identities: ["gpt-6-luna"]
Budget: {"limits": {"max_calls": 3597, "max_completion_tokens": 4601856, "reserve_calls": 960, "reserve_tokens": 983040, "identity": {"model": "gpt-6-luna", "temperature": 0, "reasoning_effort": "none", "provider": "openai"}, "scope_limits": {"search": 109, "final": 40}}, "calls": 788, "completion_tokens_or_reserved": 74166, "input_tokens": 1517184, "consecutive_errors": 0, "stopped": null, "final_calls": 240, "final_tokens": 14201}
Error: none
