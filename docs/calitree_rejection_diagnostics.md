# Why ungated trees fail on v27-rejected cases

The evidence points to **both weak learned decision rules and inappropriate
expert voting**, with additional upstream evidence errors. Extraction failures
alone do not explain the result: in several inspected cases, the cached evidence
already states that the requested goal failed, yet the trees output Yes.

This analysis uses the frozen 80-case pilot and ungated ablation. It does not fit
new rules, change reference labels, call a model, or modify original evidence.
Six image pairs were inspected as targeted examples, not as a representative
human annotation study.

## 1. Routing/selection headroom differs sharply by bank

One failed observation is excluded from the following diagnostic denominators;
it remains included in the original 80-case evaluation. A correct expert exists
means at least one expert's cached prediction equals the reference label.

| Bank | Experts | Valid v27-rejected cases | Wrong ungated votes | Wrong vote but a correct expert exists | Every expert wrong |
|---:|---:|---:|---:|---:|---:|
| 1 | 4 | 64 | 34 | 30 | 4 |
| 2 | 3 | 65 | 39 | 23 | 16 |
| 3 | 2 | 54 | 41 | 12 | 29 |

An oracle selector could reach 60/64, 49/65 and 25/54 correct on these respective
subsets, versus the actual votes' 30/64, 26/65 and 13/54. This is **routing
headroom, not demonstrated router accuracy**. A correct vote can be coincidental,
and a deployable router does not know the reference label. The banks also have
different numbers of experts and reject different subsets, so these ceilings
are not directly comparable as generalization estimates.

Among wrong votes, a correct expert is already in the task-only semantic shortlist
for 23, 13 and 7 cases respectively. That shortlist still does not establish
full evidence support. This distinction matters: task applicability can help
selection but cannot substitute for all coverage checks.

Bank 1 has considerable selection opportunity. Bank 3 has a more fundamental
problem: on 29 of its 41 valid rejected errors, no expert can supply the correct
answer. Merely changing which existing expert is selected cannot fix those cases.
The current v27 gate did not force the wrong expert on these inputs—it deferred.
The ungated ablation introduced the unconditional all-expert vote.

## 2. Some learned rules misuse evidence that is already available

### A concrete Yes shortcut

Expert `80985be9…` in bank 3 has this complete terminal path:

```text
All requirements' evidence is coherent = true
All requirements allow a recognizable counterpart = true
→ Yes
```

The leaf's original support is **three Yes examples** from two batches (G2: 1,
G4: 2). It never checks requested-goal completion. Also, `retention_need` describes
what preservation standard the instruction permits; it is not evidence that the
standard was met. “Coherent” means the observations agree, not that they describe
a successful edit.

For P01M1, “Make them stand up fully upright looking at their hands,” the cached
interpreter says `incidental_change_only`, `core_endpoint_missing` and
`material_shortfall`. The edited image shows standing figures, but does not
establish the requested hand-looking pose. The human label is No. Both bank-3
experts nevertheless output Yes. This is direct evidence that routing alone
cannot fix that bank on this case, and that the available negative evidence is
not being used as a sufficient reason to withhold full credit.

### Incorrect complements of semantic categories

For P03M4, “move the brown sphere to the right of the purple block,” the large
sphere changes color and remains left of the block. The cached interpretation
correctly reports `wrong_direction_or_target`, incidental change and a material
shortfall; the reference and regular judgment are No.

All four bank-1 experts return Partial or Yes. One checks whether the gap is
`core_endpoint_missing`, finds false, and proceeds toward Yes even though the
actual gap is the mutually exclusive `wrong_direction_or_target` category.
Likewise, `progress != none` does not imply meaningful progress: it includes
incidental change and uncertainty.

Bank 2 contains an expert that checks the failed spatial outcome and correctly
returns No. Its other two experts return Yes and Partial; the fixed three-way
tie returns Partial. The same case therefore exposes a rule failure in one bank
and a recoverable selection/voting failure in another.

### The existing rule check is narrower than semantic consistency

`portable_review_v8.violations()` checks contradictions **explicitly written on
a learned path**. The fitter likewise forbids a Yes leaf after taking an explicit
positive branch for one of four contradiction predicates. It does not inspect
all unvisited input features or require positive goal-completion evidence on
every Yes path. Thus a tree can avoid testing a contradiction and still return
Yes when that contradiction is present in the input.

On valid rejected cases:

| Bank | Ungated Yes outputs | Correct Yes outputs | Yes outputs with an active all-requirements goal-contradiction feature |
|---:|---:|---:|---:|
| 1 | 26 | 2 | 16 |
| 2 | 13 | 4 | 5 |
| 3 | 8 | 1 | 8 |

At the individual-expert level, 53/91, 29/56 and 32/40 Yes votes have an active
contradiction predicate that their path never reads. These counts establish
**rule/evidence disagreement**, not a causal count of rule-induced errors:
the cached evidence can itself be wrong, and some contradictory Yes votes happen
to match the human label.

The broader structural issue is that our objective rewards local label fit and
compactness. Semantic feature names do not make every learned association a
sound decision policy. Three locally correct examples can support an overly
broad shortcut unless the policy language imposes stronger semantic requirements.

## 3. Upstream evidence also contains real errors

### Visual grounding: the missing-cat claim

P06M3 requests a doodle rendering. The edited image visibly retains an outlined
gray cat-shaped figure in front of the television, between smaller figures.
The observer nevertheless says the cat disappeared. It marks preservation false,
and marks deformation true even though its accompanying comparison says no
structural deformation is established beyond the authorized style change.

The interpreter propagates this into material shortfall, material collateral
change and conflicting evidence. The human and regular-judge labels are Yes;
bank 3's two trees both say No. This is an identifiable visual-evidence error,
including an internal state/description inconsistency, not just misrouting.

An **isolated manual diagnostic repair** changes the three affected observation
judgments and updates the materiality/consistency interpretation. The original
program, images, evidence files and reference label remain unchanged. This is
not a new model output or an official human annotation.

| Bank | Original ungated vote | After manual evidence repair | Human label |
|---:|---|---|---|
| 1 | Partial | Partial | Yes |
| 2 | Partial | Yes | Yes |
| 3 | No | Partial | Yes |

Correcting this evidence helps, but is insufficient in two banks. In bank 3,
one tree now says Yes while the other penalizes the transformed counterpart;
the tie rule yields Partial. This demonstrates interacting upstream and
policy/voting errors rather than a clean one-cause partition.

### Instruction grounding: a canister's “right hand”

P09M1 asks to place a hat “on the right hand of” a canister. The compiler turns
this into placement on the canister's literal hand. The observer then reports
that no hand is discernible. The source and edit show ordinary tabletop objects,
with a hat moved to the canister's right and an extra hat introduced. This is a
likely misgrounding of right-side language into an anatomical relation. The
human label is Partial. Fixing the downstream tree cannot reconstruct the
intended geometry from a wrongly specified question without additional evidence.
This case was inspected but not manually recompiled or rescored.

### Compound requirements and aggregation

P14M5 requests a bottle and a card on a table. The observer finds no bottle and
interprets an added printed item as card-like. One requirement is recorded as
`none/core_endpoint_missing`, the other as `requested_endpoint/none`. Whether
the printed item should count as the requested card is itself ambiguous.

The learned global tests `progress_none_all=false` and
`endpoint_gap_core_endpoint_missing_all=false` do not establish that both
requirements succeeded. Some trees nevertheless produce Yes. This combines
possible object-grounding ambiguity with a rule/representation problem:
not-all-failed is not all-succeeded. The human label is No; it was not changed.

## 4. What I would change first

1. **Make Yes require affirmative, requirement-level outcome support.** Prevent
   instruction-type descriptors, coherent evidence or lack of collateral damage
   from substituting for goal achievement. Test these constraints against the
   existing local accuracy/coverage requirements before adoption; inconsistent
   local evidence may need repair rather than a weaker semantic rule.
2. **Route by demonstrated conditional competence.** Prefer experts with relevant
   supported task/evidence regions; do not give every batch tree an unconditional
   equal vote. The oracle gap motivates this work but is not its promised result.
3. **Repair specific upstream contract failures.** Address right-side grounding,
   authorized style transformations, presence/disappearance verification and
   disagreement between check states and their supporting descriptions.
4. **Use paired corrected-evidence diagnostics to measure causation.** A stratified
   reviewed subset with adjudicated task decomposition and evidence would let us
   compare fixed trees on original versus corrected evidence. The present six
   targeted examples do not justify assigning a global percentage of errors to
   extraction versus rules.

More merge search alone will not solve the cases where every expert is wrong or
where the evidence asks the wrong question. Retain the coverage gate while these
policy and evidence problems are addressed.

## Artifacts and verification

Run: `logs/exps/261020-rejection-diagnostics-v31`. It contains per-bank/rejection
reason oracle diagnostics, per-expert unread contradiction flags, six reviewed
examples with image references and traces, the isolated doodle intervention and
the three-example shortcut leaf's original provenance.

The audit verifies the count decomposition, source/image hashes, original leaf
support, counterfactual schema/bindings and all repaired votes. Original evidence
and models remain unchanged. Seventeen targeted tests pass. There are **zero
model calls, no fitting, and no reference-label changes**.
