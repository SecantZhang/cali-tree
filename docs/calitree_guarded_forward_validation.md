# Frozen forward validation of the guarded policy

The [guarded development study](calitree_guarded_development.md) improves the
reviewed pilot while preserving local predictions. Its separate 36-case matched
comparison remains pending approval for the additional paid regular judgments.
This update completes offline validation without changing the fitted policies.

## Exact bounds before the regular baseline

For every case and bank, the analyzer evaluates No, Partial, Yes and unresolved
as hypothetical regular-judge outputs. It computes the paired correctness change
against regular and v27 using the same hypothetical answer for both systems.
These are exact extrema over possible baseline outputs, not observed accuracy,
confidence intervals or forecasts.

| Bank | Possible correct-count change versus v27 | Versus regular |
|---|---:|---:|
| 1 | −1 to +1 | −4 to +11 |
| 2 | 0 to +1 | −4 to +5 |
| 3 | −2 to +1 | −2 to +7 |

Bank 2 cannot lose to v27 on this particular frozen cohort for any regular
answer. No bank has a guaranteed strict gain. Banks 1 and 3 can regress, so the
pilot improvements do not prove forward accuracy improvement. The fitted
policies were not adjusted using these forward results.

## Runtime and cache checks

`verify_calitree_regular_aware_runtime_v35.py` runs all **432 scenarios** through
the actual `RegularAwareJudge`, using original cached bound evidence and a stub
regular response. All decisions match the frozen direct policy. There are 420
cache hits and 12 retained upstream-failure scenarios (one failed case × three
banks × four labels). Every scenario makes exactly one stub regular call; no
new extraction, per-expert calls or real model requests occur. Original regular
responses retain separate provenance from deterministic policy outputs.

`audit_calitree_forward_cache_v35.py` inspects 3,651 budget files across the
current and original checkouts. From 1,964 exact-identity ledgers, it searches
37,380 job files for compatible flat judgments. It finds **zero matching cases**.
An eligible slot must match the frozen prompt/schema, model identity, image
pair, slot protocol and token cap; a prediction from another prompt is not a
replacement baseline. The audit never scores human references or copies old
responses into the prepared collector.

Twenty-eight focused tests pass. New cases check exact hypothetical extrema,
retention of failed baselines, durable token reservations, request-budget
tampering, and rejection of caches with a different prompt or edited image.
The previously reported broader-suite missing dependencies/assets are unchanged.

## Prepared completion path

The analysis code and policy hashes are pinned in
`logs/exps/261020-guarded-forward-v32-r1/supplemental_v35/analysis_plan.json`.
Before approval, the baseline ledger and response directory remain absent.

After the separately requested approval, the existing collector can make at
most 36 GPT-6 Luna requests and use 73,728 completion tokens, plus input tokens.
It makes no retries or new extraction calls. The supplemental v35 analysis adds
zero requests. Its report checks all durable slots and independently reconciles
the input tokens and completion-token usage/reservations before reporting
regular, v27, v28 and both v35 arms. All 36 cases, including failures, remain in
the denominator.

```bash
PYTHONPATH=. python run/collect_calitree_guarded_forward_v32.py \
  --live --output-dir logs/exps/261020-guarded-forward-v32-r1
PYTHONPATH=. python run/analyze_calitree_guarded_forward_v35.py \
  --report --output-dir logs/exps/261020-guarded-forward-v32-r1
```

The first command requires paid-call approval; it has not been run. These
sources have older research exposure but are excluded from all fitting of the
new policies. A completed comparison can measure matched source-disjoint
accuracy; it will not make this a globally untouched benchmark.

Artifacts: `261020-regular-aware-runtime-v35-r1` and
`261020-forward-cache-audit-v35` under `logs/exps`, plus
`supplemental_v35/hypothetical_bounds.json` in the forward preparation.
The initial runtime report used an imprecise metadata field saying references
were not read; the original preflight does read their file for hash validation.
The corrected report states that references are not used for inference. Its
432 decisions are unchanged, and the earlier auditor source snapshot is retained.
