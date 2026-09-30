# Every case: two fresh observations

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

## Every condition

| Case | Condition | Run 1 | Run 2 |
|---|---|---|---|
| J01 | curtains_closed_state | partial | transport_error |
| J01 | person_action_association | absent | absent |
| J01 | scene_preservation | partial | partial |
| J02 | cond1 | partial | partial |
| J02 | cond2 | absent | absent |
| J03 | cond1 | unknown | unknown |
| J03 | cond2 | absent | absent |
| J04 | stand_up_upright | complete | complete |
| J04 | looking_at_hands | absent | absent |
| J04 | scene_preservation | absent | absent |
| J05 | c1 | absent | absent |
| J05 | c2 | absent | absent |
| J06 | c1 | absent | absent |
| J06 | c2 | absent | absent |
| J07 | remove_green_shiny_block | absent | absent |
| J07 | preserve_scene_except_target | absent | absent |
| J08 | c1 | absent | absent |
| J08 | c2 | absent | absent |
| J09 | c1 | partial | partial |
| J09 | c2 | partial | partial |
| J10 | cartoon_style_applied | partial | partial |
| J10 | source_scene_preserved | complete | complete |
| J11 | c1 | partial | partial |
| J11 | c2 | complete | complete |
| J12 | style_cubism_applied | absent | absent |
| J12 | source_scene_preserved | partial | transport_error |
| J13 | cond1 | complete | complete |
| J13 | cond2 | partial | partial |
| J14 | cond1 | partial | absent |
| J14 | cond2 | complete | complete |
| J15 | cond1 | partial | partial |
| J15 | cond2 | partial | unknown |
| J17 | cond_1 | unknown | unknown |
| J17 | cond_2 | unknown | absent |
| J17 | cond_3 | absent | absent |
| J18 | add_2_white_square_saucers | partial | partial |
| J18 | preserve_source_scene | absent | absent |
| J19 | remove_2_sharks | absent | absent |
| J19 | scene_preservation | partial | partial |
| J20 | cond1-object-addition | transport_error | absent |
| J20 | cond2-spatial-relation | absent | absent |
| J20 | cond3-target-identification | absent | absent |
| J20 | cond4-scene-preservation | partial | partial |
| J21 | cond1 | complete | complete |
| J21 | cond2 | unknown | absent |
| J21 | cond3 | absent | absent |
| J22 | catcher_identification | transport_error | complete |
| J22 | catcher_laughing | transport_error | complete |
| J22 | scene_preservation | partial | partial |
| J23 | toilet_bowl_identification | complete | complete |
| J23 | lid_presence_on_toilet | absent | transport_error |
| J23 | scene_preservation | partial | absent |
| J24 | seat_down_action | absent | absent |
| J24 | scene_preservation | complete | complete |
| J25 | flip_bottle_upside_down | absent | absent |
| J25 | preserve_source_scene | partial | partial |
| J26 | cond1 | absent | absent |
| J26 | cond2 | complete | complete |
| J26 | cond3 | complete | complete |
| J27 | cloth-unfolding | partial | partial |
| J27 | scene-preservation | partial | partial |
| J28 | move_cup_away_from_pen | absent | unknown |
| J28 | scene_preservation | partial | partial |
| J29 | move_bowl_left_of_flower | partial | partial |
| J29 | scene_preservation | partial | partial |
| J30 | move_can_right_of_knife | unknown | unknown |
| J30 | scene_preservation | absent | absent |
| J31 | move_bowl_to_armchair | absent | absent |
| J31 | preserve_scene_except_bowl_move | partial | partial |
| J32 | c1 | absent | unknown |
| J32 | c2 | partial | partial |
| N01 | C1 | absent | unknown |
| N01 | C2 | partial | partial |
| N04 | jacket_fully_closed | unknown | unknown |
| N04 | preserve_source_scene | absent | absent |
| N14 | target_cube_gray | complete | complete |
| N14 | preserve_source_scene | partial | partial |
| N16 | remove_target | complete | complete |
| N16 | preserve_scene | partial | partial |
| N20 | comic_book_visual_treatment | complete | complete |
| N20 | source_scene_preservation | complete | complete |
| N24 | background_oil_painting | complete | complete |
| N24 | preserve_source_scene | complete | complete |
| N25 | both_hands | absent | absent |
| N25 | preserve_source_scene | complete | partial |
| N31 | open_sandwich_maker | absent | absent |
| N31 | sandwich_inside_maker | absent | absent |
| N31 | preserve_source_scene | partial | partial |
| N35 | c1 | unknown | unknown |
| N35 | c2 | partial | partial |
| N38 | swap_positions | absent | absent |
| N38 | preserve_source_scene | complete | complete |
| N42 | patties_in_pan | absent | complete |
| N42 | preserve_source_scene | complete | complete |
| N43 | banana_shaped_candles | absent | absent |
| N43 | placement_in_candle_holder | partial | partial |
| N43 | preserve_source_scene | complete | partial |
| N46 | helmet_on_source_woman | complete | complete |
| N46 | preserve_source_scene | partial | partial |
| N48 | giraffe_added | complete | complete |
| N48 | source_scene_preserved | complete | complete |
| N50 | tipping_sign | absent | absent |
| N50 | preserve_source_scene | partial | partial |
| N54 | egg_added | complete | complete |
| N54 | scene_preservation | partial | partial |
| N57 | cap_identity | absent | absent |
| N57 | cap_position | unknown | unknown |
| N57 | scene_preservation | absent | absent |
| N59 | C1 | absent | absent |
| N59 | C2 | partial | partial |
| N64 | C1 | absent | absent |
| N64 | C2 | complete | complete |
