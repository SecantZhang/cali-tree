# Combined versus separately executed visual checks

This experiment tests whether splitting the same visual criteria into independent
model calls improves repeat consistency. It does not run another optimizer search:
changing both the criteria and their execution would confound that question.

## Frozen protocol

Reuse the twelve prior AURORA cases and their original label-free seed programs,
with the exact image hashes and four cases per class. These cases have been observed
before. Compile a shared bank of two or three independently assessable visual facts
for each case, plus decision criteria for every original requested outcome. A
separate label-blind audit checks atomicity, semantic preservation and sufficient
coverage. Freeze every bank and audit before executing either arm. At most one label-blind semantic repair proposal may address a rejected bank
before freezing; unchanged proposals reuse their original audit. There is no
label-guided rule selection or retry of a failed HTTP slot. Rejected or unrepresentable
banks are recorded as unresolved, without truncating requirements.

Both arms use the exact same fact and outcome criteria:

- **Combined:** one image call returns every fact observation and the requested
  outcome judgments together.
- **Separated:** one independent image call per fact, followed by one text-only
  fulfillment call using those observations and the shared decision criteria.

Facts use present/absent/unknown. Fulfillment uses complete/partial/absent/unknown.
Negative facts are usable evidence. Required unknown facts block their dependent
outcomes in both arms, even if the model emits a confident fulfillment judgment.
Applicable requested outcomes aggregate as all complete → yes, all absent → no,
otherwise known progress → partial. Unknown applicability, required unknowns or an
empty applicable outcome set remain unresolved. Facts never count as extra edits.

Run five fresh repeats of each arm per case. Alternate arm order by case and repeat;
use independent durable slots without cross-arm observation reuse. Reference labels
are used only by reporting, never compilation, audit, visual checks or fulfillment.

## Metrics and interpretation

The primary measure is mean case-level pairwise label inconsistency over the ten
pairs among five draws. Any pair containing an unresolved label counts as
inconsistent, including two unresolved labels. This avoids calling repeated failure
stable. Also report disagreement conditional on two resolved labels, reference-label
agreement with unresolved draws counted incorrect, coverage, five-of-five matching
cases, five-of-five resolved-consistent cases, rule-level inconsistency, calls and
measured tokens. Atomic consistency does not establish atomic correctness.

The exact two-sided paired sign-flip calculation uses one difference per eligible
case, not one difference per draw. It is an exploratory diagnostic on at most twelve
cases. Full-cohort metrics retain preparation failures as unresolved; the paired
execution-effect calculation excludes cases without an approved bank.

Separation changes context isolation, visible intermediate evidence and the number
of calls. The fulfillment call deliberately cannot re-inspect the images. Therefore
this measures the complete execution-format change, not prompt length alone. Equal
criteria do not mean equal inference cost; separated calls cost more. A result on
these previously observed cases cannot establish cross-case generalization.

## Budget and durability

Use GPT-6 Luna throughout, temperature zero and reasoning none. The approved ceiling
is 400 calls and 409,600 completion tokens. The amended planned maximum is 348 calls and
405,504 completion tokens: 12 compilations plus 12 audits, and at most 12 semantic
repairs plus 12 further audits, all at up to 2,048 tokens each,
and 300 execution calls at up to 1,024 tokens each. Reserve the full execution
allowance before preparation. Each separated case uses at most 20 execution calls,
within the existing runtime's 24-call final allowance.

One HTTP attempt per durable slot; failed and interrupted calls remain charged and
are never resampled. A provider rejection or three consecutive transport failures
stops the run without substitution. Save source snapshots, exact banks, audits,
individual observations, responses, predictions and usage. Frozen implementation
or image changes prevent live resume. Reporting does not contact the provider.

```sh
.venv/bin/python -m run.calitree_check_ablation --preflight --output-dir RUN_DIRECTORY
.venv/bin/python -m run.calitree_check_ablation --live --resume --output-dir RUN_DIRECTORY
.venv/bin/python -m run.calitree_check_ablation --report --output-dir RUN_DIRECTORY
.venv/bin/python -m pytest -q tests/unit/calitree/test_check_ablation.py
```

The bounded repair was added before any live evaluation after all initial banks
failed preparation. Earlier attempts and source snapshots are preserved in
`261006-check-ablation-v1` and `v2`; `v3` carries their exact durable slots and costs
forward. An empty explanatory reason field parser defect was also fixed before any
evaluation; no compiler response was regenerated to fix it.

Results and limitations: [paired experiment report](experiments/calitree_check_ablation.md).
