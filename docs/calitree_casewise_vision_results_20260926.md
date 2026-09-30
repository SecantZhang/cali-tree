# CaliTree AURORA case-by-case vision results (2026-09-26)

These are saved, single-run predictions from the paired 64-case AURORA evaluation. "Direct" applies the optimized prompt to the source/edited image pair; "decomposed" applies its `two_way_vision` policy to the same pair. This is a historical development cohort, not a new manual-canvas run. Each parenthesized value is that **case’s accuracy**: `1` means the prediction matches the human label; `0` means it does not. Invalid decomposition output counts as `0`. A single case has no meaningful percentage accuracy beyond this 0/1 result.

Source results: [`gpt-5.4-mini`](../.cache/calitree-tests/vision-fresh64-mini-20260926/fresh_validation/results.json) and [`gpt-4.1`](../.cache/calitree-tests/vision-fresh64-gpt41-20260926/fresh_validation/results.json).

| Case | Edit instruction | Human label | gpt-5.4-mini: direct → decomposed | gpt-4.1: direct → decomposed |
|---|---|---|---|---|
| N01 | Make the person walk down the stairs | partial | partial (1) → partial (1) | no (0) → invalid (0) |
| N02 | Make him stand up | no | yes (0) → partial (0) | no (1) → no (1) |
| N03 | Open the door | no | yes (0) → yes (0) | yes (0) → yes (0) |
| N04 | Make her close her jacket fully | no | no (1) → partial (0) | no (1) → no (1) |
| N05 | Make them look at the shelf behind them | no | no (1) → partial (0) | no (1) → no (1) |
| N06 | Make the person lift their left leg up | no | no (1) → no (1) | partial (0) → partial (0) |
| N07 | Make her turn to the left | no | no (1) → no (1) | no (1) → no (1) |
| N08 | Show his hands on the plate to arrange the food | no | yes (0) → partial (0) | partial (0) → partial (0) |
| N09 | move the green sphere in front of the red small sphere | no | partial (0) → no (1) | no (1) → no (1) |
| N10 | make the big green rubber cylinder turn purple | no | no (1) → no (1) | no (1) → no (1) |
| N11 | the cyan object turns shiny | no | no (1) → partial (0) | no (1) → partial (0) |
| N12 | the gray metal block becomes matte | no | no (1) → no (1) | no (1) → no (1) |
| N13 | remove the tiny blue matte ball | no | no (1) → no (1) | no (1) → no (1) |
| N14 | Turn the blue cube gray | yes | yes (1) → yes (1) | partial (0) → partial (0) |
| N15 | remove the tiny blue metallic cylinder | no | yes (0) → yes (0) | no (1) → no (1) |
| N16 | remove the tiny blue shiny object | partial | yes (0) → yes (0) | no (0) → partial (1) |
| N17 | Make it look like a renaissance painting | no | no (1) → no (1) | no (1) → no (1) |
| N18 | Turn the image into a drawing made from chalk | no | no (1) → partial (0) | no (1) → no (1) |
| N19 | Change the background to a swamp | no | no (1) → no (1) | no (1) → no (1) |
| N20 | Make this look like a comic book photo | no | yes (0) → yes (0) | partial (0) → partial (0) |
| N21 | Make the photo seem like it was taken at a picnic at a park | no | partial (0) → partial (0) | no (1) → partial (0) |
| N22 | Depict this as if it were a comic book picture | no | yes (0) → partial (0) | partial (0) → partial (0) |
| N23 | Give this image a look inspired by Michelangelo's "David" | no | partial (0) → partial (0) | no (1) → no (1) |
| N24 | Change the background in oil painting | partial | yes (0) → yes (0) | partial (1) → yes (0) |
| N25 | Put both hands around the plate | no | yes (0) → no (1) | partial (0) → no (1) |
| N26 | Move the hand towards the oven knob | no | no (1) → partial (0) | no (1) → no (1) |
| N27 | Open the drawer a little more | no | yes (0) → partial (0) | no (1) → no (1) |
| N28 | Move all the dishes into sink right under the water tab | no | no (1) → partial (0) | no (1) → no (1) |
| N29 | Put the bowl down on the left side | no | no (1) → yes (0) | no (1) → yes (0) |
| N30 | Move the hand towards the handle of the drawer | no | yes (0) → yes (0) | no (1) → no (1) |
| N31 | Open the sandwich maker and place the sandwich inside | no | yes (0) → no (1) | no (1) → no (1) |
| N32 | Open the orange bag further with both hands | no | yes (0) → partial (0) | partial (0) → partial (0) |
| N33 | let the teenage mutant ninja turtle figure drop | no | yes (0) → partial (0) | partial (0) → yes (0) |
| N34 | the white drug bottle is flipped upside down | no | yes (0) → yes (0) | no (1) → no (1) |
| N35 | put the yellow nesquik chocolate powder canister on the right hand of the red towel | partial | partial (1) → partial (1) | no (0) → partial (1) |
| N36 | turn the green-purple pencil case 90 degrees | no | partial (0) → partial (0) | partial (0) → no (1) |
| N37 | transform the black DVD into a white DVD | no | partial (0) → partial (0) | no (1) → no (1) |
| N38 | Swap the positions of the two objects | no | yes (0) → no (1) | yes (0) → yes (0) |
| N39 | Move the white soccer cleats and the white-pink shoes closer to each other | no | yes (0) → partial (0) | no (1) → no (1) |
| N40 | add 1 red towel to the image | no | yes (0) → partial (0) | no (1) → no (1) |
| N41 | change the white couch to a brown couch | no | partial (0) → no (1) | no (1) → no (1) |
| N42 | let there be patties in the pan | partial | no (0) → no (0) | no (0) → no (0) |
| N43 | put banana shaped candles in the candle holder | partial | partial (1) → partial (1) | no (0) → no (0) |
| N44 | change the bed to a bean bag | partial | yes (0) → yes (0) | no (0) → partial (1) |
| N45 | Add a leashed dog to the hydrant | no | no (1) → no (1) | no (1) → partial (0) |
| N46 | Give the woman a helmet | partial | yes (0) → yes (0) | no (0) → partial (1) |
| N47 | Have the dog lick the teddy bear | no | yes (0) → partial (0) | no (1) → invalid (0) |
| N48 | Add a giraffe in the field | yes | yes (1) → yes (1) | yes (1) → yes (1) |
| N49 | Stuffing the paper into the cup | no | partial (0) → partial (0) | yes (0) → partial (0) |
| N50 | Tipping sign over | partial | no (0) → no (0) | no (0) → no (0) |
| N51 | Remove the black marker | no | no (1) → no (1) | no (1) → no (1) |
| N52 | Tear paper apart | no | partial (0) → partial (0) | no (1) → no (1) |
| N53 | Add an orange | no | yes (0) → no (1) | no (1) → no (1) |
| N54 | Putting egg into the bowl | partial | yes (0) → partial (1) | partial (1) → partial (1) |
| N55 | Add lid onto jar | no | partial (0) → partial (0) | no (1) → no (1) |
| N56 | Remove the lid of the left bottle with the hand | no | no (1) → no (1) | no (1) → no (1) |
| N57 | Move the cap to the right of the candle | no | no (1) → no (1) | no (1) → no (1) |
| N58 | Move the book behind the tape | no | no (1) → no (1) | no (1) → no (1) |
| N59 | Move the pot to the right of the chair | partial | no (0) → partial (1) | no (0) → no (0) |
| N60 | Move the pot on the chair | no | partial (0) → partial (0) | no (1) → no (1) |
| N61 | Move the book behind the flower | no | no (1) → no (1) | no (1) → no (1) |
| N62 | Move the can to the left of the knife | no | no (1) → no (1) | no (1) → no (1) |
| N63 | Move the mug to the right of the headphones | no | no (1) → no (1) | no (1) → no (1) |
| N64 | Move the oven mitt under the chair | no | yes (0) → no (1) | no (1) → no (1) |

## Two image-grounded examples

**N31 — “Open the sandwich maker and place the sandwich inside.”** Human label: `no`. For gpt-5.4-mini, the direct optimized prompt said `yes (0)`; decomposition said `no (1)`. Its saved plan separated opening the maker (`complete`) from placing the sandwich inside (`absent`). The sandwich remained outside the maker. For gpt-4.1, both predictions were `no (1)`.

**N29 — “Put the bowl down on the left side.”** Human label: `no`. For both models, the direct optimized prompt said `no (1)` and decomposition said `yes (0)`. The decomposed plan interpreted “left side” relative to the bowl’s earlier position and recorded that condition as `complete`, whereas the direct evaluation judged that the bowl was in the sink rather than on the left side. This shows a concrete case-level regression.

The predictions, validity flags, rationales, compiled plans, observations, and image paths are retained in the source result JSON files above.
