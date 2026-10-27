# Independent judge experts with an explicit semantic gate

The verified optional-expert replay improves from223/276 (80.8%) to
**225/276 (81.5%)**, with two corrections and no losses. All99 original cases,
144 original slots and273/276 upstream coverage remain unchanged. The active
>85% target still requires235/276, ten more correct cases.

This result uses15 valid cached Sol judgments on the primary comparison plus
one retained failed slot. Other cases retain the existing pipeline. The cache
subset comes from older selected diagnostics, so this is not a complete or fresh
Sol benchmark or evidence of81.5% on a new population.

## Cached evidence and source control

V84 audits4,197 budget files and46,065 durable job files across the two project
checkouts. Exact instruction, ordered image identity, generic regular prompt,
schema, model identity and request hash matching recovers the915 existing Luna
slots plus44 Sol slots. Of the latter,42 completed:27 original and15 primary
cases. No human labels or image bytes are read during matching; no model is
called. The fixed generic prompt has no fitted rubric or calibration examples.

Using every available Sol label directly also reaches225/276, but introduces
two primary losses and reduces original-case retention to92/99. The semantic
gate avoids those losses and keeps all originals. Even a perfect selector
between v72 and these cached Sol labels could reach only227/276; this limited
cache cannot by itself supply the235/276 target.

The first audit omitted the textual SOURCE/EDITED media markers and falsely
rejected matches. It is marked superseded. The corrected r2 audit reproduces all
915 known baseline matches and has regression tests for ordered media identities.

V85 compares three semantic vocabularies, one/two positive fitting-source
support, and actual-only versus all-label original protection. Every arm keeps
the same five source folds and excludes all held-source siblings. Existing30
inner source-excluded teacher views train the gate; no new teacher fitting or
paid inference is required. One-source support proposals improve transfer here;
they remain weakly supported hypotheses rather than general accuracy guarantees.

The selected semantic gate allows one positive fitting source but protects every
original input against every hypothetical Sol label. Each fold's material-
collateral/progress rule transfers between the two corrected held sources:
removing red objects with collateral deletions (N091), and a partly realized
basketball-court background replacement (P05M1). The latter contrasts with Luna's
over-crediting Yes; both were under-credited No by the boosted base.

## The executable rubric

The full artifact contains two review rules, following existing v72 corrections:

1. If the boosted judge says No, material collateral change is reported for all
   requirements, its No lacks an explicit rubric warrant, and a disagreeing
   independent proposal has a warrant, select that independent judgment.
2. If the boosted judge says Partial without a warrant, its normalized model
   support is below0.65, and a disagreeing independent proposal has a warrant,
   select that independent judgment.

A warrant uses same-requirement goal witnesses, endpoint/progress, identity,
authorized-change and collateral conditions. Missing or uncertain evidence does
not establish physical failure. Model support is a routing cue, not calibrated
correctness. "Reported material collateral" describes the observer's claim;
it does not itself certify the pixels or prove the boosted judge wrong.

The gate therefore keeps an independent vote. Replacing it with an unambiguous
counterfactual grade supported only by existing semantic fields drops accuracy
to218/276: three gains and eight losses versus v72. This is a changed policy,
not equivalent prompt compression. V86's eight broader one-source rubric
searches likewise do not beat223/276. The existing observations are not reliable
enough to replace the additional image judgment with prose rules alone.

## Reusable inference and routing coverage

`IndependentExpertPolicy` wraps the original v72 base and validates a supplied
independent record against its exact request contract. Missing, failed, malformed,
wrong-image or wrong-profile records retain v72. Existing v72 semantic corrections
have priority. The old teacher's class scores stay nested under its own route
when an independent grade overrides them; they are not presented as confidence
for that new grade.

`IndependentSemanticJudge` executes the actual bound inference path and renders
the independent explanation with its semantic review conditions. It does not
make per-node or automatic Sol calls. The opt-in artifact is in
`examples/calitree_independent_semantic_v87`; serving defaults stay unchanged.

`review_bound` computes the semantic region before acquiring an independent vote.
It enumerates possible proposals, returns whether review could affect the result,
and keeps the base decision. It must not convert those hypothetical proposals
into predictions: that is the failed standalone ablation above. All99 original
cached inputs request no independent review, and all297 hypothetical original
input/label combinations retain their original grade in every fold.

## Verification and remaining work

`logs/exps/261023-verified-independent-expert-v87-r2/verification.json` independently
checks36 native teachers, re-induces all six gates, validates actual144-slot
retention, and replays915 inputs through the exported policy and high-level
judge.67 focused tests pass, including record identity, semantic gate integrity,
fallback/priority, pre-review without prediction, and score provenance. All80
reserved sources remain excluded. No new paid calls were made.

The active target is not complete. The separately approved v75 training-only
contrastive pilot has since completed72 requests within its344,064-completion-token
cap: fresh regular15/24, semantic Luna14/24 and semantic Sol13/24. Neither semantic
arm is promoted. See [the v88 completion report](calitree_contrastive_pilot_v88.md).
Its Sol-medium certificate is a different contract from this historical generic
Sol-high profile and cannot be substituted silently.
