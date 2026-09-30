# Neutral observation and source anchoring on the observed J32 cohort

These experiments follow the frozen 32-source validation in
[visual_calibration_holdout32_20260926.md](visual_calibration_holdout32_20260926.md).
The J cohort is now development data, not an unseen test. No new task/source
pixels were consumed. The optimized category rubrics, condition plans, training
reference pairs and original calibrated-vision decisions were reused exactly.
Query human annotations were used only for scoring after prediction.

## Source anchoring diagnostic

Four previously observed failures (J01, J05, J10, J29) were selected to investigate
identity and hallucinated state changes. A text-only instruction/condition plan
plus SOURCE image generated target descriptions and normalized bounding boxes.
The compiler had no EDITED image, rubric, human label or previous decision.
Automatic SOURCE crops added ten percent relative padding and were verified
pixel-for-pixel against their verified source images. No coordinates were chosen
by a person. Both arms used the same frozen calibrated grader and a generic
source-identity instruction. One supplied anchor text; the other also supplied
SOURCE crops with adjacent image-role markers.

| Case | Human | Frozen control | Anchor text | Anchor text and crops |
| --- | --- | --- | --- | --- |
| J01 | no | yes | yes | yes |
| J05 | no | partial | no | partial |
| J10 | partial | no | no | no |
| J29 | partial | no | no | no |

Text anchors corrected J05; adding crops lost that correction. This selected
failure diagnostic provides no population accuracy estimate and does not support
promoting SOURCE crops. Artifacts:
`.cache/calitree-tests/vision-source-anchor-diagnostic-20260926/`.

## Independent observation algorithm

1. Compile instruction and its cached condition plan into observable questions,
   without images, rubric, annotations or previous decisions.
2. Ask the identical questions separately about SOURCE and EDITED. Each observer
   receives only one image and the questions: no instruction, rubric, image role,
   references or human annotations.
3. Add those two reports as fallible evidence to the unchanged calibrated grading
   payload. The grader still receives the original images and three training
   reference pairs with adjacent role markers. It must check reported differences
   against the images and apply the original optimized rubric.

All live calls used gpt-4.1, temperature zero, maximum 4,096 output tokens, one
quality draw and at most one schema repair per stage. Invalid cases remain in the
32-case denominator. Public image files were rechecked against the exact hashes
verified in the earlier AURORA archive provenance audit.

A free-question diagnostic on the same four failures corrected J01 and J29 but
not J05 or J10. The subsequent full-cohort draw included all 32 cases without
correctness filtering; it did not reuse successful diagnostic predictions.

| Method | Correct / 32 | Invalid | Balanced accuracy |
| --- | --- | --- | --- |
| Frozen calibrated vision control | 28 | 0 | 86.2% |
| Free-form neutral questions | 24 | 5 | 76.7% |
| Typed property probes with fixed neutral questions | 26 | 2 | 79.3% |

The cohort contains 25 no, six partial and one yes cases. Constant no scores
25/32. Balanced accuracy averages the three class recalls; the yes recall has
only one example and is not a reliable population estimate.

The free-question arm corrected J01/J05/J29 but regressed J02/J04/J07/J08/J12
(schema failures) and J16/J22 (partial became yes). In J22 the generated question
mentioned signs of laughter, leaking the requested state despite the neutral
compiler instructions. In J16 the final grader overstated the evidence for a
fork holding a disconnected fish piece. Extra observations therefore did not
reliably prevent desired-state hallucination.

The typed arm selected from existence/attributes, count, spatial relations, body
state, facial expression, interaction and style distribution. Object and reference
classes were intended as generic noun classes. Fixed renderers described visible
facts without mentioning the desired state. These are observation templates,
not hand-written per-case label rules. The observer still received only rendered
questions and one image. This corrected J05/J29 but regressed J02/J08/J11/J16.

J02 failed because the repaired relation probe had a null reference class. J08
failed because the observer returned an invalid answers container after repair.
Other raw responses had missing final braces or omitted question IDs. They were
short responses, so token-limit truncation is not established by their length.
The old engine did not retain finish reason, leaving that mechanism unverified.
Semantic errors also remain: J01 interpreted curtains as more closed (partial vs
human no); J10 treated a cartoon wall picture as no rather than human partial;
J11 similarly assigned no to a localized style change; J16 assigned no to the
partially accomplished fork/fish action. Correct formatting alone cannot settle
these partial-credit judgments or establish visual grounding.

## Audit limitation and repair

The original free-question diagnostic/development request helper retained raw
calls only after successful validation. Failed observer responses and some
preceding successful role responses were lost; no full history writer was
attached. The original result remains preserved and is not retroactively claimed
to have complete failure traces. The typed-property run corrected this logging
problem: every stage response was appended before validation, including failed
attempts, and a full LLM history was attached. Its prompts, manifest, source
snapshot, draws and final results remain frozen.

Artifacts:

- `.cache/calitree-tests/vision-neutral-observation-diagnostic-20260926/`
- `.cache/calitree-tests/vision-neutral-observation-development32-20260926/`
- `.cache/calitree-tests/vision-neutral-property-development32-20260926/`

Neither observation variant is promoted into a core decomposition strategy.
The opt-in calibrated vision implementation and defaults remain unchanged.
## Strict JSON Schema development result

The identical typed-property prompts and semantic validators were rerun once on
all 32 cases using native strict JSON Schema at every stage. Schema enum/length
constraints enforce output fields, valid IDs and reference-class presence for
relation probes; semantic condition coverage and meaningful strings remain
validated locally. No predictions were selected across repeated draws.

The result was **28/32, zero invalid**, balanced accuracy **82.0%**. This ties the
frozen control's raw accuracy and has lower balanced accuracy (86.2% control).
It corrected J01/J05 but regressed J11/J17 relative to that control. Remaining
mismatches: J10/J11/J29 (human partial, predicted no) and J17 (human no, predicted
partial). It resolves the response-format failure route in this run but does not
establish a quality gain. Schema constraints can alter generated content, so the
semantic differences cannot all be attributed to formatting repairs.

Artifacts: `.cache/calitree-tests/vision-neutral-property-strict-development32-20260926/`.
Its `log_directory.json` links the full `logs/exps/` history, execution log, config
and result. Strict output follows the [official Structured Outputs guide](https://developers.openai.com/api/docs/guides/structured-outputs) and [GPT-4.1 support documentation](https://developers.openai.com/api/docs/models/gpt-4.1). It is an opt-in LM engine capability; existing advisory
schema behavior and core decomposition defaults remain unchanged. Refusal and
completion finish reason are retained, and unsupported provider adapters fail
rather than silently downgrade the requested constraint. Offline suite after
this change: 911 passed, 23 skipped, 52 existing warnings.

## User-directed restart

The user subsequently clarified that individual case accuracy, rather than
unseen-case generalization, is the criterion. Further exploration restarts from
each real image pair and its cached original/optimized prompts, fitting explicit
visual criteria with known human-label feedback. That feedback use must remain
visible in the case history. This changes the exploration criterion; it does not
retroactively change the above results or their data usage.
