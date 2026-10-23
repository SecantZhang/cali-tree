# Semantic profiles for pairwise merge scheduling

The v25 experiment adds an opt-in semantic ordering of merge candidates. It leaves
parent induction, child accuracy floors, proposal selection, coverage rebuilding,
and inference unchanged. Frozen v24 files and artifacts remain immutable.

## Profiles and ordering

For each expert, the scheduler collects compiled outcome kind/expected-state
pairs on correctly predicted examples within that expert's original local scope.
These counts become a normalized task distribution. A second profile records
predicate families in the first two tree levels, weighting the root twice as much
as a child and combining `all`/`any` aliases. Availability/requirement boilerplate
is excluded from that predicate profile.

Pairs are ordered lexicographically by:

1. Higher weighted Jaccard overlap between supported task distributions.
2. Higher prediction agreement on the child union's examples with shared task kinds.
3. Higher weighted Jaccard overlap between shallow predicate profiles.
4. Artifact ID for deterministic ties.

Profiles are recomputed after accepted merges. Every pair remains eligible; no
semantic threshold deletes a candidate. Batch/source IDs only recover training
scope; their names are not profile dimensions. Original reference labels are used
only to identify correct local support, not to score development cases. Pair
ranking never receives the coverage regression probes. These profiles are offline
scheduling metadata and are not an inference router or a new specialist tree.

## Controlled comparison

The protocol fixes 4, 8, and 24 fit budgets per split before execution, with four
as the primary comparison. Each budget is run with both artifact-ID order and
semantic order across all three splits, starting from the same frozen v23 banks.
Both use the v24 fitter, two quantifier variants per pair, at most three rounds,
and the existing exact child-accuracy and routing checks.

A fit is one quantifier-specific parent-search invocation, including searches that
hit their state cap or prove infeasibility. Exact repeated fit keys within an arm
are free, matching v24. Identical computations across arms are physically memoized,
but each arm has a separate logical budget. Reported fit/state counts therefore
represent independent searches; memoized runtime is not reported as a speedup.
Existing union experts may still be considered after the fit budget is exhausted,
matching the control's behavior. Ordering alone cannot save fits in a complete
all-pairs round; any advantage must come from selecting useful work earlier under
a bounded budget.

## Reproduction

```bash
PYTHONPATH=. python run/compare_calitree_semantic_merge_v25.py \
  --previous-run logs/exps/261019-counterexample-coverage-v23 \
  --output-dir logs/exps/261019-semantic-merge-v25
PYTHONPATH=. python run/verify_calitree_semantic_merge_v25.py \
  --output-dir logs/exps/261019-semantic-merge-v25
```

Use a fresh output directory. The standalone runner
`run/calitree_semantic_merge_v25.py` also exposes `--ordering semantic|artifact_id`
and `--fit-budget`. No live API calls or final-set access are involved.

## Interpretation

Treat the profiles as a search heuristic. Supported task-family similarity need
not imply compatible decision boundaries. In split 2, the semantic ordering
places a pair with task overlap 0.655 and prediction agreement 0.419 ahead of the
successful pair (overlap 0.638, agreement 0.750). Artifact-ID order happens to
visit the successful pair first. Thus semantic similarity alone is not yet a
reliable proxy for mergeability, especially for mixed-task batch experts.

A follow-up could test a joint task/behavior score or profiles of smaller
supported rule regions. That would be a new development experiment; the current
ranking was not retuned after seeing this comparison. Neither ordering guarantees
a global optimum under a limited budget. Accuracy preservation here concerns the
same cached local evidence; the regression probes remain known development data.

## Results

All six arms finish with the same expert bank and gates: 9 experts, 56 terminal
rules and 1,256 stored conditions across the three alternative splits, down from
10 experts, 59 rules and 1,290 conditions. Only split 2 merges; its rules fall
22→19 and shared correct support remains 17.

| Fit cap per split | Ordering | Actual fits, all splits | Search states | Coverage rebuilds | Final rules |
|---:|---|---:|---:|---:|---:|
| 4 | artifact_id | 10 | 506,188 | 5 | 56 |
| 4 | semantic | 10 | 499,951 | 3 | 56 |
| 8 | artifact_id | 18 | 655,385 | 5 | 56 |
| 8 | semantic | 18 | 638,193 | 5 | 56 |
| 24 | artifact_id | 30 | 1,074,817 | 5 | 56 |
| 24 | semantic | 30 | 1,074,817 | 5 | 56 |

There is **no fit-count advantage from semantic ordering** in this study. At the
primary budget it saves two coverage rebuilds (5→3) and 1.2% of search states; at
the eight-fit budget it saves 2.6% of states. The full-budget searches perform
identical work. Both four-fit arms recover the earlier full-search result with
10 rather than 30 total fits, so that 67% reduction is a budget result shared by
the control, not evidence for the semantic heuristic.

Every arm preserves all 144 local predictions (12 original batches at 12/12),
all 294 recorded accept/defer and final-label decisions, and all 112 exact regular
fallbacks. Development accuracy remains 116/150. No inference router, default
pipeline, model prompts, or final-set access changed.

The comparison makes 116 logical fit requests. Cross-arm memoization evaluates
30 unique requests and reuses 86, without changing any arm's charged fit budget.
The artifact-ID full-budget control exactly reproduces v24's prior accepted
parent, expert bank, final gate, complexity, work counts and routing checks.

## Verification

All 89 focused unit/regression tests pass. The independent audit verifies all
18 split runs across six arms: 24 pair schedules, 116 logical fit requests,
1,764 recorded final routing decisions, and each accepted parent's local
retention constraints. It rebuilds candidate coverage, replays raw cached local
inputs and exact regular fallbacks, refits accepted learned parents, and verifies
the full-budget control against the sealed v24 result. The study is sealed under
`logs/exps/261019-semantic-merge-v25/completion_seal.json`. Compact measurements
and the audit are in `docs/experiments/calitree_semantic_merge_v25.json` and
`docs/experiments/calitree_semantic_merge_completion_audit.json`.
