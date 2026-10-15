# M2 v8: reusable semantic rules with above-90% local accuracy

**Date:** October 14, 2026. **Status:** implemented and verified for the user's
clarified objective: rules should not be specific to a case's input. Held-out
accuracy is a separate future evaluation, rather than this version's acceptance
gate. The user also permitted local accuracy above 90% instead of perfect fit.

The recommended reviewed policy scores **44/48 (91.7%)**, with fourteen rules
using thirteen distinct semantic predicates. Every rule has at least two
distinct source cases and two distinct instruction texts supporting it.

| Local reference class | Correct |
|---|---:|
| No | 16/16 |
| Partial | 15/16 |
| Yes | 13/16 |

One Partial case still lacks its original M1 observation. It remains unresolved
and stays in the denominator. Three Yes cases remain disagreements. Their
references and original observations were not edited or replaced.

## What “reusable” means here

The policy language can express instruction-dependent conditions about:

- Whether requested endpoints are reached or a core outcome remains missing.
- Whether identity retention requires the same instance or only a recognizable
  transformed counterpart.
- Whether an unrelated change is material or minor.
- Whether any/all applicable physical outcome, identity, preservation, or
  intermediate checks have a specified evidence state.
- Whether the instruction requests a type of outcome, such as physical contact.

It cannot express a condition containing a case/source ID, image hash, object
name, exact instruction string, pixel coordinate, raw count of generated
checks, or a majority-of-checks threshold. It does not route by looking up an
observed case's complete feature signature.

The runtime artifact contains only the predicate schema reference, semantic
condition tree, predicate descriptions, and output labels. All fitting records,
source IDs, batch IDs, support examples, and class-count provenance are kept in
separate training/audit artifacts. They are not available to its decision logic.

M1 still binds the instruction to concrete objects and desired values. That is
necessary to inspect a specific image pair. M2's learned rule uses the resulting
abstract facts; it does not bake those object names or values into its policy.

For example, a style-related branch uses the requirement that a recognizable
counterpart is sufficient. Its two supporting instructions ask for cubist art
and Matisse-like art. Neither artist/style name appears in the learned rule.
This demonstrates reuse of the predicate, not proof that the branch is correct
for every artistic transformation.

## Fitting and semantic review

The fixed whitelist contains 894 Boolean predicates. It excludes raw check-count
and majority features, including versions attached to semantic requirements.
An instruction-kind flag means that an operation is requested; it is not a
threshold on the number of questions the compiler happened to generate.

Candidate trees are selected using fitting accuracy and complexity, without
using held-out scores. The accepted floor is strictly above 90% across all 48
rows, including missing evidence. Stronger minimum source support is preferred
when it meets that floor, followed by fewer nodes and shallower depth.

| Preserved artifact | Local fit | Terminal rules | Purpose |
|---|---:|---:|---|
| Deeper portable fit | 47/48 | 19 | Fitting-capacity diagnostic; not the recommended reviewed policy |
| Compact portable fit | 46/48 | 15 | Selected fit before semantic review |
| **Reviewed deployment policy** | **44/48** | **14** | Recommended rule-level portable artifact |

The review found one explicit contradiction: a branch predicted Yes while its
written conditions asserted that every requirement had a missing core endpoint.
A spatial/non-spatial subtype split was supplying a Yes exception for two fitting
examples. The generic review procedure collapsed that exception into a shared
parent rule while preserving the accepted accuracy floor. It does not use case
names or object names to select the pruning action.

This is training-time pruning of a contradictory written branch. It does not
reinstate the earlier universal requirement that every M1 check pass before Yes
is allowed. Unknowns and instruction-dependent exceptions remain available to
the learner. The review also does not prove that every remaining learned
correlation is causally valid or that all possible inconsistent inputs are
handled correctly.

The final mismatches are G1C09 (bench/pew), G3C12 (pet-store background), and
G4C03 (wooden table), plus the missing G3C05 observation. In the first two, the
available semantic descriptions assert a core endpoint shortfall despite a Yes
reference. The reviewed policy leaves these as errors instead of retaining the
contradictory Yes exception. This does not establish whether the observation,
interpretation, or reference is responsible for the disagreement.

## Current inference path

1. M1 compiles the instruction into bound physical checks.
2. M1 observes the SOURCE/EDITED pair once and answers those checks.
3. One text-only pass interprets the cached physical evidence relative to the
   instruction: progress, endpoint gaps, retention needs, identity materiality,
   collateral materiality, and evidence consistency. It receives no reference
   labels or prior satisfaction judgments.
4. Code projects the facts into the portable vocabulary and executes the frozen
   semantic rule tree to return No, Partial, Yes, or Unresolved.

All model stages use the same GPT-6.1 Sol/high profile. A fresh case currently
requires the two M1 calls plus one additional text-only interpretation call.
Rule execution itself makes no model call. A missing required interpretation
is unresolved; valid interpretations containing uncertain facts can still be
used by the learned policy.

The current goal used 59 explicitly authorized text-only calls: 47 observed
training cases and twelve supplementary development cases. All completed with
valid bound outputs. No images were resent. The original failed M1 observation
was not retried, and the final fifty cases remain reserved.

## Verification

- **147 scoped tests pass**, including the prior M0–M4 protections and new
  interpretation, portability, semantic-review, and runtime tests.
- An independent audit recomputes all 48 predictions and checks every rule's
  source support, distinct-instruction support, predicate whitelist, and absence
  of explicit written semantic contradictions.
- Reversing the training row order and replacing every source and original-batch
  identifier produces an identical deployment artifact after fitting and review.
- **515 equivalent-check probes across 59 observed cases produce zero feature,
  prediction, or trace changes.** These reorder/rename local check identifiers or
  repeat an identical bound check, while holding the semantic interpretation
  fixed. They test rule-level portability, not LLM re-extraction or paraphrases.
- All raw-call payloads, fixed model identities, official endpoint hosts, binding
  references, and one-attempt budgets were checked. No reference labels or images
  were included in interpretation requests.
- Training/review/runtime replay is offline. Earlier experiment artifacts and
  the M0 final-test reservation are preserved.

## Statistical accuracy remains a separate question

Before the user's clarification, this goal explored held-out performance. Those
results are retained, not promoted or hidden. A physical-only nested selector
scored 21/48; the interpretation-based nested selector scored 18/48. A scoped
candidate retained 44/48 locally and scored 25/48 on held-out training groups,
but then scored only 7/12 on a frozen supplementary check versus v4's 9/12.

V8 was selected for reusable rule language and local fit under the clarified
objective. It is not claimed to fix those statistical transfer limitations.
Only 48 training sources support these conditions; five of the fourteen reviewed
rules have two examples each. Larger-corpus accuracy, robustness to genuinely
different decompositions, and repeated/paraphrased model calls remain untested.

## Artifacts and reproduction

Use the **deployment policy** for execution. The unreviewed fits remain available
for comparison and should not be confused with the reviewed recommendation.

- [Deployment-only policy](../logs/exps/261014-m2-portable-semantic-v8/deployment_policy.json)
- [Readable reviewed rules](../logs/exps/261014-m2-portable-semantic-v8/reviewed_rules.txt)
- [Reviewed training artifact](../logs/exps/261014-m2-portable-semantic-v8/reviewed_policy.json)
- [Reviewed scores and case predictions](../logs/exps/261014-m2-portable-semantic-v8/reviewed_result.json)
- [Portability audit](../logs/exps/261014-m2-portable-semantic-v8/portability_audit.json)
- [Equivalent-check audit](../logs/exps/261014-m2-portable-semantic-v8/equivalent_check_audit.json)
- [Rule support examples](../logs/exps/261014-m2-portable-semantic-v8/rule_support_examples.json)
- [Model-call audit](../logs/exps/261014-m2-portable-semantic-v8/live_call_audit.json)

```bash
.venv/bin/python -m run.calitree_m2_portable_v8 --replay --output-dir logs/exps/261014-m2-portable-semantic-v8
.venv/bin/python -m run.calitree_m2_portable_review_v8 --output-dir logs/exps/261014-m2-portable-semantic-v8
.venv/bin/python -m run.audit_m2_portability_v8 --output-dir logs/exps/261014-m2-portable-semantic-v8
```

Library inference uses `PortableRuleExecutor` with a record from
`portable_features_v8.project(program, observation, pair_ref, interpretation)`.
The generic fitter/runtime do not require any particular case, object, image,
or original training-batch identifier. No global default pipeline or M5 merging
implementation was changed by this experiment.
