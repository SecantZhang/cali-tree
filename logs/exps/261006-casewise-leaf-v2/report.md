# CaliTree casewise leaf optimization

Previously observed cases fitted independently using their own labels. No generalization evaluation.

Status: completed

| Case | Target | Seed agreement | Selected agreement | Coverage | Flips | Atomic unstable/unknown | Checks | Status |
|---|---|---:|---:|---:|---:|---:|---:|---|
| aurora-task-49616ac011dcfc46a053::magic_reproduce_epoch=47-step=12999 | no | 0.0% | 66.7% | 100.0% | 33.3% | 100.0% | 3 | unstable |

Search: unstable; stop: round_limit; usage: {"search": 15, "final": 6, "completion_tokens_or_reserved": 1995, "input_tokens": 23661}
| aurora-task-4d9932789529604a30e8::finetune_magicbrush_ag_something_kubric_15-15-1-1_init-magic_first_epoch=02-step=41999 | yes | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% | 3 | unmatched |

Search: unmatched; stop: round_limit; usage: {"search": 13, "final": 6, "completion_tokens_or_reserved": 1985, "input_tokens": 19285}
| aurora-task-52fd3fa52d915723d12d::mgie | partial | 66.7% | 100.0% | 100.0% | 0.0% | 0.0% | 3 | locally_fitted |

Search: confirmed_local; stop: matching_confirmation; usage: {"search": 15, "final": 6, "completion_tokens_or_reserved": 1939, "input_tokens": 23476}
| aurora-task-538ef5e1e9d068bbfe6d::magic_reproduce_epoch=47-step=12999 | yes | 100.0% | 100.0% | 100.0% | 0.0% | 0.0% | 3 | locally_fitted |

Search: confirmed_local; stop: seed_matches; usage: {"search": 6, "final": 6, "completion_tokens_or_reserved": 645, "input_tokens": 20987}
| aurora-task-65581617ad341fa398cb::magic_reproduce_epoch=47-step=12999 | yes | 66.7% | 33.3% | 100.0% | 33.3% | 100.0% | 3 | unstable |

Search: confirmed_local; stop: seed_matches; usage: {"search": 6, "final": 6, "completion_tokens_or_reserved": 738, "input_tokens": 11851}
| aurora-task-7b78f1229d9bb014bcc5::finetune_magicbrush_ag_something_kubric_15-15-1-1_init-magic_first_epoch=02-step=41999 | partial | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% | 6 | unmatched |

Search: unmatched; stop: round_limit; usage: {"search": 13, "final": 12, "completion_tokens_or_reserved": 2113, "input_tokens": 51532}
| aurora-task-88caae46533b0440f452::finetune_magicbrush_ag_something_kubric_15-15-1-1_init-magic_first_epoch=02-step=41999 | no | 100.0% | 100.0% | 100.0% | 0.0% | 0.0% | 3 | locally_fitted |

Search: confirmed_local; stop: seed_matches; usage: {"search": 6, "final": 6, "completion_tokens_or_reserved": 777, "input_tokens": 22616}
| aurora-task-9a1ea55edac097679512::mgie | no | 100.0% | 100.0% | 100.0% | 0.0% | 0.0% | 3 | locally_fitted |

Search: confirmed_local; stop: seed_matches; usage: {"search": 6, "final": 6, "completion_tokens_or_reserved": 824, "input_tokens": 8709}
| aurora-task-bfa82afe32a86d47dfdf::finetune_magicbrush_ag_something_kubric_15-15-1-1_init-magic_first_epoch=02-step=41999 | no | 100.0% | 100.0% | 100.0% | 0.0% | 0.0% | 3 | locally_fitted |

Search: confirmed_local; stop: seed_matches; usage: {"search": 6, "final": 6, "completion_tokens_or_reserved": 821, "input_tokens": 11910}
| aurora-task-ce641cb29939011016cc::mgie | partial | 33.3% | 66.7% | 100.0% | 33.3% | 100.0% | 3 | unstable |

Search: unstable; stop: round_limit; usage: {"search": 13, "final": 6, "completion_tokens_or_reserved": 1841, "input_tokens": 22177}
| aurora-task-e0f9b97dc3bc00415cf2::mgie | partial | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% | 3 | unmatched |

Search: unmatched; stop: round_limit; usage: {"search": 10, "final": 6, "completion_tokens_or_reserved": 3313, "input_tokens": 36527}
| aurora-task-f335b1c6c0f2062b2cfd::finetune_magicbrush_ag_something_kubric_15-15-1-1_init-magic_first_epoch=02-step=41999 | yes | 100.0% | 100.0% | 100.0% | 0.0% | 0.0% | 6 | locally_fitted |

Search: confirmed_local; stop: seed_matches; usage: {"search": 10, "final": 12, "completion_tokens_or_reserved": 1185, "input_tokens": 20372}

Three repetitions are one case, not three independent samples. Agreement and semantic audits do not certify atomic visual correctness.
Final comparisons never feed repair. All fitting is local; no reuse or generalization claim is made.

Budget: {"limits": {"max_calls": 600, "max_completion_tokens": 768000, "reserve_calls": 288, "reserve_tokens": 294912, "identity": {"model": "gpt-6-luna", "temperature": 0, "reasoning_effort": "none"}}, "calls": 203, "completion_tokens_or_reserved": 18176, "input_tokens": 273103, "consecutive_errors": 0, "stopped": null, "final_calls": 84, "final_tokens": 3825}

Error: none
