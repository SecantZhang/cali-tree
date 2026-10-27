# Single-tree replacement comparison

**None of the tested standalone trees matches V112 or V144.** The best eligible
tree scores203/276 (73.6%) overall and64.1% balanced accuracy, compared with
V112's227/276 (82.2%)/67.9% and V144's226/276 (81.9%)/71.1%. V112 remains selected.

## What was tested

The bounded comparison includes60 fixed configurations: semantic-only versus
full primitive evidence, human labels versus V112/V144 hard-label distillation,
uniform versus equal-class weighting, and leaf budgets8/16/32/64/128. Each runs
on the existing five source-held folds and a separate full-data fit:360 models.
The declared primary is full primitive evidence, human labels, equal class
weight,32 leaves. It scores184/276 (66.7%),56.5% balanced accuracy.

The semantic vocabulary contains the original instruction-bound physical/task
predicates. The full vocabulary uses the same fold-specific primitive feature
pool as the visual booster, adding regular-judge cues and SigLIP2 measurements.
This is a standalone tree: no boosted supports, predictions, review masks,
example membership, raw embeddings, object-name features or case lookups are
needed at inference. Distillation reads its teacher's fitting predictions only
to construct training targets; runtime exports contain no teacher.

Every fitting source and its sibling outputs are excluded when held out. All
276 evaluation cases remain in the denominator, including the unchanged
regular fallback for invalid bound evidence. These are repeatedly reviewed
development cases, not an untouched final evaluation. Best-arm reporting is
retrospective, not a newly preregistered model choice.

## Results

| Policy | Correct /276 | Overall | Balanced | Protection |
|---|---:|---:|---:|---|
| V112 |227|82.2%|67.9%|99 originals/144 slots retained|
| V144 candidate |226|81.9%|71.1%|99 originals/144 slots retained|
| Best eligible32-leaf tree, full/V112/uniform |195|70.7%|57.3%|99 originals/144 slots retained|
| Best eligible64-leaf tree, full/V144/balanced |203|73.6%|64.1%|99 originals/144 slots retained|
| Best eligible128-leaf tree, full/V144/balanced |200|72.5%|60.6%|99 originals/144 slots retained|

No8/16-leaf configuration retains all99 protected cases across every fit under
the tested fitting procedure. Six of twelve32-leaf configurations qualify;
all twelve64-leaf and all twelve128-leaf configurations qualify. There are30
eligible configurations in total. Failed local fits remain reported as
ineligible rather than being repaired with a hidden ensemble or lookup.

The best semantic-only tree by ordinary accuracy reaches198/276 (71.7%),53.6%
balanced accuracy at128 leaves. The best semantic-only balanced result is
181/276 (65.6%),55.2% balanced accuracy at64 leaves. The two maxima describe
different models and must not be combined into one score.

All configurations retain the same upstream273/276 validity/coverage mask and
exact regular fallback. The winning64-leaf full-data tree uses57 distinct
predicates and depth12; its fold models reach depth15. Eight full-data leaves
have only one distinct fitting source, so even this tree is not a short,
uniformly well-supported judging rubric. Its recalls are83.4% No,48.2% Partial,
and60.6% Yes. It loses24 correct decisions relative to V112.

## Fitting and protection

Each model is one deterministic log-loss CART, with no depth limit and minimum
leaf size1. For each fixed configuration, fitting tries original-case anchor
weights1/5/25/125/625 and stops at the first weight retaining the actual99
original predictions. Balanced arms renormalize each class after anchoring so
the classes retain equal total mass. No held-case labels select anchors,
features or pruning. Every full tree is exported as Boolean branches and
three-grade leaves, with named predicate descriptions and source counts.

The first run stopped before exporting its first model because sklearn's leaf
count was a numpy integer rejected by strict JSON. The metadata now explicitly
converts it to a Python integer. The failed r1 snapshot remains intact; the
complete experiment is a fresh r2, with no paid or neural calls in either run.

## Interpretation and limits

This establishes a negative result for bounded greedy CART with these feature
and target choices. It does not prove a compact semantic policy is impossible,
or isolate classifier architecture as the entire cause of the accuracy gap.
V112/V144 also have conditional local-observer/independent-expert evidence that
is not in the primitive booster feature pool. Reproducing their old review
mask with a booster would defeat this experiment's standalone replacement.
No new evidence collection was performed to remove that information gap.

The rendered tree is an empirical policy over named evidence, not a guarantee
that every grade has an affirmative semantic witness. False predicates retain
their original not-established meaning. More expressive rule induction,
better outcome/gap observations, or small task-specialist policies remain
distinct hypotheses; matching the current pipeline has not been demonstrated.

## Verification and artifacts

- Completed study: `logs/exps/261026-single-tree-v173-r2`.
- Independent audit: `logs/exps/261026-single-tree-audit-v174-r1`.
- The audit re-fits all360 models/1339 native fitting attempts, checks all35352
  exported/native topology nodes, and reproduces329400 scalar/native rows.
  Topology checks establish equivalence across the native tree's Boolean
  domain, beyond the cached row replay. All splits, targets, fallback routes,
  local-retention results and evaluation metrics agree.
- 16 focused tests pass, including portable JSON execution, insufficient
  capacity, identical-input label conflicts, tampering/missing evidence,
  anchor/class-weight behavior and the unchanged current pipeline.
- Zero API, local-observer, encoder or reserved-source calls; no default change.

```bash
PYTHONPATH=/tmp/calitree-catboost-v143:. python -m run.calitree_single_tree_v173 \
  --output-dir logs/exps/NEW_SINGLE_TREE_RUN
PYTHONPATH=/tmp/calitree-catboost-v143:. python -m run.verify_calitree_single_tree_v174 \
  --study logs/exps/NEW_SINGLE_TREE_RUN --output-dir logs/exps/NEW_TREE_AUDIT
```
