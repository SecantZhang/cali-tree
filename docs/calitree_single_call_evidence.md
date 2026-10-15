# Single-call evidence judge

This opt-in judge records explicit checks in one multimodal response, then applies
a fixed label policy in Python. It does not replace or optimize the existing
fulfillment pipeline.

The model receives only the instruction and labeled SOURCE/EDITED images. Its
structured response contains:

- An interpretation of the instruction's target and scope.
- Target correspondence: matched, wrong target, or unknown.
- Relevant source integrity: preserved, material deviation, meaning destroyed,
  or unknown. Authorized scene/style transformations count as preserved.
- One to six material requirements, each with an exact instruction quote, an
  observable question, core/constraint role, visible evidence, and a state of
  complete, incomplete, absent, or unknown.

Core requirements are the requested transformations/actions/results. Constraints
are explicit material qualifiers, quantities, relations, or scope. The model
selects these roles in the same response; code verifies structure and provenance,
not the semantic correctness or completeness of the decomposition.

## Fixed policy

The policy `core-fulfillment-material-shortfall-v1` has no fitted weights or
numeric thresholds. For fully observed evidence:

1. Wrong target or destroyed source meaning yields No.
2. If all core requirements are absent, yield No. Satisfying a constraint cannot
   substitute for performing the requested action.
3. If every requirement is complete and relevant source integrity is preserved,
   yield Yes.
4. Otherwise, some core fulfillment with a material shortfall yields Partial.

Unknown states are expanded to their possible known states. A label is returned
only when every possible completion yields the same label. Otherwise the result
is unresolved. Malformed observations are rejected and remain unresolved in the
benchmark denominator. No model chooses the final label.

The versioned prompt is
`critical/core/prompts/templates/single_call_evidence_v1/check.txt`; implementation
and response schema are in `critical/core/decision/single_call.py`.

## Matched twelve-case benchmark

```sh
.venv/bin/python -m run.calitree_single_call --preflight \
  --output-dir logs/exps/NEW-EVIDENCE-RUN
.venv/bin/python -u -m run.calitree_single_call --live \
  --output-dir logs/exps/NEW-EVIDENCE-RUN
.venv/bin/python -m run.calitree_single_call --replay \
  --output-dir logs/exps/NEW-EVIDENCE-RUN
```

The default baseline is `logs/exps/261013-flat-sol-high-balanced12`; override it
with `--baseline-dir` only for a compatible saved flat run. Preflight verifies
its manifest, images, responses, and four-per-class sample. It freezes the new
prompt, schema, policy, code snapshot, and baseline hashes before calls.

Both arms use GPT-6.1 Sol at high reasoning, temperature omitted, a 16,384
completion-token cap, one SOURCE-first presentation and one judgment per case.
The twelve saved flat judgments are reused; only twelve new calls are authorized.
Four workers process independent cases. Each case has its own durable one-attempt
ledger; interrupted/failed slots cannot be resampled. Replay must reproduce the
saved results without making a provider call. All human labels and scores stay
outside inference payloads.

Results include accuracy, per-class recall, coverage, paired improvements and
regressions, exact McNemar diagnostic, token usage, and every evidence record.
Failures and unresolved cases remain in the accuracy denominator.

## Limits of the comparison

These twelve cases have already been inspected. They are a diagnostic comparison,
not an untouched test or evidence of broad generalization. Their references come
from released aggregate human means, discretized at 0.5/1.5; they are not atomic
human check annotations. One response per case does not measure repeat robustness.
Checks within one call share visual and reasoning errors. Model-selected scope,
requirements, and materiality remain potential sources of error.

The prompt, evidence representation, and label aggregation change together, so
the comparison does not isolate decomposition alone. Matching a model alias and
settings does not guarantee an identical provider backend snapshot across calls.
