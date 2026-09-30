# Expanded fresh-observation check: 12 cases

**Superseded before live execution:** the user requested [50 cases](calitree_fresh_observation_expanded50.md). This 12-case preparation made zero model calls.

## Frozen protocol

User requested a modest expansion of the three-case Luna pilot. This run retains
the same frozen criteria, model settings and conservative reducer. There is no
prompt repair, optimization, new decomposition variant, or retrospective case selection.

- Model: `gpt-6-luna`, reasoning none, temperature 0, strict JSON.
- Cases: J02, J03, J05, J06, J07, J10, J11, J13, J17, J18, J25, J30.
- Scope: four human-action/orientation cases, three synthetic object-attribute edits,
  two style edits, two spatial edits and one count/addition edit.
- Three prior anchors (J03/J10/J13), nine additions. All receive new calls in this run.
- 25 frozen conditions × two fresh repetitions = **50 requests maximum**.
- 1,024 completion tokens per request; **51,200 completion tokens maximum**.
- One HTTP attempt per request, zero schema repairs; stop on transport failure.
- Independent repeat checkpoints. No label, previous prediction, or previous observation
  is sent to the checker. J16 remains excluded by explicit user review.

The cohort is selected for task variety, not randomly sampled. All retained plans
report no case-specific fitting feedback; historical category prompts were optimized.
The provisional labels comprise nine no, two partial and one yes. This imbalance
and the selected historical cohort prevent population/generalization claims. Report
case-level outputs and conditions rather than treating overall label agreement as
verified accuracy. A visibly poor edit is a useful failure example and is not
excluded simply for being unusual; ambiguous evidence remains unknown.

Compare paired categorical states and known coverage separately. A stable unknown
is not a resolved feature. Check every saved description against the images, with
explicitly limited assistant audit rather than independent concept gold. Review
whether apparent stability hides incorrect source identification or rule application.
No criterion or target will be changed after results are seen.

## Pre-run visual audit

The three contact sheets in the run directory show source on the left and edit on
the right; they are inspection aids only. The model receives original image bytes.

| Case | Visible facts and uncertainty to inspect |
|---|---|
| J02 | Woman remains near monitor/mug; added or altered books and changed framing. A clear book grasp is not evident in the displayed edit. Hand visibility limits action inference. |
| J03 | Open round laundry door/person replaced by blue rectangular appliances. Distinguish missing door referent from visible scene replacement. |
| J05 | Original small yellow cylinder at rear-left disappears; foreground objects are substantially changed. Track source identity rather than treating any brown object as success. |
| J06 | Foreground purple sphere remains large; rear gray sphere becomes purple. Track the original purple sphere separately from color changes elsewhere. |
| J07 | Shiny green block on the right remains. Other colors/lighting change slightly. |
| J10 | Cartoon-like wall picture appears in a predominantly photographic room. |
| J11 | Picasso-like face pictures appear in train windows while people and carriage remain photographic. Global style versus embedded pictures is a scoring-policy boundary. |
| J13 | Right hand holds an enlarged egg; kitchen layout remains recognizable with framing/body-position changes. |
| J17 | Source floor scene with clock/toy is replaced by a rendered wall-and-toys scene. A new clock appears high-left, but source-object continuity is doubtful. |
| J18 | Original dish/floor scene is replaced by white angular forms against a dark background. Whether those forms are saucers is uncertain; scene replacement is visible. |
| J25 | Bottle remains upright, cap above base. Labels/details shift. |
| J30 | Edit adds text, changes framing and can appearance; original knife is not clearly identifiable. Do not infer its position from the requested instruction. |

These observations were recorded before new model calls. They do not override the
saved condition definitions or constitute adjudicated human labels.

## Reproduction and evidence

```bash
.venv/bin/python -m run.calitree_observation_reliability \
  --output-dir logs/exps/260929-22:20:26-exps --repeats 2 \
  --case J02 --case J03 --case J05 --case J06 --case J07 --case J10 \
  --case J11 --case J13 --case J17 --case J18 --case J25 --case J30
```

Add `--live` for the bounded live execution. The default performs no model calls.
The existing runner, source/image hashes, artifact bindings and uncertain-case
registry checks are unchanged from the smaller pilot. The dry run has saved the
manifest. Results will be reported here after execution.
