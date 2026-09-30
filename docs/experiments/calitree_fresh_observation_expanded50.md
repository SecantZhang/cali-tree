# Fresh observation reliability: 50-case expansion

The subsequent [five-repeat extension](calitree_five_repeat_agreement.md) preserves this run and adds three fresh draws to the same frozen criteria.

## Frozen protocol

The user expanded the requested sample to 50 cases before the prepared 12-case run made any API calls. This study retains the simple frozen-criterion checker and GPT-6 Luna; it adds no J16-specific algorithms.

- 31 existing J cases (J01–J32 except user-quarantined J16) retain their saved criteria unchanged.
- 19 additional N cases receive one text-only Luna compilation using their cached optimized prompt and instruction, without images, human annotations or earlier predictions. The existing compiler template/schema is reused; no fitting or repairs.
- All 50 cases are evaluated twice with fresh image-based condition calls. Labels stay local and provisional.
- Four historical plans (J01/J09/J22/J29) used earlier case-label fitting feedback. Report this group separately; new inference calls receive no feedback. New-plan versus historical-plan groups have different compiler provenance.
- Selected across all eight AURORA task families, deliberately adding partial/yes examples as well as failures. Selection used task/instruction and provisional label diversity, not new model outcomes; this is not a random or balanced test of generalization.
- Official api.openai.com; gpt-6-luna; reasoning none; temperature zero; one HTTP attempt per call, no schema repair, no model fallback.
- Upper bound: 19 compiler calls (2,048 tokens each), plus 446 observation calls (1,024 tokens each), totaling **465 calls / 495,616 completion tokens maximum**. The worst-case bound permits eight conditions in each new plan; the actual plan count determines a lower observation count.
- Transport errors/invalid outputs remain durable outcomes and are not resampled. Continue independent planned checks after isolated failures; stop after three consecutive transport failures or budget exhaustion. Interrupted job reservations are not silently retried on restart.
- Unknown, invalid, transport-error and unexecuted slots cannot become negative training targets. The conservative reducer returns unresolved if any condition is not known.
- Per-condition scheduling uses the exact same checker prompt, schema, media and condition payload as the smaller runner; an offline equivalence test verifies this. It changes failure isolation and bookkeeping, not the decomposition method.

Provisional label counts: {'no': 32, 'partial': 15, 'yes': 3}. Task counts: {'ag': 6, 'clevr': 6, 'emu': 6, 'epic': 5, 'kubric': 6, 'magicbrush': 8, 'something': 6, 'whatsup': 7}.

## Every selected case

| ID | Task | Instruction | Provisional label | Criteria origin |
|---|---|---|---|---|
| J01 | ag | Make them close the curtains | no | historical_frozen (earlier label feedback) |
| J02 | ag | Make her grab the book from the shelf | no | historical_frozen |
| J03 | ag | Close the laundry machine door | no | historical_frozen |
| J04 | ag | Make them stand up fully upright looking at their hands | no | historical_frozen |
| J05 | clevr | the tiny yellow cylinder turns brown | no | historical_frozen |
| J06 | clevr | make the purple sphere smaller | no | historical_frozen |
| J07 | clevr | remove the green shiny block | no | historical_frozen |
| J08 | clevr | the tiny yellow object turns purple | no | historical_frozen |
| J09 | emu | I want this as a watercolor | partial | historical_frozen (earlier label feedback) |
| J10 | emu | Make the image look like a cartoon | partial | historical_frozen |
| J11 | emu | turn this photo into a picasso painting | partial | historical_frozen |
| J12 | emu | Change the style to Cubism | no | historical_frozen |
| J13 | epic | Pick up the egg with the right hand | yes | historical_frozen |
| J14 | epic | Lift the frying pan up | no | historical_frozen |
| J15 | epic | Let the paper towel fall down | no | historical_frozen |
| J17 | kubric | shift the position of the vintage metal alarm clock above the toy squirrel | no | historical_frozen |
| J18 | kubric | add 2 white square saucer to the scene | no | historical_frozen |
| J19 | kubric | remove 2 shark from the image | no | historical_frozen |
| J20 | kubric | place the CARSII on the right of the green-purple pencil case | no | historical_frozen |
| J21 | magicbrush | Put a dragonfly on the dog's ear | no | historical_frozen |
| J22 | magicbrush | make the catcher laugh | partial | historical_frozen (earlier label feedback) |
| J23 | magicbrush | Let the toilet bowl have a lid | no | historical_frozen |
| J24 | magicbrush | Put down the seat | no | historical_frozen |
| J25 | something | Flip the bottle upside down | no | historical_frozen |
| J26 | something | Drop the glass on top of the pills | no | historical_frozen |
| J27 | something | Unfold cloth | no | historical_frozen |
| J28 | something | Moving cup away from pen | no | historical_frozen |
| J29 | whatsup | Move the bowl to the left of the flower | partial | historical_frozen (earlier label feedback) |
| J30 | whatsup | Move the can to the right of the knife | no | historical_frozen |
| J31 | whatsup | Move the bowl on the armchair | no | historical_frozen |
| J32 | whatsup | Move the sunglasses under the chair | no | historical_frozen |
| N01 | ag | Make the person walk down the stairs | partial | new_luna |
| N04 | ag | Make her close her jacket fully | no | new_luna |
| N14 | clevr | Turn the blue cube gray | yes | new_luna |
| N16 | clevr | remove the tiny blue shiny object | partial | new_luna |
| N20 | emu | Make this look like a comic book photo | no | new_luna |
| N24 | emu | Change the background in oil painting | partial | new_luna |
| N25 | epic | Put both hands around the plate | no | new_luna |
| N31 | epic | Open the sandwich maker and place the sandwich inside | no | new_luna |
| N35 | kubric | put the yellow nesquik chocolate powder canister on the right hand of the red towel | partial | new_luna |
| N38 | kubric | Swap the positions of the two objects | no | new_luna |
| N42 | magicbrush | let there be patties in the pan | partial | new_luna |
| N43 | magicbrush | put banana shaped candles in the candle holder | partial | new_luna |
| N46 | magicbrush | Give the woman a helmet | partial | new_luna |
| N48 | magicbrush | Add a giraffe in the field | yes | new_luna |
| N50 | something | Tipping sign over | partial | new_luna |
| N54 | something | Putting egg into the bowl | partial | new_luna |
| N57 | whatsup | Move the cap to the right of the candle | no | new_luna |
| N59 | whatsup | Move the pot to the right of the chair | partial | new_luna |
| N64 | whatsup | Move the oven mitt under the chair | no | new_luna |

## Outputs and interpretation

Report all cases, per-condition repeat statuses, known coverage, instability, provisional label agreement and costs. Compare fresh anchors to the earlier pilot descriptively, without selecting a preferred draw. A visual-description audit is assistant inspection, not independent human concept gold. Consistency alone cannot verify accuracy, and disagreement alone cannot justify changing labels or quarantining cases. The broad assumption remains unverified until these distinctions are addressed.

The experiment does not learn a tree, refine criteria or claim generalization. Review the resulting failures as patterns rather than adding mechanisms around individual cases.

## Reproduction

```bash
.venv/bin/python -m run.calitree_observation50 \
  --output-dir logs/exps/260929-22:30:00-exps
# Add --live for the authorized bounded run.
```

The default is a no-call preflight. Manifest hashes bind source code, original image bytes, prompts and conditions. `jobs/*.json` stores every planned attempted compiler/check slot, including partial and failed attempts; `frozen_plans.json` is saved before observations. Full requests, returned model IDs and usage are in `llm-histories.log`. `results.json` includes all cases.

Offline verification before execution: 17 focused tests passed, including no-label compilation, exact checker-payload equivalence, durable failure isolation, resume without resampling, invalid compiler retention and unknown handling.

## Completed results

**The expanded test shows useful repeatability, but does not verify that every
exported condition is a reliable independent training feature.** All 50 selected
cases reached both scheduled observation passes. The actual plans contained 112
conditions: 19 compiler calls plus 224 checker calls, **243 attempts total**.
All 19 compilations and 218 observations succeeded; six isolated transport failures
were retained without retry. All successful outputs were valid structured responses.

| Measurement | Result | Meaning |
|---|---:|---|
| Paired conditions with two valid responses | 106/112 | Six pairs lack one response because of transport errors. |
| Identical status across valid pairs | **95/106 (89.6%)** | Includes stable unknown; not a correctness score. |
| Consistent and known condition pairs | **89/112 (79.5%)** | Requires both responses and excludes unknown. |
| Known completed observations | **200/218 (91.7%)** | 18 completed observations are unknown; another six attempts failed. |
| Cases with a complete, stable, known condition vector | **30/50** | Candidate features for further review, not automatically approved training cases. |
| Same final output with all underlying responses available | **38/45** | Six are stable unresolved; five other cases have a transport-affected pair. |
| Same resolved final output with all responses available | **32/50** | Two of these hide a condition-status change. |
| Resolved case predictions | **78/100** | Remaining 22 comprise 17 model-unknown draws and five transport-affected draws. |
| Agreement with provisional human reference | **57/100 planned case draws**, or **57/78 resolved** | Annotation agreement only, not verified accuracy. |

This sample has 32 no, 15 partial and three yes reference labels. Agreement by
reference group was 40/64 no draws, 15/30 partial draws and 2/6 yes draws. Do not
interpret these selected, repeated cases as a population ranking or generalization
estimate. Human references were not revised or treated as unquestionable ground truth.

### Criteria provenance

| Criteria group | Cases | Stable / valid condition pairs | Stable and known / planned condition pairs | Resolved case draws | Reference agreement / planned draws |
|---|---:|---:|---:|---:|---:|
| Historical, no case-specific feedback | 27 | 51/58 | 48/61 | 41/54 | 35/54 |
| Historical, prior case-label feedback | 4 | 7/7 | 7/10 | 6/8 | 6/8 |
| Newly compiled once by Luna | 19 | 37/41 | 34/41 | 31/38 | 16/38 |

These groups differ in cases, prompts and compiler history. Their rates do not
isolate the effect of compiler model or label feedback. Historical plans were
reused unchanged; no feedback was supplied in this run.

### What the case traces establish

The assistant inspected the source/edit contact sheets for all 50 cases and read
selected full traces, including concrete inconsistencies and label disagreements.
This is a qualitative audit, not independent human concept annotation or a measured
concept-accuracy rate. The trace files retain all model descriptions for review.

1. **Repeatability can hide a scope error — J07.** The removal check correctly sees
   the shiny green block still present. In both repeats, the *separate preservation*
   check describes the rest of the scene as largely recognizable but returns absent
   because the block was not removed. Its own condition explicitly excludes that
   block. The final no agrees with the human reference, and both categorical features
   are stable, yet the preservation feature is not measuring its declared scope.
2. **Separate checks can contradict each other's observations — J24.** Both action
   checks describe the edited toilet seat as raised; both preservation checks describe
   it as lowered. This is an internal descriptive inconsistency regardless of which
   interpretation an independent reviewer ultimately accepts. The final no repeats
   and agrees with the reference, masking the inconsistency.
3. **A decisive measurement can reverse — N42.** The pan-content check changes from
   absent to complete. One repeat does not recognize patties; the other recognizes
   patty-like food already present. The final output changes **no → yes** with the
   same images and frozen criteria. Its provisional human reference is partial;
   neither that reference nor a preferred model draw is selected as the answer.
4. **Compilation can add a questionable requirement — N43.** The new placement
   criterion treats partially occupying the holder as incomplete. Both placement
   responses penalize empty candle-holder arms, although the instruction specifies
   banana-shaped candles, not filling every arm. The shape checker also says the
   candles are not banana-shaped while placement descriptions call them banana-shaped.
   This suggests both a criterion-scope question and inconsistent property descriptions;
   repeating checks does not itself validate compilation fidelity.
5. **Correct visible action and final annotation agreement are different — J13/N14.**
   The egg pickup and blue-to-gray cube change are consistently recognized as complete.
   Preservation penalties give partial in both repeats against the provisional yes
   references. The appropriateness of those penalties needs policy/annotation review;
   a disagreement alone is not proof of a visual mistake or a bad human label.
6. **Some simple distinctions repeat usefully.** J05/J06 identify wrong-object or
   missing-target edits; J25 keeps the bottle upright rather than inferring a flip;
   N31 separately fails opening the sandwich maker and placing the sandwich inside;
   N48 consistently recognizes the added giraffe and preserved field. These are useful
   starting examples, with the same limitations on independent concept verification.

The 11 observed categorical changes are J14 lift (partial→absent), J15 preservation
(partial→unknown), J17 above relation (unknown→absent), J21 ear placement
(unknown→absent), J23 preservation (partial→absent), J28 cup movement
(absent→unknown), J32 sunglasses placement (absent→unknown), N01 stair action
(absent→unknown), N25 preservation (complete→partial), N42 patties (absent→complete),
and N43 preservation (complete→partial). Seven change the final output in otherwise
fully observed cases: J14, J15, J21, J28, J32, N01 and N42. J17 still has another
unknown, N25/N43 retain another absent, and J23 also has a separate transport failure.

The earlier three anchors behave comparably in this run: J03 unresolved/unresolved,
J10 partial/partial, and J13 partial/partial. J03 preservation is now absent in both
new repeats, while its door state remains unknown. The earlier unknown preservation
response is retained as historical evidence, not replaced by these new results.

### Readiness decision

**Promising for a small, manually audited feature/tree prototype; not verified for
unchecked training on the whole set.** Even the 30 stable, known case vectors need
semantic review: J07 and J24 are among them. Do not equate a resolved/stable vector
with a trustworthy one, or a human-label mismatch with a case that should be removed.

Keep the simple architecture. Before using an affected feature, check that it measures
only its declared condition, distinguishes visible failure from unavailable evidence,
and applies the intended preservation tolerance. Treat uncertain annotations as review
candidates and retain their provenance. No case-specific detector, crop pipeline,
criterion repairs, automatic relabeling, or new quarantine was introduced by this run.
A broader tree-training claim would additionally require shared-feature alignment;
this observation experiment does not test that step.

### Usage and verification

Successful responses reported **299,345 prompt tokens and 41,071 completion tokens**.
Six failed attempts retain 6,144 completion tokens of conservative reservations,
for a ledger total of 47,215 used/reserved completion tokens, well within the cap.
Using the previously verified standard uncached rates of $0.10/M input and $0.50/M
output gives about **$0.0505 for successful requests**, excluding unknown failed-request
billing and cache discounts. This is an estimate, not an invoice. See the
[Luna model documentation](https://developers.openai.com/api/docs/models/gpt-6-luna).

Offline verification: **55 focused tests passed** for the new driver, smaller driver,
budgets, provider transport and structured output. A saved-call audit verified all
source/image hashes, unchanged historical plans, model IDs, exact allowlisted checker
payloads, label-free compiler inputs, single-attempt transport and budget limits.
All 243 request attempts are accounted for; no failure was silently retried or erased.
`git diff --check` passed. The production decomposition executor remains unchanged.

Run directory: `logs/exps/260929-22:30:00-exps/`. Artifacts include `manifest.json`,
`frozen_plans.json`, all `jobs/*.json`, `llm-histories.log`, `budget.json`, `results.json`,
`audit.json`, `observations.csv`, `case_table.md`, `traces.md` and ten contact sheets.
The saved `analyze_saved_calls.py` reconstructs the exports without model calls.

## All 50 case outputs

Human labels are provisional references; this table measures agreement, not adjudicated accuracy. Unknown and failed checks produce unresolved.

| Case | Task | Instruction | Human reference | Run 1 | Run 2 | Stable known conditions |
|---|---|---|---|---|---|---|
| J01 | ag | Make them close the curtains | no | no | unresolved | 2/3 |
| J02 | ag | Make her grab the book from the shelf | no | no | no | 2/2 |
| J03 | ag | Close the laundry machine door | no | unresolved | unresolved | 1/2 |
| J04 | ag | Make them stand up fully upright looking at their hands | no | no | no | 3/3 |
| J05 | clevr | the tiny yellow cylinder turns brown | no | no | no | 2/2 |
| J06 | clevr | make the purple sphere smaller | no | no | no | 2/2 |
| J07 | clevr | remove the green shiny block | no | no | no | 2/2 |
| J08 | clevr | the tiny yellow object turns purple | no | no | no | 2/2 |
| J09 | emu | I want this as a watercolor | partial | partial | partial | 2/2 |
| J10 | emu | Make the image look like a cartoon | partial | partial | partial | 2/2 |
| J11 | emu | turn this photo into a picasso painting | partial | partial | partial | 2/2 |
| J12 | emu | Change the style to Cubism | no | no | unresolved | 1/2 |
| J13 | epic | Pick up the egg with the right hand | yes | partial | partial | 2/2 |
| J14 | epic | Lift the frying pan up | no | partial | no | 1/2 |
| J15 | epic | Let the paper towel fall down | no | partial | unresolved | 1/2 |
| J17 | kubric | shift the position of the vintage metal alarm clock above the toy squirrel | no | unresolved | unresolved | 1/3 |
| J18 | kubric | add 2 white square saucer to the scene | no | no | no | 2/2 |
| J19 | kubric | remove 2 shark from the image | no | no | no | 2/2 |
| J20 | kubric | place the CARSII on the right of the green-purple pencil case | no | unresolved | no | 3/4 |
| J21 | magicbrush | Put a dragonfly on the dog's ear | no | unresolved | no | 2/3 |
| J22 | magicbrush | make the catcher laugh | partial | unresolved | partial | 1/3 |
| J23 | magicbrush | Let the toilet bowl have a lid | no | no | unresolved | 1/3 |
| J24 | magicbrush | Put down the seat | no | no | no | 2/2 |
| J25 | something | Flip the bottle upside down | no | no | no | 2/2 |
| J26 | something | Drop the glass on top of the pills | no | no | no | 3/3 |
| J27 | something | Unfold cloth | no | partial | partial | 2/2 |
| J28 | something | Moving cup away from pen | no | no | unresolved | 1/2 |
| J29 | whatsup | Move the bowl to the left of the flower | partial | partial | partial | 2/2 |
| J30 | whatsup | Move the can to the right of the knife | no | unresolved | unresolved | 1/2 |
| J31 | whatsup | Move the bowl on the armchair | no | no | no | 2/2 |
| J32 | whatsup | Move the sunglasses under the chair | no | no | unresolved | 1/2 |
| N01 | ag | Make the person walk down the stairs | partial | no | unresolved | 1/2 |
| N04 | ag | Make her close her jacket fully | no | unresolved | unresolved | 1/2 |
| N14 | clevr | Turn the blue cube gray | yes | partial | partial | 2/2 |
| N16 | clevr | remove the tiny blue shiny object | partial | partial | partial | 2/2 |
| N20 | emu | Make this look like a comic book photo | no | yes | yes | 2/2 |
| N24 | emu | Change the background in oil painting | partial | yes | yes | 2/2 |
| N25 | epic | Put both hands around the plate | no | no | no | 1/2 |
| N31 | epic | Open the sandwich maker and place the sandwich inside | no | no | no | 3/3 |
| N35 | kubric | put the yellow nesquik chocolate powder canister on the right hand of the red towel | partial | unresolved | unresolved | 1/2 |
| N38 | kubric | Swap the positions of the two objects | no | no | no | 2/2 |
| N42 | magicbrush | let there be patties in the pan | partial | no | yes | 1/2 |
| N43 | magicbrush | put banana shaped candles in the candle holder | partial | no | no | 2/3 |
| N46 | magicbrush | Give the woman a helmet | partial | partial | partial | 2/2 |
| N48 | magicbrush | Add a giraffe in the field | yes | yes | yes | 2/2 |
| N50 | something | Tipping sign over | partial | no | no | 2/2 |
| N54 | something | Putting egg into the bowl | partial | partial | partial | 2/2 |
| N57 | whatsup | Move the cap to the right of the candle | no | unresolved | unresolved | 2/3 |
| N59 | whatsup | Move the pot to the right of the chair | partial | no | no | 2/2 |
| N64 | whatsup | Move the oven mitt under the chair | no | no | no | 2/2 |


## Detailed artifacts

- [Every condition and case](../../logs/exps/260929-22:30:00-exps/case_table.md)
- [Full condition traces](../../logs/exps/260929-22:30:00-exps/traces.md)
- [Machine-readable audit](../../logs/exps/260929-22:30:00-exps/audit.json)
- [All observation rows](../../logs/exps/260929-22:30:00-exps/observations.csv)
