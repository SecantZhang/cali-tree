# Fifty-case GEPA robustness comparison

## Question

On a larger set of image-edit judgments, does repeated-evaluation GEPA repair
produce prompts with higher repeated correctness than single-draw GEPA repair?

## Frozen protocol

- Select 50 distinct AURORA test-split source tasks from the prior 100-case
  repair experiment's clean holdout. Balance the aggregate human labels at
  17 `no`, 17 `partial`, and 16 `yes`; spread selection across eight source
  categories and five editing models. The selection seed is 44. These cases
  are new to the earlier repair sample, but their labels enter this experiment's
  optimization feedback, so final evaluation is in-sample for the optimizer.
- Start both arms from the same CaliTree v2 initial rubric. Use five GEPA 0.1.4
  mutation proposals per case and arm, current-best strategy, no merging or
  response caching, and no perfect-score skip.
- Single arm: one GPT-5.4-mini judgment per GEPA evaluation; accept only a
  strict observed correctness gain.
- Repeated arm: five independent judgments per GEPA evaluation; accept only a
  strict gain followed by strictly better correctness in ten fresh judgments
  each for candidate and incumbent. Ties keep the incumbent.
- Freeze all prompts, then obtain 15 fresh judgments per case and arm: exactly
  1,500 final judgments. Final responses cannot affect prompt selection.
- Judge: GPT-5.4-mini, reasoning `none`, temperature 0.3, maximum 512 tokens.
  Reflection: same model, temperature 0, maximum 4,096 tokens.
- Human labels are used only for local scoring and optimizer feedback; judge
  requests contain the rubric, instruction, and two images. Malformed completed
  judgments count as incorrect. Every call has a stage-specific identity and
  exact resume checkpoint. The estimated list-cost cap is $30.

The sample is class-balanced and is not a prevalence-weighted sample of AURORA.
One search trajectory per case and arm is exploratory; it cannot determine
optimizer reliability across seeds. If both arms end with the same prompt on a
case, their final draws are still distinct and any measured difference there is
sampling variation.

## Reproduction

```bash
PYTHONPATH=. .venv/bin/python run/robust_prompt_repair_50.py \
  --output-dir logs/exps/260924-50-case-15-repeat --dry-run
PYTHONPATH=. .venv/bin/python run/robust_prompt_repair_50_parallel.py \
  --output-dir logs/exps/260924-50-case-15-repeat --workers 3 --live
```

The run stores frozen case and code hashes, source/edited image hashes,
candidate diffs, decisions, raw API responses, usage, and final draws in
`logs/exps/260924-50-case-15-repeat`.

## Completed results

| Arm | Correct final draws | Accuracy | Pairwise disagreement | All 15 correct | Always wrong | Accepted edits | Completed calls | Estimated cost |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Single-draw GEPA | 475/750 | 63.3% | 13.1% | 24 | 7 | 21 | 1,772 | $2.692 |
| Repeated GEPA | 472/750 | 62.9% | 12.7% | 22 | 10 | 23 | 5,645 | $7.691 |

Repeated minus single accuracy was **-0.4 percentage points**. The descriptive
paired task-bootstrap 95% interval was **[-9.2, +8.8] points**. Pairwise
disagreement was 0.4 points lower under repeated repair, with a task-bootstrap
interval of **[-5.8, +4.8] points**. This run does not establish an accuracy or
stability advantage for repeated repair. The added calls bought more search
evidence and confirmation, but at these settings the final results were
essentially tied.

The same prompt was selected by both arms in 27/50 cases. Those cases happened
to score 285/405 in each arm using separate final calls. On the 23 cases where
the prompts differed, single-draw repair scored 190/345 and repeated repair
187/345. There were seven case-level gains, twelve losses, and 31 ties for the
repeated arm. Partial-label recall was low in both arms: 34.9% single, 27.8%
repeated. Large gains and losses on individual cases remain possible despite
the near-zero mean difference.

The completed run contained 500 decisions, 500 reflection calls, 5,417
search/confirmation judge calls, and 1,500 fresh final judge calls. Total
estimated list cost was **$10.383903**, below the $30 cap. An independent audit
verified the input hashes, prompt lineages, unique call and provider response
IDs, all 1,500 post-freeze final identities, target-free judge requests, and
the recomputed final scores. A TLS failure interrupted final evaluation once;
resumption reused only completed checkpoints.

[Full report](../../logs/exps/260924-50-case-15-repeat/report.md) ·
[Summary JSON](../../logs/exps/260924-50-case-15-repeat/summary.json) ·
[Verification record](../../logs/exps/260924-50-case-15-repeat/verification.json)
