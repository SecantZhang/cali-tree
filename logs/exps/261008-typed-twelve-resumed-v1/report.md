# Twelve-case typed evidence optimizer comparison

Twelve previously observed local fitting cases. Four per reference class. No cross-case feedback, atomic correctness or held-out generalization claim.

Status: stopped

| Method | Mean seed → selected matches / 5 | Selected usable / 5 | Locally robust cases |
|---|---:|---:|---:|
| criterion-only | 0.00 → 0.00 | 0.00 | 0/12 |
| nested-required | 0.00 → 0.00 | 0.00 | 0/12 |

Missing/unattempted/invalid draws are nonmatches in the full twelve-case denominator. Usable means resolved, including wrong labels. Repeats are within cases, not independent cases.

| Case / reference | Method | Seed → selected matches / 5 | Usable / 5 | Rounds completed | Nested checks | Status / reasons |
|---|---|---:|---:|---:|---|---|
| transform the black DVD into a white DVD / no | criterion-only | 0 → 0 | 0 | unavailable | none | unattempted; none |
| transform the black DVD into a white DVD / no | nested-required | 0 → 0 | 0 | unavailable | none | unattempted; none |
| Make her close her jacket fully / yes | criterion-only | 0 → 0 | 0 | unavailable | none | unattempted; none |
| Make her close her jacket fully / yes | nested-required | 0 → 0 | 0 | unavailable | none | unattempted; none |
| Change the image into pencil drawing / partial | criterion-only | 0 → 0 | 0 | unavailable | none | unattempted; none |
| Change the image into pencil drawing / partial | nested-required | 0 → 0 | 0 | unavailable | none | unattempted; none |
| Give the woman a helmet / yes | criterion-only | 0 → 0 | 0 | unavailable | none | unattempted; none |
| Give the woman a helmet / yes | nested-required | 0 → 0 | 0 | unavailable | none | unattempted; none |
| Change the background into a basketball court / yes | criterion-only | 0 → 0 | 0 | unavailable | none | unattempted; none |
| Change the background into a basketball court / yes | nested-required | 0 → 0 | 0 | unavailable | none | unattempted; none |
| Move the mug to the right of the headphones / partial | criterion-only | 0 → 0 | 0 | unavailable | none | unattempted; none |
| Move the mug to the right of the headphones / partial | nested-required | 0 → 0 | 0 | unavailable | none | unattempted; none |
| Move the book behind the flower / no | criterion-only | 0 → 0 | 0 | unavailable | none | unattempted; none |
| Move the book behind the flower / no | nested-required | 0 → 0 | 0 | unavailable | none | unattempted; none |
| Stuffing the paper into the cup / no | criterion-only | 0 → 0 | 0 | unavailable | none | unattempted; none |
| Stuffing the paper into the cup / no | nested-required | 0 → 0 | 0 | unavailable | none | unattempted; none |
| Make this look like a comic book photo / no | criterion-only | 0 → 0 | 0 | unavailable | none | unattempted; none |
| Make this look like a comic book photo / no | nested-required | 0 → 0 | 0 | unavailable | none | unattempted; none |
| Turn the image into a drawing made from chalk / partial | criterion-only | 0 → 0 | 0 | unavailable | none | unattempted; none |
| Turn the image into a drawing made from chalk / partial | nested-required | 0 → 0 | 0 | unavailable | none | unattempted; none |
| Put a frog in the toilet / partial | criterion-only | 0 → 0 | 0 | unavailable | none | unattempted; none |
| Put a frog in the toilet / partial | nested-required | 0 → 0 | 0 | unavailable | none | unattempted; none |
| the small gray rubber cylinder becomes brown / yes | criterion-only | 0 → 0 | 0 | unavailable | none | unattempted; none |
| the small gray rubber cylinder becomes brown / yes | nested-required | 0 → 0 | 0 | unavailable | none | unattempted; none |

Confirmation success is provisional; final verification remains frozen and independent. Negative support is usable evidence. Confidence is self-report; consistency is not atomic correctness.

Returned models: ["gpt-6-luna"]
Usage: {"limits": {"max_calls": 3600, "max_completion_tokens": 4608000, "reserve_calls": 960, "reserve_tokens": 983040, "identity": {"model": "gpt-6-luna", "provider": "openai", "temperature": 0, "reasoning_effort": "none"}, "scope_limits": {"search": 109, "final": 40}}, "calls": 1413, "completion_tokens_or_reserved": 293366, "input_tokens": 4715746, "consecutive_errors": 0, "stopped": "Three consecutive transport failures", "authorized_resumes": [{"source": "/Users/zzhang/Documents/Projects/Adobe/calitree-mlsys/logs/exps/261008-typed-twelve-v2", "stop": "Three consecutive transport failures", "calls": 684, "consecutive_errors": 0, "completion_tokens_or_reserved": 133385}]}
Error: ProviderStopped: Three consecutive transport failures
