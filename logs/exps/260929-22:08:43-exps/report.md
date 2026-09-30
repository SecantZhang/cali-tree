# Luna fresh-observation reliability pilot

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
