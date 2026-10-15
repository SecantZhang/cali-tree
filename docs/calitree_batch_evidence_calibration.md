# Batch calibration of single-call evidence

The batch layer learns the mapping from cached evidence to AURORA's three
reference classes on a separate source-disjoint calibration batch. It consumes
the same single-call evidence records used by the fixed-policy judge. The image
observer and its prompt remain unchanged.

## Data separation

The pilot selects 36 AURORA-editor outputs from official seed-42 training tasks:
12 No, 12 Partial and 12 Yes. Selection uses source-pixel fingerprints, category
spreading and deterministic hash ties. It excludes all twelve evaluation source
groups, the earlier twelve fitting source groups, and the reserved fifty-case
holdout. The twelve evaluation cases are reused exactly; they are never fitted.

References remain released aggregate human means mapped at 0.5/1.5, not individual
annotator votes or human annotations of individual checks. The calibration sample
is balanced before calls; failed/malformed observations are not resampled and
cannot enter fitting. Their count and full-batch uncalibrated accuracy remain
reported. Fitting stops if usable records cannot support three-fold selection.

## Calibration model

`EvidenceBatchCalibrator` subclasses the existing `Calibrator` interface. It fits
an L2 multinomial logistic classifier using:

- Target and source-integrity categorical states.
- Fractions of complete/incomplete/absent/unknown checks within core and
  constraint requirements, plus their counts.
- Up to 256 TF-IDF words/bigrams from the scope, evidence explanations, and
  check questions; terms must occur in at least two fitting records.

It receives no case IDs, task labels, editing model names, human means, or
evaluation references. Its input whitelist accepts only instruction and evidence
records. The instruction is used to validate requirement provenance; raw
instructions are not appended separately to the text features.

Three-fold stratified CV selects C from 0.1, 1, and 10 using macro recall, with
ties favoring smaller C. Text vocabulary and numeric scaling are fitted inside
each fold. A final model is fitted on all usable calibration records and published
to an immutable, content-versioned calibration registry before evaluation.
The JSON artifact contains vocabulary, IDF, scaling, coefficients, and training
provenance; it needs no pickle or model calls to predict.

Two guards remain fixed: unresolved evidence stays unresolved, and a fixed-policy
No stays No. Other resolved records may become any of the three labels. Classifier
probabilities are reported for inspection but are not validated confidence scores.
This is a statistical text calibration baseline, not a learned semantic rule tree.

## Run

```sh
.venv/bin/python -m run.calitree_batch_calibration --preflight \
  --output-dir logs/exps/NEW-CALIBRATION-RUN
.venv/bin/python -u -m run.calitree_batch_calibration --live \
  --output-dir logs/exps/NEW-CALIBRATION-RUN
.venv/bin/python -m run.calitree_batch_calibration --replay \
  --output-dir logs/exps/NEW-CALIBRATION-RUN
```

Use `--evidence-dir` to choose a compatible cached twelve-case evidence run.
The default is `logs/exps/261013-single-call-evidence-balanced12-v1`.

The pilot makes at most 36 new image calls, with four independent API workers,
the same GPT-6.1 Sol/high profile, one SOURCE-first presentation and one durable
HTTP attempt per calibration case. Fitting and twelve-case evaluation are fully
offline. Logs include the frozen manifest/source, cost estimate, observations,
registry artifact, fold predictions, three-way comparison and exact replay.

## Interpretation

Training accuracy and model-selection CV are calibration diagnostics, not final
test accuracy. The source-disjoint twelve-case comparison is small and historically
inspected. One observation per case does not measure repeat robustness. A small
text model may learn lexical/category correlations instead of semantic tolerance;
it cannot recover visual information omitted or misread by the observer. Protected
No decisions also limit what this calibration layer can correct.
