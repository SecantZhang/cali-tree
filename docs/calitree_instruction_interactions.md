# Instruction-dependent interaction rules

The v7 prototype replaces additive score compensation with explicit conditional
gates. It is opt-in and does not change the existing judge or calibration default.

An instruction's label-blind contract determines whether original identity,
relations, count, attributes, and scope are required. The resulting label logic is:

1. No meaningful progress, a clearly wrong required original instance, or destroyed
   source meaning gives No.
2. Yes requires both progress and actual endpoint achievement, all activated
   fidelity checks, and applicable instruction-relative preservation to clear
   their boundaries. Every gate must pass; high scope cannot offset poor identity.
3. Meaningful progress with a material required shortfall gives Partial.
4. Unknown facts use lower/upper completions; prediction resolves only if both
   agree. A contract-required check incorrectly marked inapplicable is unknown.
   Missing model responses always abstain. No learned unknown-to-No shortcut is used.

The previous evidence grade scale already calls grade 2 a material shortfall and
grade 3 near-complete fulfillment. The sixteen candidate policies respect that
semantics: the meaningful-progress boundary is 1 or 2; outcome, required fidelity,
and preservation Yes boundaries are 3 or 4. Only four thresholds are fitted.
Optimization cannot delete a required gate or lower its Yes floor to fit a case.
It optimizes accuracy alongside macro-F1 and retains the existing two-correct-
sources-per-class floor. Unsupported fits raise an explicit error.

`critical/core/calibration/instruction_rules.py` subclasses `Calibrator`.
`instruction_record` strips all prose, IDs and labels, retaining only the fixed
instruction-contract flags and applicable/grade facts. Prediction accepts only
that whitelist. Artifacts retain thresholds, the exact rule contract, training
feature/target hashes, metrics, and all training-equivalent candidates. A fixed
default-biased tie-break chooses among them without evaluation labels.

## Validation

The experiment in `logs/exps/261014-instruction-interactions-v7/` reuses the exact
previous 48 cases and cached same-model evidence. It makes no new API calls.
Luna is primary; Sol and the previously quote-normalized mini cache are secondary.
Extraction and labels remain unchanged, isolating decision-rule changes.

The predeclared primary fit uses G1's twelve labels, freezes the rule, then scores
the other 36 cases without recalibration. All four reciprocal train-12/evaluate-36
folds and local diagonals are reported. The prior v6 rubric from the same training
group and the same-model flat judge are controls. A fixed unfitted semantic
policy is also reported separately; it never replaces an unsupported learned fit.

Results are negative for broad accuracy improvement. The fixed semantic rule
scores Luna 27/48, Sol 26/48, mini 21/48. Only two Luna groups, three Sol groups,
and two mini groups admit a fitted rule under the retained class-support floor.
The primary Luna/G1 fit is unsupported, so no successful primary fitted transfer
is claimed. Qualified Luna G2/G3 policies score 15/36 and 18/36 on other groups.
See `report.md` for all metrics, coverage, recalls and denominator treatment.

The gates catch the intended compensation failure by construction, but the
underlying evidence sometimes contradicts human labels: for example, Luna gives
required identity grade 1 to a human-Yes lamp relocation. A new gate faithfully
blocks Yes from that evidence. It cannot determine whether the extraction or
the averaged human reference better reflects the image. New evidence validation
is needed before this family should replace the current pipeline.

All groups have been inspected in earlier development. The cross-group tests
withhold labels from each fit, but they are retrospective rather than a pristine
untouched benchmark. Reciprocal folds reuse cases and are not independent samples.

Reproduce without API calls:

```bash
.venv/bin/python -m run.calitree_instruction_rules --replay --output-dir logs/exps/261014-instruction-interactions-v7
.venv/bin/python -m run.report_calitree_instruction_rules --output-dir logs/exps/261014-instruction-interactions-v7
.venv/bin/python -m pytest tests/unit/calitree/test_instruction_rules.py tests/unit/calitree/test_instruction_interactions_properties.py -q
```

The independent audit checks training-only feature/target hashes, frozen policy
identity before/after evaluation, disjoint sources in all cross-group cells,
direct scalar interaction predictions, all 192 metric sets, failure handling,
and exact replay. The full CaliTree suite passes 704 tests with 23 skipped.
