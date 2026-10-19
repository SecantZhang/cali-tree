# CaliTree advisor demo

There are now two offline presentations:

- **[Six-case intuitive walkthrough](six-case-demo.html)** — a short, illustrated algorithm explanation with entirely synthetic examples. Start here to introduce the idea.
- **[Twelve-case research walkthrough](calitree-demo.html)** — actual development images, the current v11 merged root and seven recorded merges, plus the earlier M2 selection/review/support/audit artifacts for comparison.

Open **[calitree-demo.html](calitree-demo.html)** in a browser. It is one self-contained file, including all images, code, and data. No installation, server, network, credentials, or model calls are needed. Copy this file to another computer if useful.

The multi-file editable version starts at `index.html`. Source files are `app.js`, `style.css`, and `build_demo.py`; `data.js`, `media/`, and `calitree-demo.html` are generated exports.

## Current merging update: M4 skipped, M5–M7 completed

### Direct 8 → 4 → 2 → 1 illustration

In the full demo, click **Open 8 → 4 → 2 → 1** on the System map, or open **Recorded merging → 8 → 4 → 2 → 1**. Opening the HTML with `#merging` also enters this illustration directly.

- **Play** replays all three balanced rounds and stops at one root. **Merge 8 → 4**, then **Merge 4 → 2**, then **Merge 2 → 1** advances manually; Back and Reset restore earlier stages.
- The current policies are highlighted; upcoming outputs are unrevealed, and previous policies fade. The diagram pans to the active round on narrow screens.
- The round frontiers are the actual selected eight seeds, four twelve-source parents (P1/P2/P4/P5), two twenty-four-source parents (P3/P6), and root P7. Counts are derived from the saved lineage rather than invented pairings.
- Each stage retains the same 48 distinct sources. Own-cohort fitting totals are **38/48 → 44/48 → 47/48 → 46/48**; these are not scores of a routed inference system. The final stage explains the one-case compression tradeoff.
- Click any revealed **S1–S8 / P1–P7** cell to open the detailed merge inspector. Cells in **Recorded construction** open the same inspector. Closing it returns focus to the selected cell; opening it pauses playback.
- **Before / after trees** displays the exact saved child A, child B, and merged parent policies. Select any original training case to highlight its paths in all three; **Start at root → Next predicate** evaluates them step by step. Expand a tree for readability, zoom/pan, and click a node for its complete predicate and original source support. Outside-child predictions are explicitly labeled cross-transfer probes.
- **Prediction changes** lists every original union slot with reference, owning child, before and after outputs, and corrected/lost/unchanged status. Before correctness always uses the original owning child, never the best child. Filters isolate changed outputs, corrected cases, lost correctness, and unresolved cases.
- **Rules & reuse** lists every exact terminal clause, label counts, source examples and distinct-instruction support. Compare inherited versus new predicate vocabularies and exact ordered clause reuse; predicate reuse does not imply preserved decisions.
- **Sources & evidence** contains the saved training instructions, bound check questions/identities, normalized source/edited evidence and semantic interpretations. The missing G3C05 observation stays unresolved and in the denominator. No training images are added.
- **Acceptance & search** exposes actual retention gates, pair score/transfer probes, recorded refinement attempts, selected search metadata/limits and candidate evaluations. **Raw artifacts** includes the exact portable policies, identities, source paths/hashes and saved verification.
- Seeds have no incoming merge: clicking one shows its original fitted tree, its sibling and its first recorded parent. No unrecorded pre-fit tree is invented. The inspector’s layer selector reaches all fifteen saved cells.

`merge-rounds.js` and `merge-inspector.js` implement these views and is embedded in the standalone HTML. This is a round-based replay of the selected construction, not a new fitting run or a simulation of all proposal trials.

The current full demo follows the completed router-free reuse-first study in **CaliTree Dataset Preparation**, documented in `docs/calitree_router_free_union_merging.md`. It loads the frozen package in `examples/calitree_union_reuse_v11` and defaults to its selected **46/48 local / 10/12 development** root. Earlier M2 stays available as a separate **44/48 / 9/12** comparison.

**Recorded merging** replaces the old synthetic merge laboratory. Its construction is **8 six-source semantic seeds → 4 twelve-source parents → 2 twenty-four-source parents → 1 forty-eight-source root**. The fifteen-node training-lineage diagram is distinct from the twenty-seven-node deployed rule tree. Select Seeds or steps 1–7, click construction nodes, and switch to **Selected policy tree** to inspect the actual rules of that parent.

- **M4:** deliberately omitted. The final judge uses one root, with no specialist router, training-batch selection, child vote, or training membership lookup.
- **M5:** rank pairs by predicate overlap, operation overlap, and mean mutual-transfer macro-F1. Shared mistakes are recorded separately.
- **M6:** relearn against original references on the exact deduplicated descendant union. Reuse child predicates first; try bounded additions of up to four generic predicates; disclose a full-grammar repair if necessary.
- **M7:** search balanced binary unions, retain up to two policies per union, and select only complete 48-source roots. Prefer qualified child-only reuse before bounded refinement or full-grammar repair, without using development labels.

The actual acceptance gates are strictly above 90% union agreement (missing evidence retained), no class collapse for classes with at least two reference sources, at least two sources and instruction texts per terminal rule, written-path consistency, complete lineage, and at most `max(1, floor(child_size/10))` additional errors on either immediate child cohort. These are local fitting/retention gates, not separate-validation evidence.

The seven selected union fits are **11/12, 11/12, 24/24, 11/12, 11/12, 23/24, and 46/48**. Five lower-level merges use full-grammar repair; one uses bounded refinement; only the final root uses child predicates alone. Its eleven used predicates come from sixteen available child predicates. The final merge changes 47/48 combined child correctness to 46/48, within its retention allowance, while reducing nineteen rules to fourteen and 36 nodes to 27. Ten root terminal rules have examples from both immediate children; not every rule must span both.

**M5–M7 algorithm** exposes real transfer diagnostics and the sealed search protocol. **Controls & limits** compares the earlier M2, fresh-refit control (47/48 locally, 7/12 development), and selected reuse-first root. Balanced-half grouping failed to complete a qualifying hierarchy under the inspected bounded search. Three training Yes decisions retain cached missing-endpoint/incidental-progress conflicts; the demo lists G1C09, G3C12, and G4C12 explicitly. Structural portability does not prove semantic correctness. The two current development errors are H01 and H07, both No references predicted Partial.

The exporter independently replays every selected child/parent prediction and terminal-rule support, the seven recorded union gates and pair diagnostics, all 48 training/root predictions, all twelve development/root traces, and the fresh-refit control scores. It checks the frozen package hashes and never refits a parent or reads the final fifty-case records. The saved study verification reports 969 tests passed, 23 skipped, and 515 equivalent-check probes; those saved audit counts are distinct from the demo’s own tests.

To update only the full demo and preserve the separate six-case teaching file:

```sh
.venv/bin/python demos/calitree_meeting/build_demo.py --full-only
node demos/calitree_meeting/check_demo.cjs
```

`merge-view.js` renders the recorded study and is embedded in the standalone full HTML. The six-case teaching file remains a separate, explicitly synthetic lesson; its earlier illustrative merge discussion is not a report of this v11 experiment.

## Completed M2 update

The completion report in **CaliTree Dataset Preparation** identifies the reviewed v8 policy already present on `codex/decision-program-optimizer` at `6bff6524`. No new policy or replacement predictions were invented for this update. The full demo now explicitly presents M2 as completed for **rule portability and greater-than-90% local agreement**, with:

- 44/48 local agreement, including the missing observation in the denominator.
- The 47/48 deeper fit → 46/48 compact selection → 44/48 reviewed deployment history.
- Fourteen terminal rules and their distinct-source/distinct-instruction support examples.
- The saved 147-test verification report, 515 equivalent-check probes with zero changes, independent prediction replay, and source-ID/order invariance.
- Explicit scope: semantic interpretation held fixed for the check probes; statistical transfer, new LLM extraction robustness, and M5–M9 semantic hierarchy validation remain separate.

In **Batch calibration → M2 verification & support**, expand any of the fourteen rules. Its support examples belong to audit metadata; runtime prediction never reads them.

## Five-minute six-case presentation

Open `six-case-demo.html`; it is independently self-contained. The editable sources are `six-case-index.html`, `six-case.js`, and `six-case.css`.

The six invented examples form two batches: recolor a blue ball red (A1–A3) and remove the blue ball (B1–B3). Each batch contains one complete edit, one partial edit, and one unchanged output. A plant makes preservation concrete.

1. **Six examples.** Show both kinds of edit and the invented teaching references.
2. **Compile checks.** Translate the request into endpoint, progress, and collateral questions. The physical questions differ by operation.
3. **Observe images.** Show how the source/edited comparison answers those exact questions. A true physical answer is not automatically a Yes verdict.
4. **Abstract meaning.** Compare A2 with B2. Both map to endpoint=false and progress=true despite different visual changes.
5. **Fit local rules.** Grow the majority leaf into the endpoint and progress splits. Try depth 1 versus 2, local versus pooled sources, and support 1 versus 2. Inspect the exact split scores and partitions. The older fixed candidates remain available in an expandable comparison.
6. **Propose a parent.** Pool all six originals. The shared rule fits 6/6, but there are zero separate validation sources: the hierarchy replacement stays pending and children are retained. A bad parent visibly loses the Partial distinction.
7. **Freeze & execute.** All reference labels disappear. Follow True/False branches, change a synthetic evidence value, and compare the learned tree with an explicitly authored collateral guard. Unknowns resolve only when all admissible toy evidence completions give the same output.
8. **Replay & score.** Reveal all six references and show the same-example score. This is a synthetic fitting illustration, never a benchmark or unseen-transfer claim.

**Play walkthrough** advances through the eight steps; Left/Right navigates steps; `[`/`]` changes cases; `N` toggles speaker notes. Both demos link to each other when kept in the same folder.

The teaching grammar has three predicates and adjustable support/depth limits; it is much smaller than the actual fourteen-rule v8 artifact. Local support 1 is an explicitly marked relaxation. The authored collateral condition and the toy evidence-bounds handling must not be attributed to all current M2 decisions.

## Presentation controls

- Use the chapter navigation or Left/Right arrows to walk through the system.
- Choose H01–H12 to follow a specific case across inputs, checks, evidence, and inference. `[` and `]` change cases.
- **Present** hides the sidebar; **Speaker notes**, or `N`, toggles the suggested narration.
- **Frozen inference → Run twelve** reveals every case in sequence. Predictions appear before reference revelation in the single-case inspector.
- Inside **Frozen inference**, step through **Compile checks → Observe images → Interpret evidence → Execute policy → Score prediction** for any of the twelve cases. Each step displays its actual saved output.
- **Recorded merging** steps through seven actual accepted merges, their training lineage, parent rule trees, acceptance gates, learning modes, and study controls.
- The predicate-flip control is an explicitly synthetic rule-level probe. It never edits the recorded evidence.

## Branching rule trees and algorithm inspection

Both versions now draw actual **root → True/False branches → decision/output nodes**, rather than nested text or a vertical rule list. Click a node to inspect its full meaning and the examples reaching it. Use **Fit tree**, **100%**, and the zoom buttons, then scroll the canvas to explore larger trees.

The full research demo shows all **27 nodes and 26 edges** from the current v11 merged-root deployment artifact (with the earlier M2 tree separately available) in **Batch calibration**, with a case selector and highlighted prediction route. In **Frozen inference → Execute policy**, **Start at root** and **Next test** follow that exact saved route one predicate at a time. Short visual labels are abbreviations; the inspector retains the full original predicate descriptions. Example counts on this graph refer to exported development records, not M2 training support.

The six-case **Fit local rules** step now executes a small bounded search in the browser:

1. Choose Batch A, Batch B, or the pooled six-source set.
2. Change maximum depth and minimum child-source support.
3. **Reset to majority leaf**, then **Grow next selected split** to replay construction of the selected tree.
4. Click a tree node to inspect its source subset and class counts.
5. Click a candidate predicate to inspect its True/False partitions, immediate errors, recursive result, or rejection reason.
6. **Freeze fitted tree** captures that candidate and its source/depth/support provenance, then opens its inference walkthrough. Later search-control changes do not silently alter the frozen artifact; explicitly freeze again to replace it. Inference traverses the saved immutable tree without refitting.

The search ranks a bounded shortlist by immediate errors, label purity, balance, and feature order. Recursive candidate selection minimizes **training errors, then total nodes**, stopping at the first perfect subtree in the shortlist. It does not claim a global optimum. This follows the structure of `portable_tree_v8.py` on a deliberately tiny, three-predicate grammar. It also shows the stop conditions: pure labels, a depth limit, and insufficient source support.

At depth 1, the pooled fit reaches 4/6. At depth 2 and minimum child support 2, it reaches 6/6 with two decision nodes and three output leaves. Local three-source fits require the explicitly relaxed toy support floor of 1; at support 2 they cannot split. During export, the real Python M2 fitter independently runs on the same six synthetic feature records. Automated checks require identical browser/Python trees, node counts, and predictions at depths 1, 2, and 3, with minimum support 2. These are synthetic algorithm checks, not real image-accuracy observations.

In **Freeze & execute**, compare **Learned from six** with **Authored collateral guard**. The six original examples all preserve the plant, so the learner has no evidence from which to learn a collateral-damage split. The additional guard is explicitly supplied for comparison. Unknown observations illuminate multiple admissible branches; **Next branch** advances through the tree before showing the result.

Shared source files are `rule-tree.js` and `rule-tree.css`. The browser learner is `six-search.js`; `six-case-reference.js` is generated from the actual Python fitter. Both standalone HTML files embed these dependencies.

## Suggested full-demo meeting (current v11)

1. **System map — 1 minute.** Distinguish the training merge lineage from the deployed decision tree. Inference uses one root and skips M4.
2. **Inputs & labels — 1 minute.** Show H03, both images and the AURORA mean-to-label mapping. Keep references outside the model stages and runtime decisions.
3. **Selection policies — 1 minute.** Explain the original partition, label-blind semantic grouping, pair scoring and training-only preference for a qualified reused root.
4. **Decision check sets — 2 minutes.** Use H08 to separate hand/spoon movement, grip, powder release and intermediates. Inspect exact question bindings.
5. **Evidence & meaning — 1 minute.** Inspect physical states and the cached instruction-relative interpretation. Recorded model facts can still be wrong.
6. **Batch calibration — 1 minute.** Show the current 46/48 root, then the earlier 44/48 M2 tree. Click a rule node and illuminate a case path.
7. **Recorded merging — 3 minutes.** Step through the eight seeds and seven selected unions. Show strict union/retention gates, full-grammar repairs and the final child-only root. The last merge trades one correct answer for five fewer rules within the sealed allowance.
8. **Frozen inference — 1 minute.** Execute the current root step by step and run all twelve cases. Toggle the earlier M2 policy to compare exact decisions using the same evidence.
9. **Results & boundaries — 1 minute.** Report 46/48 locally and 10/12 development. Keep H01/H07 disagreements and the three training semantic conflicts visible. The final fifty remain reserved.

## The twelve cases

These are actual H01–H12 development records from the October 14 M1 run, not synthetic test outcomes. Four sources per reference class; all twelve sources are disjoint from the 48 v8 fitting sources. Their historical project exposure prevents a globally fresh-test claim.

| Case | Instruction / distinguishing issue | Reference | Earlier M2 | Current merged root |
|---|---|---|---|---|
| H01 | Remove the man; incomplete removal and collateral damage | No | No  Partial |
| H02 | Make the man partially stand up; requested partial endpoint and body-pose evidence | Partial | Partial  Partial |
| H03 | Move the mug to the right; preservation/materiality dispute | Yes | Yes  Yes |
| H04 | Thomas Kincaid painting style; incidental change versus style progress | No | No  No |
| H05 | Remove the tiny blue metallic cylinder; unrelated sphere disappearance | Partial | Yes  Partial |
| H06 | Remove two sharks; source-anchored absence | Yes | Yes  Yes |
| H07 | Remove the left bottle’s lid with a hand; identity/action uncertainty | No | Partial  Partial |
| H08 | Move hand/spoon right and drop powder; compound action and failed endpoint | Partial | No  Partial |
| H09 | Put a frog in the toilet; addition and spatial relation | Yes | Yes  Yes |
| H10 | Crayon style; incidental appearance versus requested transformation | No | No  No |
| H11 | Add a right-side gray ball; unrelated sphere-size change | Partial | Partial  Partial |
| H12 | Put a comb into the box; addition and containment | Yes | Yes  Yes |

The earlier M2 disagreements were H05, H07, and H08. The merged root corrects H05/H08 but loses H01, leaving H01 and H07 as disagreements. No observations or labels were edited to improve the demonstration. The M1 fixed uncalibrated diagnostic also scores 9/12, with two unresolved outputs; it is a different decision policy and a different pattern of errors.

## Provenance and implementation status

The export recomputes the bound M1 records, validates the existing instruction-relative interpretations, projects the v8 predicates, runs the real Python `PortableRuleExecutor`, and checks all 48 training predictions against the saved reviewed result. The browser traverses the same saved tree and checks exact prediction/trace parity for all twelve exported cases at startup. The source ledger includes artifact SHA-256 identities.

- **Recorded and replayed:** actual images, instructions, references, 90 bound questions, observations, semantic interpretations, current deployment tree, candidate-selection results, and v16 local policies.
- **Implemented in another path:** the legacy/modular prompt-tree builder supports TextGrad/GEPA plans, raw/decomposed evaluation, guarded multi-child merges, residual promotion, and immutable stage artifacts. These are not presented as empirical v8 hierarchy results.
- **Recorded:** v11 semantic groups, seven selected merges, exact union/retention gates, child-vocabulary reuse and full-grammar repairs. **Illustrative:** only explicitly marked counterfactuals and the separate six-case lesson.
- **Not established:** broad statistical transfer, complete semantic correctness of learned associations, final fifty-case results, repeated/paraphrased model robustness, or production qualification.

No training, optimizer, image extraction, or final-set prediction runs are launched by this demo. The exporter does not read the reserved final-set records. Historical experiment files remain untouched.

## Rebuild and verify

From the repository root:

```sh
.venv/bin/python demos/calitree_meeting/build_demo.py
node demos/calitree_meeting/check_demo.cjs
node demos/calitree_meeting/check_six.cjs
```

The exporter needs the existing experiment artifacts and local AURORA images. The interaction check uses the repository’s already installed `web/node_modules/jsdom`. The generated single-file demo needs neither Python nor Node.

For an optional local preview, serve **only this directory**:

```sh
python3 -m http.server 8765 --bind 127.0.0.1 --directory demos/calitree_meeting
```

Open `http://127.0.0.1:8765/`. The standalone file remains the presentation deliverable and works after the preview server stops.
