# Router-free M5–M7: successful union merges and child-rule reuse

**Date:** October 15, 2026. **Status:** implemented, fitted, and independently
audited on the same 48 AURORA training sources. M4 is skipped. The selected
semantic hierarchy merges eight six-case groups into one 48-case policy and
scores **46/48 (95.8%)** locally with fourteen rules.

The final root uses only predicates inherited from its two immediate children.
It is one executable semantic decision tree; inference needs no batch identity,
applicability scope, specialist router, child vote, or training membership lookup.

## What changed

The earlier v9 experiment fitted a parent on 24 cases and then let an overly
broad scope send unrelated cases to it. Its fitting success could therefore
damage the complete system. This experiment evaluates a proposed parent only
on the complete deduplicated union of the children it is replacing. Smaller
parents remain training artifacts. A policy is exported for general inference
only after its lineage covers all 48 training sources.

The original editing-model category, released mean-derived labels, cached
physical observations, cached semantic interpretations, and fixed judge model
are unchanged. No example was relabeled, dropped, duplicated, or retried. One
missing observation stays unresolved. There were zero new API calls, and the
reserved final fifty remain unevaluated.

## Results

| Configuration | Complete root | Local accuracy | Rules | Separate development |
|---|---|---:|---:|---:|
| Previous reviewed pooled M2 | One pooled policy | 44/48, 91.7% | 14 | 9/12 |
| Router-free full-grammar refit control | Original four groups, three selected merges | 47/48, 97.9% | 19 | 7/12 |
| **Selected reuse-first merge** | **Eight semantic groups, seven selected merges** | **46/48, 95.8%** | **14** | **10/12** |

The control demonstrates fitting capacity. The selected method instead prefers
a qualified root that recombines its children's predicates. Its 10/12 score was
computed after freezing the training-only selection. These twelve sources have
historical project exposure and remain a small development diagnostic. They do
not establish improved statistical transfer or repeated-model robustness.

The root recalls are No 16/16, Partial 15/16, and Yes 15/16. G3C05 remains
unresolved because its original observation is missing; G3C09 is a Yes-reference
case predicted Partial. The two development disagreements are H01 and H07:
both have No references and are predicted Partial.

## Smaller groups: which approach worked?

Three partitions use the exact same 48 sources:

1. **Original:** four twelve-case groups.
2. **Balanced halves:** split each original group into two six-case groups,
   maintaining two examples per class in every seed.
3. **Semantic:** eight six-case clusters formed from reusable instruction kinds,
   progress, endpoint gaps, identity/materiality context, and physical-state
   summaries. Reference labels are unavailable to this grouping function.

The semantic grouping uses fixed weighted distances, farthest-first centers,
capacity-constrained assignment, and improving swaps. Every group has six
distinct sources. Labels are inspected afterward for reporting; there is no
downsampling or requirement that each semantic group be class-balanced.

| Partition and learner | Highest-fitting retained root | Preferred reuse root | Selected merges to that root |
|---|---:|---:|---:|
| Original four, post-fit semantic review | 47/48 | Not a reuse-first run | 3 |
| Original four, constraints inside search | 47/48 | Not a reuse-first run | 3 |
| Balanced halves, full grammar | No complete qualifying hierarchy | — | — |
| Semantic eight, full grammar | 47/48 | Not a reuse-first run | 7 |
| Original four, reuse first | 46/48 | 45/48, child-only root | 3 |
| Balanced halves, reuse first | No complete qualifying hierarchy | — | — |
| **Semantic eight, reuse first** | **47/48 with full-grammar root repair** | **46/48, child-only root** | **7** |

Simply increasing the number of groups was insufficient under the tested
balanced-depth search and retention gates. Grouping related evidence states
provided a successful smaller-group hierarchy. The search is bounded and keeps
two policy alternatives per union; the failed balanced-halves runs do not prove
that every possible hierarchy for that partition is impossible.

Six-case seed policies are initialization candidates, not validated specialists.
Some seed labels have only one example, and some seeds fit only 4–5/6. They are
never deployed on other cases. Every accepted parent, starting at twelve cases,
must meet the explicit union-quality and retention gates.

## How a parent learns

The first v10 control retrains from the entire grammar on each union, with
relabeled child trees as alternatives. Its selected path uses fresh fits rather
than reused child conditions. V11 tests stronger structural reuse:

1. Collect the Boolean predicates actually used by the two child policies.
2. Relearn their interactions on the complete original-label union. Also evaluate
   each child tree after relabeling its terminal regions from that union.
3. If no candidate passes, add one generic evidence predicate at a time, up to
   four, ranked from errors inside that union. Relearn the restricted tree.
4. If that still fails, allow a clearly marked full-grammar repair. Original
   reference labels remain the targets throughout; child answers are never
   substituted as ground truth.

A full-grammar repair searches the existing cached-predicate vocabulary. It
does not reobserve images, alter the cached evidence, or make a model call.

The fitter also excludes explicitly contradictory written Yes branches during
search, such as a path asserting no requested progress and then predicting Yes.
It retains the existing M2 meaning of this review: it is a written-path
consistency check, not a universal rule that every physical check must pass.
The post-fit-review control is preserved to separate this change from removing M4.

A shared parent can keep different conditions for different instructions. The
method does not require every terminal rule to span both children. Every rule
needs at least two distinct sources and instruction texts, and shared-rule
support is separately measured. All conditions remain within the closed M2
vocabulary: no case IDs, exact instructions, object names, pixel coordinates,
raw check counts, majority thresholds, or observed-case signature lookup.

## Acceptance and iteration

Every accepted parent must:

- Contain the exact deduplicated union of all descendant sources, including
  extraction failures and previous errors.
- Score strictly above 90% over that entire union.
- Avoid zero recall for a reference label represented by at least two sources.
- Lose at most `max(1, floor(child_size / 10))` correct answers on either
  immediate child's fitting cohort.
- Preserve the source/instruction support and written semantic-consistency
  constraints.

M5 ranks child pairs using predicate/operation overlap and measured mutual
transfer on each other's fitting sets. Common mistakes are recorded separately.
M6 fits and checks the parent. M7 explores balanced binary training hierarchies,
retaining up to two distinct policies per union. The declared limits are eight
initial groups, hierarchy depth three, and 1,536 evaluated child pairs per run.
Training-set membership masks belong only to this bounded scheduler; they are
absent from the exported judge.

The selected construction is:

```text
8 groups × 6 cases
    → 4 parents × 12 cases
    → 2 parents × 24 cases
    → 1 root × 48 cases
```

| Selected merge | Union fit | Learning mode |
|---|---:|---|
| First 12-case parent | 11/12 | Full-grammar repair |
| Second 12-case parent | 11/12 | Child predicates plus bounded refinement |
| First 24-case parent | 24/24 | Full-grammar repair |
| Third 12-case parent | 11/12 | Full-grammar repair |
| Fourth 12-case parent | 11/12 | Full-grammar repair |
| Second 24-case parent | 23/24 | Full-grammar repair |
| **48-case root** | **46/48** | **Child predicates only** |

This is an important limitation: five of the seven lower-level merges needed
full-grammar repair. The experiment proves successful supervised consolidation
and a genuinely reused final predicate vocabulary, not uniform transfer of all
small-seed rules.

The final merge takes children scoring 24/24 and 23/24 and retains 46/48. The
first child's score becomes 23/24; the second stays 23/24. That one-case loss
passes the predeclared retention allowance. The root reduces their combined
nineteen terminal rules to fourteen and their 36 policy nodes to 27. Ten root
terminal rules have examples from both immediate children. Its eleven used
predicates are a subset of the sixteen predicates available from those children.

## Inference

The [frozen package](../examples/calitree_union_reuse_v11/manifest.json) contains
one policy, the upstream prompt/schema contracts, model profile, and hashes.
Training lineages, source IDs, grouping assignments, and labels are separate.

A fresh case uses the existing M1 compilation, M1 image observation, and one
text-only semantic interpretation, all with GPT-6.1 Sol/high and one SOURCE-first
presentation. The frozen policy then executes deterministically. There is no M4
selection and no model call at a merge node.

```python
from critical.core.calibration.semantic_hierarchy.union_runtime_v11 import load

judge = load("examples/calitree_union_reuse_v11")
decision = judge.predict_bound(program, observation, image_pair_ref, interpretation)
```

```bash
.venv/bin/python -m run.calitree_union_predict \
  --package examples/calitree_union_reuse_v11 --evidence /path/to/bound_evidence.json
```

## Verification and limits

The complete CaliTree suite passes **969 tests**, with 23 skipped. Fifteen new
tests cover no-M4 operation, fitting/restore at 12/24/48/96 rows, source retention,
child-rule reuse, outside-union warm-start rejection, child-retention regression,
shared concurrent caches, inference isolation, package integrity, and the
training-only preference for a qualifying reused root over a more accurate cold root.

Independent audits reconstruct all registered model predictions and source
lineages, original-reference fitting contracts, semantic rule support, parent
gates, cross-transfer cells, selected merge order, and final root selection.
The selected semantic-eight run replays exactly with zero new solver fits.
Across 59 observed training/development sources, 515 exact check duplication,
identifier, and order changes preserve features, predictions, and traces while
cached semantic interpretations are held fixed.

These checks do not prove that every learned association has the correct causal
meaning. Minimum two-case support is small, the vocabulary and observations
remain model-generated, and fitting accuracy is not transfer accuracy. The
development gain from 9/12 to 10/12 is descriptive; the cohorts have historical
exposure and the search budgets differ. The final fifty are reserved for a
separate frozen evaluation. No global default pipeline was changed.

The v10 cold-refit controls are under
`logs/exps/261015-union-merging-v10/`; the reuse-first study and its selected
lineage are under `logs/exps/261015-union-reuse-v11/`. Reproduce with:

```bash
.venv/bin/python -m run.calitree_union_reuse --run semantic8_reuse --replay \
  --output-dir logs/exps/261015-union-reuse-v11
.venv/bin/python -m run.audit_calitree_union_merge \
  --output-dir logs/exps/261015-union-reuse-v11
.venv/bin/python -m run.audit_calitree_union_invariance \
  --output-dir logs/exps/261015-union-reuse-v11
.venv/bin/python -m pytest tests/unit/calitree -q
```

Cached replay repeats deterministic proposal scoring and terminal relabeling;
it performs no new cold/restricted solver fits or model calls. Production
inference performs neither fitting nor proposal scoring.
