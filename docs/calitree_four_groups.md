# Four independent twelve-case local fits

The experiment freezes four nonoverlapping AURORA groups of twelve cases, each
with four No, four Partial and four Yes references. Sources are distinct across
all 48 cases and exclude the preceding 36, original twelve, earlier listed fits,
separate calibration thirty-six and reserved fifty-case holdout. Sampling uses
official test tasks, AURORA-editor outputs only, category spreading and fixed
hash ties, without predictions or fit outcomes.

Each case receives one flat baseline judgment and one label-blind rich-evidence
response, using the unchanged GPT-6.1 Sol/high settings and SOURCE-first images.
There are at most 96 one-attempt calls, with eight API workers and no retries or
repeat voting. Extraction payloads contain instruction/images only.

After collection, v4 macro-F1 calibration fits separately on each group's own
twelve labels and scores that same group. No pooling or cross-group feedback
occurs. Objective, predicates, depth-two/three-split/minimum-two-source limits,
monotonicity and uncertainty handling stay fixed.

The two-correct-source-per-class gate means at least 50% fitting recall per class
on a twelve-case group. If no candidate qualifies, the group is reported as
infeasible: no resampling, weakened gate or class-collapsed fallback. Reports show
fit feasibility and conditional successful-group averages separately. Failed
groups remain abstentions in an explicitly named all-48 end-to-end score.

```sh
.venv/bin/python -m run.calitree_four_groups --preflight \
  --output-dir logs/exps/NEW-FOUR-GROUPS
.venv/bin/python -u -m run.calitree_four_groups --live \
  --output-dir logs/exps/NEW-FOUR-GROUPS
.venv/bin/python -m run.calitree_four_groups --replay \
  --output-dir logs/exps/NEW-FOUR-GROUPS
```

Preflight freezes membership, code, prompts/schema and fitting constraints before
model calls. Every arm/case has an independent durable one-attempt ledger. Replay
reuses observations, exactly refits each group and reproduces all results without
new model calls. The report retains transport failures and uncertain decisions.

This measures local fitting consistency across four batches, not generalization
or repeat robustness. Human labels remain aggregate-mean classes with 0.5/1.5
cutoffs, and historical project usage of other examples may remain.
