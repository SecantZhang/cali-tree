# M0 complete: reserved fifty-case AURORA protocol

**Date:** October 14, 2026\
**Status:** M0 preparation and verification complete. M1–M4 were subsequently implemented and audited as experimental components; M5 and later milestones remain future work. The final reservation remains unevaluated.\
**Reservation:** `logs/exps/261014-semantic-hierarchy-m0-fifty-v1/`

## What is ready

| Partition | Cases | Label composition | Purpose |
|---|---:|---|---|
| Training | 48 | 16 No / 16 Partial / 16 Yes | Fit local and pooled candidates |
| Development validation | 12 | 4 No / 4 Partial / 4 Yes | Already-observed diagnostics and development selection |
| Reserved final test | 50 | 17 No / 17 Partial / 16 Yes | Future frozen hierarchy comparison |

All 110 cases have distinct decoded source-image identities across the three
partitions. The final fifty also exclude the 144 earlier recorded excluded or
reserved sources. They cover all eight task categories: six each from ag,
clevr, whatsup, magicbrush, epic, and something; seven each from emu and kubric.
Fifty is not divisible by three, so 17/17/16 is the predeclared near-balanced split.

The editing model remains the existing AURORA editor category. The planned
judge remains GPT-6.1 Sol/high. Labels retain the released-mean cutoffs:
`<0.5 → No`, `[0.5,1.5) → Partial`, and `≥1.5 → Yes`. They are not majority votes.

**No model calls, predictions, recalibration, or optimization were performed on
the reserved set.** M0 validates data and freezes the protocol; it does not
establish an accuracy result for the new hierarchy.

## Historical exposure and the approved scope

The audit examined 44,114 historical artifacts under `logs/exps`,
`.cache/calitree-tests`, `docs/experiments`, and the CaliTree JSON fixtures.
It indexes the release's 400 tasks and 394 distinct decoded source groups.
Exposure propagates across editor outputs and tasks sharing a source image.
Pure dataset catalogs, raw data nodes, unused-pool metadata, and asset layout
audits are distinguished from evaluation artifacts and development references.

After applying the existing study exclusions, the strict audit found only 13
candidate rows without mapped exposure references: nine No, four Partial, and
zero Yes. It could not provide a fresh, balanced fifty-case reservation.

The user explicitly chose **“Reserve 50 with historical exposure disclosed.”**
The finalized test is therefore **study-relative**, not globally untouched:

- 49 of its 50 cases have mapped historical project references.
- One has no mapped prior reference; this is not proof it was never observed.
- The audit retains 7,673 unresolved legacy alias records, including unrelated
  datasets and older artifacts that cannot be reliably attributed from aliases
  alone. It does not silently classify those records as proof of freshness.
- A historical reference is conservative context evidence, not necessarily a
  successful API call on that task. The ledger records its source artifact.
- Exposure outside the explicitly audited checkout is not covered.

This reservation can test transfer away from the new study's fitting and
selection cases. It cannot support a claim that the research process never saw
these examples. Reports must retain that limitation.

The strict failed preparation is preserved separately at
`logs/exps/261014-semantic-hierarchy-m0/`; it has no final-test seal.

## Frozen selection and comparison protocol

The prospective comparison arms are:

1. A strong flat judge.
2. One pooled semantic policy.
3. Local policies with actual inference routing and no merging.
4. The merged and recalibrated hierarchy.

The three semantic arms share one frozen extraction version. Macro-F1 is the
primary metric, accompanied by full-denominator accuracy, every label's recall,
coverage, confusion counts, paired differences, complexity, and inference cost.
Failures and unresolved results remain in the denominator.

Four source-grouped selection folds are defined within the 48 training cases.
Each fold has 36 fitting cases and 12 validation cases, with every source held
out once. The aggregate contains 16 references per label, sufficient for the
protocol's eight-per-label support gate. The separate twelve development cases
are supplementary diagnostics; their four references per label do not alone
justify a merge acceptance claim.

For each fold, local candidates, proposal ranking, parent fitting, and learned
routing must be rebuilt using only that fold's fitting sources. A child policy
trained on the held-out fold cannot be reused as a warm start. These are still
development estimates because all historical sixty development examples informed
the design of the representation.

The merge protocol freezes macro-F1 and Partial-recall non-regression, coverage
non-regression, bounded other-label/scope regressions, adequate support, and a
requirement for measured improvement or lossless complexity reduction. Full
parameters are in the sealed protocol files. These are prospective research
criteria, not evidence that merging already works.

## Prospective budgets

M0 itself has a zero-call budget. For one future validated two-stage extraction
version, the sealed plan allocates:

| Work | Maximum new calls |
|---|---:|
| Development extraction on 60 cases | 120 |
| Development flat baseline | 60 |
| Final extraction on 50 reserved cases | 100 |
| Final flat baseline | 50 |
| Total | 330 |

All semantic policy arms reuse the extraction records. Rule search, routing,
and parent fitting use no LLM calls in the primary plan. There are at most 24
unique parent proposals and five full build evaluations—four selection folds
plus final refitting—for at most 120 parent-fit evaluations. Maximum depth is
three, with at most two active initial candidates per batch.

These are future ceilings, not execution performed by M0. The two-stage
extractor is a later milestone. Substituting the current four-stage v16 path or
changing the schema requires an explicit protocol/budget revision. The future
completion-token ceiling is 5,406,720 at 16,384 tokens per call; actual use and
cache reuse must be reported.

## Artifacts and commands

The reservation contains:

- `study_protocol.json`: arms, model, labels, presentation, metrics, gates, and search limits.
- `selection_protocol.json`: source-grouped folds and the complete prospective budgets.
- `exposure_ledger.json`: source-level history and the hashed artifact inventory.
- `scope_decision.json`: the explicit historical-exposure decision.
- `splits/train.json`, `splits/validation.json`, `splits/test.json`: the three source-disjoint partitions.
- `test_inputs.json`: exactly fifty inference inputs without labels.
- `test_references.json`: references kept separately for the eventual scorer.
- `baseline_snapshot/`: original four policies, local/transfer results, and failure reports.
- `seal.json`, `completion_seal.json`: immutable reservation and completion hashes.
- `verification.json`, `completion_audit.json`, `preservation_audit.json`: independent checks.

Run the verification commands without any model access:

```bash
.venv/bin/python -m run.calitree_m0 verify --output-dir logs/exps/261014-semantic-hierarchy-m0-fifty-v1
.venv/bin/python -m run.calitree_m0_finalize --check --output-dir logs/exps/261014-semantic-hierarchy-m0-fifty-v1
.venv/bin/python -m pytest tests/unit/calitree/test_m0_reservation.py tests/unit/calitree/test_m0_sealed.py -q
```

Verification checks all 220 image files, their byte hashes, source-pixel
identities, metadata, label mapping, partition sizes, source independence,
historical disclosures, original baseline hashes, label-free inference inputs,
fold separation, and budget arithmetic. An additional preservation audit checked
814 original artifacts across the v5/v10/v12/v13/v16 and transfer experiments.

Seventeen tests passed. Negative tests reject altered policy snapshots,
train/test source overlap even after a manifest is rehashed, reference labels
inserted into model inputs, a false untouched-data claim, selection-fold leakage,
and premature final-set evaluation.

## Next milestone

M1–M4 are now implemented and audited; see the [bound-evidence report](calitree_m1_bound_evidence.md)
and [scalable learner / routing results](calitree_m2_m4_semantic_baselines.md).
Their weak development transfer does not qualify the new system for deployment.
Do not evaluate the reserved fifty while developing M1–M7.
