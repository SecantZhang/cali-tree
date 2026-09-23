# Cali-Tree calibration system: goal and current functionality

## Primary goal

Build an image-judge calibration system that deliberately specializes prompts at the
leaves, then compresses those specialized prompts bottom-up into increasingly general
parent prompts.

The intended behavior is:

1. Each leaf prompt overfits a small, semantically coherent set of training examples.
2. Similar leaves are clustered.
3. Their prompts are merged and compacted into a parent prompt.
4. The parent is accepted only if it retains sufficient accuracy over its descendants.
5. This repeats bottom-up, ideally producing a root prompt that covers most cases.
6. Cases that cannot be classified reliably as `no`, `partial`, or `yes` can be referred
   as `needs_human`.

The central research question is whether specialization followed by validated compression
produces a compact, generalizable calibration tree—and whether selective human referral
can address the particularly difficult `partial` boundary.

## Current data and target

Each ImagenHub case contains:

- Source image
- Edited image
- Editing instruction
- Editor/model identity
- Task UID
- Three human Semantic Consistency ratings
- Three Perceptual Quality ratings
- Train/test split metadata

Semantic Consistency is the prediction target. The three human SC ratings use:

- `0.0` → `no`
- `0.5` → `partial`
- `1.0` → `yes`

The median SC rating becomes the three-class target.

All outputs belonging to the same task UID must stay in the same partition to prevent task
leakage.

The validated large benchmark currently contains 1,200 held-out cases: 150 tasks × 8 public
editors.

## Current Cali-Tree v2 algorithm

### 1. Leaf specialization

The current implementation groups the editor outputs for one task into a joint leaf.
Therefore, a leaf specializes to one instruction/task rather than one individual image
pair.

Each leaf begins with the global rubric and is optimized with TextGrad:

- Stop when all covered training cases are correct.
- Stop after three optimization steps.
- Stop if the shared optimizer completion-token budget is exhausted.
- Save every prompt version, prediction, token count, and optimization result.

Leaf granularity should remain configurable if the next experiment wants one leaf per case
or one leaf per semantic cluster.

### 2. Prompt preprocessing

Each optimized prompt is converted into normalized components:

- Evaluation criteria
- Priorities
- Output constraints
- Semantic operation family
- Conflict-sensitive requirements

Instructions are also mapped into target-blind operation families such as:

- Add
- Remove
- Replace
- Recolor
- Spatial transformation
- Style transformation

The preprocessing must never use the human target or test-set performance.

### 3. Semantic clustering

Prompt components are embedded with a configured embedding model.

Active nodes are paired using complete-link cosine similarity:

- Initial similarity threshold: `0.90`
- Reduce by `0.05` per level
- Minimum threshold: `0.70`
- Early levels additionally require compatible operation families
- Rejected pairs are not repeatedly retried at looser thresholds

A better semantic clustering or pre-merging algorithm is an open experimental direction.

### 4. Conflict detection

Before merging, the system checks for incompatible criteria. Examples include prompts that
apply conflicting definitions of success or source preservation.

When conflicts cannot be reconciled safely:

- Do not force a merge.
- Preserve the children as separate branches.
- Record the conflict and the conflicting criteria.

Conflict resolution can produce a conditional parent rubric if the distinction is
identifiable from inference-time inputs. It must not use dataset identity, target labels,
or hidden test information.

### 5. Bottom-up merge and compaction

The optimizer synthesizes a shorter parent prompt intended to cover the union of both
children.

The candidate parent is evaluated on all covered leaf cases and an internal task-grouped
validation guard:

- `100%` covered-case accuracy: accept as a full merge.
- `≥80%`: accept as a partial merge.
- Correctly handled cases remain assigned to the parent.
- Incorrect original leaves are promoted and remain available for later merging.
- `<80%`: reject without modifying the children.
- Generalization-guard failure: reject or prune the proposed parent.

The process stops when no eligible merge remains. A single universal root is desirable but
not mandatory—a validated forest is preferable to an inaccurate root.

### 6. Inference routing

For an unseen case:

1. Construct a target-blind representation from its instruction and permitted metadata.
2. Start at the validated global root or nearest general node.
3. Descend only when a child centroid exceeds its stored routing threshold.
4. Otherwise remain at the nearest validated ancestor.
5. Avoid routing to unsupported one-case leaves without an extremely close match.

The output records:

- Underlying three-class prediction
- Routed node ID
- Prompt version
- Route path and thresholds
- Confidence/evidence
- Human-review decision

## Current `needs_human` behavior

`needs_human` is currently a deployment decision, not a fourth human annotation.

Each result preserves both fields:

```json
{
  "label": "no | partial | yes",
  "decision_label": "no | partial | yes | needs_human",
  "needs_human": true,
  "review_reason": "reason for referral",
  "routed_node_id": "node identifier"
}
```

The underlying `label` is retained even when the case is referred. This is essential for
measuring the full-coverage classifier independently from the review policy.

The next version should improve the referral decision using explicit evidence:

- Are essential requested conditions visible?
- Is the evidence contradictory?
- Is the edit visibly incomplete, or merely difficult to determine?
- Do multiple judge paths disagree?
- Is the routed node unsupported or below its validation threshold?

The semantic distinction must be:

- `partial`: there is clear evidence that the instruction was only partly completed.
- `needs_human`: the system cannot reliably determine whether the instruction was
  completed.

## Required evaluation

### Metric 1: Full-coverage classification

Evaluate the underlying `label` against the median human target for all cases—including
cases sent to review.

Report:

- Three-class accuracy
- Balanced accuracy
- Macro F1
- Per-class precision, recall, and F1
- Confusion matrix
- Ordinal MAE using `no=0`, `partial=0.5`, `yes=1`
- Task-grouped bootstrap confidence intervals
- Train, validation, held-out, and per-editor results

This answers: “How good would the model be if it could not abstain?”

Current v2 reference on 1,200 held-out cases:

- Accuracy: `82.83%`
- Balanced accuracy: `60.41%`
- Partial recall: `26.67%`
- Partial F1: approximately `31.5%`

### Metric 2: Non-referred or automatic accuracy

Remove cases for which `decision_label=needs_human`, then evaluate accepted predictions.

Always report accuracy together with coverage:

```text
auto accuracy = correct accepted predictions / accepted cases
coverage = accepted cases / all cases
```

Current selective v2 result:

- Correct automatic decisions: `716`
- Accepted cases: `771`
- Auto accuracy: `92.87%`
- Coverage: `64.25%`
- Referred cases: `429/1,200`

Accuracy without coverage is misleading because referring every difficult case can produce
arbitrarily high conditional accuracy.

### Metric 3: `needs_human` quality

“Are the referred cases actually cases with bad human consensus?” is not conventional
accuracy. It is **referral precision**:

```text
consensus-referral precision = P(bad human consensus | needs human)
```

Use the initial frozen definition:

```text
bad_consensus = the three SC ratings are not unanimous
```

Also report:

```text
consensus-referral recall = P(needs human | bad human consensus)
```

Required referral metrics:

- Referral precision for disputed human ratings
- Referral recall for disputed human ratings
- Referral F1
- Review rate
- Error-capture recall
- Error prevalence among referred cases
- Fraction of true `partial` cases referred
- Metrics by editor and operation family

For the current v2 policy:

- Total disputed cases: `260`
- Disputed cases referred: `172`
- Total referrals: `429`
- Consensus-referral precision: `172/429 = 40.09%`
- Consensus-referral recall: `172/260 = 66.15%`
- Model errors captured: `151/206 = 73.30%`
- Model-error prevalence among referrals: `151/429 = 35.20%`

This shows that the current policy is better at capturing model errors than specifically
identifying human-rater disagreement.

These are different objectives and must remain separate:

1. **Annotation ambiguity:** humans disagree.
2. **Model risk:** the model is likely wrong.

A case can be unanimously rated by humans but still be difficult for the model. Conversely,
humans may disagree even when the model matches the released median target.

### Assisted-system result

With perfect human resolution, the current selective v2 ceiling is:

```text
(716 correct automatic + 429 perfectly reviewed) / 1,200 = 95.42%
```

This must be named the **perfect-human-review ceiling**, not model accuracy. Real assisted
accuracy requires an independent human reviewer’s returned label.

## Tree-specific metrics

In addition to classification metrics, report whether bottom-up compression actually works:

- Number of initial leaves
- Number of accepted full merges
- Number of partial merges
- Number of rejected/conflicting merges
- Final node count
- Leaf-to-final-node compression ratio
- Root-covered case percentage
- Root accuracy
- Accuracy loss from children to parent
- Accuracy and coverage by tree depth
- Mean inference route depth
- Fallback-to-root rate
- Promoted-leaf count
- Training and inference token usage
- Estimated cost and latency

## Success criteria

A publishable result should aim for:

- Automatic accuracy ≥90%
- Meaningful automatic coverage, preferably ≥50–60%
- Full-coverage accuracy materially better than the current `82.83%`
- Better `partial` precision/recall, not just higher majority-class accuracy
- Strong referral error capture
- Reported consensus-referral precision and recall
- Task-grouped confidence intervals
- No task leakage
- Frozen thresholds before final evaluation
- Similar behavior on a second dataset
- An untouched final test partition

The full 1,200-case ImagenHub set has already been inspected repeatedly. It can be used for
development and ablations, but it should no longer be described as untouched confirmation
data.

## Implementation handoff

Continue from:

- Worktree: `/Users/zzhang/Documents/vejudge/.claude/worktrees/calitree-implementation`
- Branch: `codex/calitree-implementation`
- Baseline commit: `7670df1`
- Main report: `docs/calitree.md`
- Backend: `vejudge/interface/node_calibration/calitree_nodes.py`
- Prompts: `vejudge/core/prompts/templates/calitree_v2/`
- Tests: `tests/unit/interface/node_calibration/test_calitree_nodes.py`

Do not remove the current v2 or v4 implementations. Preserve them as frozen baselines and
implement the new tree-plus-referral approach as a separately versioned experiment.
