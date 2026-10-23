# Guarded semantic policy development after the rejected-case diagnosis

The [rejected-case diagnosis](calitree_rejection_diagnostics.md) found unsupported
Yes shortcuts, correct experts losing an unconditional vote, and concrete
upstream grounding errors. This development targets the first two problems.
It does not repair or regenerate the cached evidence.

## Policy and merge changes

- **v32: conditional verdict verification and guarded merges.** Learn up to
  eight one/two-literal Boolean clauses per verdict, using declared task and
  evidence predicates. Retain every correct protected local/previous route.
  Merging must symbolically preserve goal, outcome, materiality and uncertainty
  distinctions separately for each task scope. It must also retain each child's
  local support and introduce no new false acceptance on fitting data.
- **v33: affirmative outcome warrants.** A new Yes requires positive completion,
  coherent observations, established physical outcomes and acceptable materiality.
  A new No requires affirmative failed-outcome evidence. A matching expert and
  source-supported calibration are also required. This experiment increased
  coverage but did not improve every bank, so it is retained as a control.
- **v34: conditional corrections to the regular judge.** On deferral, a matching
  expert may override the regular prediction in a short evidence region with
  at least two beneficial source groups and no observed fitting errors. This
  recovered some missed No cases but also mistook some Partial cases for No.
- **v35: regular-aware verification.** Add the regular judge's predicted label
  as a typed feature to the verdict verifier. For a new No overriding Partial,
  additionally require explicit incidental change or wrong target/direction;
  absent progress alone is insufficient. Human references are fitting/scoring
  data only; inference receives evidence and model predictions.

The models remain optional. The new `RegularAwareJudge` reuses the bound evidence
cache and keeps the regular response and execution reference separately from a
deterministic policy decision. It always obtains one regular judgment, including
on covered cases. This has a different cost profile from the original gate,
which could skip that call. No per-node or per-expert model calls are added.

## Source-held-out pilot results

For each of 16 sources, all five sibling outputs were excluded from fitting its
verifier, merge rules and correction regions. The old local data and previous
correct development routes remain protected. The pilot had already been reviewed
when these designs were chosen: these are exploratory procedure checks, not a
blind estimate of future performance. All three banks are reported separately.

Correct outputs out of 80, including the original failures:

| System | Bank 1 | Bank 2 | Bank 3 |
|---|---:|---:|---:|
| Regular judge | 53 | 53 | 53 |
| v27 | 57 | 50 | 50 |
| v28 | 56 | 50 | 47 |
| v32 guarded merge | 57 | 53 | 52 |
| v33 outcome warrants | 57 | 53 | 51 |
| v34 conditional correction | 58 | 56 | 51 |
| v35 verification only | 57 | 53 | 56 |
| v35 verification and correction | **59** | **57** | **56** |

The final v35 arm makes 19/14/17 tree decisions, of which 16/13/14 are correct
(84.2%/92.9%/82.4%). Against regular, it has 8 wins/2 losses, 4/0 and 3/0;
against v27, 3/1, 7/0 and 7/1. It preserves local accuracy and coverage rather
than claiming that all original transfer acceptances were safe.

Class balance matters: 60/80 references are No, so always predicting No scores
75% accuracy. The final v35 banks have macro F1 0.570/0.568/0.567, versus regular
0.535 and always-No approximately 0.286. Bank 1's accuracy improvement over v27
comes with lower Partial recall (4/15 versus 5/15) and slightly lower macro F1
(0.5704 versus 0.5714). Accuracy gains alone do not resolve the remaining
Partial/No boundary problem.

Full fitted v32 merges reduce 63 region definitions to 61, compared with v28's
44. Only two merges satisfy the new preservation constraints. Greater
compression is not yet justified by a safe relaxation of semantic obligations.

## Verification and next evaluation

`verify_calitree_guarded_development_v35.py` independently refits all 48
source/bank v35 models and the corresponding v34 routers, then replays frozen
predictions. The completed audit checks 2,304 local routes, 2,864 previously
correct route instances, 480 held-source predictions, and 32 accepted merge
proofs across the folds. Local accuracy/coverage and previous correct routes
are retained. Twenty-one focused unit tests pass. No new model calls were made.
The broader CaliTree suite reports 1,217 passed, 40 skipped and eight failures:
four need the missing worktree GEPA interpreter and four need historical
experiment/image assets absent from this checkout. These are environment
limitations in existing tests; the full suite is not reported as passing.

The final policies and source hashes are frozen for 36 cached legacy AURORA
cases excluded from all fitting of these fixes. They have older research
exposure and are not globally untouched examples. The regular baseline on those
36 cases is pending paid-call approval: at most 36 requests and 73,728 completion
tokens, no retries or new extraction. Supplemental v35 comparisons use those
same regular responses and require no additional requests. Full matched
forward accuracy is not available yet.

Artifacts:

- `logs/exps/261020-guarded-generalization-v32-r1`
- `logs/exps/261020-decision-warrants-v33-r1`
- `logs/exps/261020-fallback-routing-v34`
- `logs/exps/261020-regular-aware-v35`
- `logs/exps/261020-guarded-development-audit-v35`
- `logs/exps/261020-guarded-forward-v32-r1/supplemental_v35`

Earlier setup/prototype directories are retained with their code snapshots.
They are not substituted for the final versioned results above.
