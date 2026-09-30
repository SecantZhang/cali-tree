# Fresh observation reliability: small Luna prototype

## Frozen protocol, 2026-09-29

Future CaliTree experiments use **gpt-6-luna** as the main model by user request.
Historical results and saved workflows retain their recorded models. This pilot uses
Luna, temperature 0, reasoning none, strict JSON, and no model fallback.

Question: do fresh image-based measurements of the retained frozen decision sets
stay consistent and visually defensible on individual cases? This does not test
neutral single-image observations, repeated compilation, shared concept alignment,
learned trees, or generalization. No prompt optimization or criterion repair occurs.

Three fresh repetitions on J03 (laundry door), J10 (cartoon style), and J13 (egg in
right hand), each with two frozen conditions: **18 requests maximum**, 1,024 completion
tokens per request, **18,432 completion tokens maximum**. One HTTP attempt per request,
no schema repairs. Failed requests retain their reserved budget and stop the run.
Malformed draws remain failures and are not selectively resampled.

These are a deliberately small, selected subset of the historical fitted cohort.
Their retained plans report no case-specific fitting feedback, but category prompts
were previously optimized; this is not an independent accuracy evaluation. Labels
are provisional references, not condition ground truth. J16 remains excluded by its
explicit user review. Model disagreement alone never quarantines or relabels a case.

Before model execution, the assistant inspected the original image pairs:

| Case | Visible basis for auditing fresh descriptions | Limitation |
|---|---|---|
| J03 | Source contains a person and an open round laundry door. Edited image replaces the appliances with blue rectangular units and removes the person. | The original door cannot be followed into the edit; unknown versus absent may expose a criterion gap. Scene replacement is visible. |
| J10 | The room largely remains photographic; a small wall picture becomes a cartoon drawing. Furniture and layout remain recognizable. | Whether a cartoon picture counts as partial global stylization is a scoring-policy issue, distinct from seeing the picture. Small preservation changes may affect complete/partial. |
| J13 | Source has a small egg on the counter; edited image has a much larger egg held by the right hand. Kitchen and body layout remain recognizable. | Size/identity and incidental scene changes can create scoring-policy disagreements; an action observation alone does not establish a final quality score. |

J14 was initially considered but replaced before any new model calls because its
frying-pan referent was unclear on inspection. No post-result cohort replacement.
The visual audit above is assistant review, not independent human concept annotation.

Report every condition's three statuses, known coverage, status agreement, source
and edited descriptions, and case-level provisional label agreement. The local
fixed reducer returns no for any absent, otherwise partial for any partial, otherwise
yes; any unknown or invalid yields **unresolved**, including combinations with absent.
This conservative diagnostic reducer leaves the historical algorithm unchanged.

Pilot screening gate: all six conditions stable and known in all three draws, and
no material visual contradiction found in the descriptive audit. Failure identifies
what remains unverified; passing only permits a tiny exploratory feature/tree prototype,
not a claim of general reliability. Three repeats cannot establish a population rate.
Stable but wrong descriptions fail the visual audit. Label disagreements are reviewed
separately and do not automatically establish an observation error.

## Reproduction

The runner uses the existing frozen-criteria executor, original image/plan loader,
and persistent budget. Every repeat has a separate checkpoint directory. Restarting
an existing completed run is cache replay, not a fresh replicate. Changed inputs,
model settings, source code, or image hashes require a new run directory. The manifest
records exact images, prompts, plans, historical fitting provenance and source hashes.
Local manifests contain labels for analysis; model requests do not.

```bash
.venv/bin/python -m run.calitree_observation_reliability \
  --output-dir logs/exps/260929-22:08:43-exps
.venv/bin/python -m run.calitree_observation_reliability \
  --output-dir logs/exps/260929-22:08:43-exps --live
```

The default is a dry run with no credential access and no model calls. The live path
requires the configured official OpenAI endpoint. Full responses, usage, and returned
model IDs are in `llm-histories.log`; each draw also exports structured observations
and call records. This research runner requires the checkout's existing pilot data
and is not a new production decomposition variant.

Official references: [Luna model](https://developers.openai.com/api/docs/models/gpt-6-luna)
and [OpenAI changelog](https://developers.openai.com/api/docs/changelog). The September 25
image-encoding fix is another reason to collect fresh measurements rather than infer
current behavior from the earlier Luna comparison.

## Results: useful observations, reliability gate not passed

The user approved the exact bounded image transfer, and the live run used
`gpt-6-luna` throughout. Two full repetitions completed for all three cases.
The third repetition completed J03's door check, then an SSL transport failure
(`SSLV3_ALERT_BAD_RECORD_MAC`) stopped execution during its preservation check.
There was no automatic retry, criterion repair, model fallback, or follow-up paid run.

Of 18 planned calls, **14 were attempted: 13 completed, one failed, four were not run**.
All 13 completed outputs parsed and finished normally. The successful requests used
**11,927 prompt tokens and 1,857 completion tokens**. The failed request retains a
1,024-token reservation, so the budget ledger reports 2,881 completion tokens used
or reserved. Failed-request provider billing is unknown. Successful usage corresponds
to approximately **$0.0021 at the documented uncached standard rates**, excluding any
failed-request billing and cache discounts; this is an estimate, not an invoice.

### Every condition

| Case / condition | Repeat 1 | Repeat 2 | Repeat 3 | Interpretation |
|---|---|---|---|---|
| J03: laundry door closed | unknown | unknown | unknown | Target round door is not identifiable in the edit; consistent with the frozen unknown rule. |
| J03: rest of scene preserved | unknown | absent | transport error | The model describes removed/replaced objects both times, but assigns different states. |
| J10: cartoon style applied | partial | partial | not run | Cartoon-like wall picture detected; rest of room remains photographic. |
| J10: source scene preserved | complete | complete | not run | Main room contents and layout are recognized. |
| J13: right hand picks up egg | complete | complete | not run | Right-hand grasp/lift is recognized. |
| J13: rest of scene preserved | partial | partial | not run | Minor framing/body-position shifts are penalized by the strict preservation condition. |

Among the available repetitions, **5/6 conditions have identical statuses**;
**4/6 are both consistent and known**. There are **9 known and 4 unknown** results
among the 13 completed condition measurements. These denominators exclude transport
failures and unexecuted calls. They are descriptive counts on these cases, not a
population reliability estimate. No condition has three completed, known, consistent
measurements because the third repetition was interrupted and its only completed
condition was unknown.

The runner's original `results.json` summarizes completed *case draws*, so it marks
the partial third J03 draw as missing. The supplemental `audit.json` and
`observations.csv` recover the successful third door measurement from `calls.jsonl`;
it is included above. The original run artifacts were preserved unchanged.

### Case-level outputs and provisional annotations

| Case | Existing human label (provisional) | Completed fresh outputs | Agreement with that label |
|---|---|---|---|
| J03 — Close the laundry machine door | no | unresolved, unresolved | 0/2; both abstentions |
| J10 — Make the image look like a cartoon | partial | partial, partial | 2/2 |
| J13 — Pick up the egg with the right hand | yes | partial, partial | 0/2; both resolved disagreements |

All three cases repeat their *final output* across the two completed draws, but this
masks J03's underlying preservation-state change. There are four resolved judgments
out of six completed case draws, two of which agree with the provisional annotation.
This is annotation agreement, not verified accuracy. No labels were changed or cases
automatically quarantined. J16 was not evaluated.

### Visual and criterion audit

This is an assistant audit of the exact image pairs and all saved descriptions,
not independent human concept ground truth.

- **J03:** Descriptions correctly distinguish the open round door/person in the
  source from the blue rectangular units in the edit. The door's unknown state
  follows the saved criterion when its referent disappears. For scene preservation,
  the first response itself notices the missing person and front-loading appliance
  but treats insufficient correspondence as unknown. The second uses those visible
  changes to return absent. The frozen absent rule explicitly covers major object
  replacement; the unknown rule concerns invisibility or occlusion. This is a
  concrete inconsistency in mapping visible evidence to the categorical state.
  It does not require inventing a new detector or treating J03's label as wrong.
- **J10:** Both descriptions locate the cartoon treatment in the wall picture and
  retain the photographic-room observation. That visible distinction is supported.
  Calling it partial follows the broad frozen rule allowing some stylized parts;
  it does not establish that a cartoon picture fulfills a global style instruction.
  Preservation is consistently complete, although the rubric's minor-change and
  cartoon-rendering clauses leave room for scoring-policy interpretation. Thus the
  observation is useful without claiming that the compiled rule is uniquely correct.
- **J13:** Both action observations agree with the visible right hand holding the
  enlarged egg. Both preservation responses identify small framing/body-position
  differences while recognizing the same kitchen. The partial final result follows
  the strict preservation criterion. Whether these incidental changes deserve that
  penalty is a policy/annotation question; the benchmark yes is not automatically
  authoritative. The experiment supplies no independent adjudication of that boundary.

No material hallucination in the central visual descriptions was apparent in this
small audit. That limited finding does not establish exhaustive visual correctness:
it is neither blinded nor independently annotated, and the categorical status issue
remains observable regardless of agreement with the human case label.

### Decision and next step

**The fresh-observation reliability screen did not pass.** The evidence is useful,
but a complete known and stable decision-set representation is not yet demonstrated.
The SSL interruption limits the sample; the observed unknown/absent inconsistency
already prevents a pass even without the interruption.

Keep the restored simple baseline. The smallest next step is to review the generic
boundary between **visible failure (removed/replaced)** and **unobservable evidence**,
and agree on preservation tolerance before trying to learn from the exported states.
Do not rework the architecture around a single image, convert unknown to a negative
training target, or exclude a case merely because its model output disagrees with a
label. A tiny exploratory tree can use explicitly audited, resolved features later;
this run does not justify declaring assumption 3 verified or starting broader training.
No additional model calls were made or requested after the failure.

### Saved evidence and checks

Run directory: `logs/exps/260929-22:08:43-exps/`.

- `manifest.json`: frozen prompts, conditions, images, model settings and source hashes.
- `results.json`: completed case draws and transport stop reason.
- `draws/*/*/calls.jsonl`: all successful and failed condition attempts, including the partial third draw.
- `llm-histories.log`: full prompts, responses, returned model IDs and token usage.
- `audit.json` / `observations.csv`: all 18 planned condition slots, explicitly distinguishing unknown, failed and not run.
- `analyze_saved_calls.py`: offline reconstruction and assertions over model, output validity, label isolation and denominators.

The frozen runner and core algorithm were not modified after the live protocol was
saved. Earlier offline verification passed 277 tests with 23 skipped; the focused
prototype suite passed seven tests. The saved-call audit made no model calls.
