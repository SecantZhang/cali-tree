# CaliTree advisor demo

Open **[calitree-demo.html](calitree-demo.html)** in a browser. It is one self-contained file, including all images, code, and data. No installation, server, network, credentials, or model calls are needed. Copy this file to another computer if useful.

The multi-file editable version starts at `index.html`. Source files are `app.js`, `style.css`, and `build_demo.py`; `data.js`, `media/`, and `calitree-demo.html` are generated exports.

## Presentation controls

- Use the chapter navigation or Left/Right arrows to walk through the system.
- Choose H01–H12 to follow a specific case across inputs, checks, evidence, and inference. `[` and `]` change cases.
- **Present** hides the sidebar; **Speaker notes**, or `N`, toggles the suggested narration.
- **Frozen inference → Run twelve** reveals every case in sequence. Predictions appear before reference revelation in the single-case inspector.
- Inside **Frozen inference**, step through **Compile checks → Observe images → Interpret evidence → Execute policy → Score prediction** for any of the twelve cases. Each step displays its actual saved output.
- **Merge laboratory** switches among acceptance, rejection, residual promotion, and insufficient support. All its training/validation examples and metrics are explicitly synthetic.
- The predicate-flip control is an explicitly synthetic rule-level probe. It never edits the recorded evidence.

## Suggested 12-minute meeting

1. **System map — 1 minute.** The editing model produces an edited image. CaliTree judges satisfaction, returning a label and an inspectable evidence/rule trace. Distinguish the decision tree inside one policy from a hierarchy of policies.
2. **Inputs & labels — 1 minute.** Show H03. Identify instruction, source, edited output, and AURORA reference mean. Explain `<0.5 → No`, `[0.5,1.5) → Partial`, and `≥1.5 → Yes`. The released means are not reconstructed individual votes.
3. **Selection policies — 1 minute.** Distinguish source-level sampling, fitted-candidate selection, runtime routing, and merge proposal ranking. V8 is one pooled policy, without a specialist router. No inference selector sees the reference label.
4. **Decision check sets — 2 minutes.** Show H08. Hand movement, spoon movement, coherent grip, powder release, downward motion, and intermediate geometry are different checks. Inspect the exact question, role, target/reference, expected polarity, dependencies, and hash.
5. **Evidence & meaning — 1 minute.** Still on H08, inspect raw versus effective states, source/edited evidence, and the cached interpretation. Then show H05: cylinder removal and collateral sphere disappearance are separate facts. Hashes protect binding, not perceptual truth.
6. **Batch calibration — 2 minutes.** Compare the historical four v16 local policies with the current v8 pooled policy. Local agreement is fitting capacity. The current selected fit is 46/48; semantic review yields 44/48, 14 rules, and 13 used predicates. The prompt-tree optimization tab explains TextGrad, GEPA, two-way decomposition, and stage artifacts separately.
7. **Merge laboratory — 1 minute.** Pool the complete original training union, including failures. Compare the candidate parent plus router against the prior routed system on separate validation. Show a rejection caused by Partial-recall regression and a partial parent retaining four residual assignments. The newer semantic hierarchy is future work.
8. **Frozen inference — 1 minute.** Show a saved v8 predicate trace, reveal its reference, and run all twelve. A fresh case uses two M1 calls plus one text-only interpretation; rule execution itself is deterministic. This offline replay makes zero calls.
9. **Results & boundaries — 1 minute.** Report 9/12 on these historically exposed development sources, versus 44/48 local training fit. Preserve all disagreements. Do not describe either as final-test accuracy. The reserved final fifty are outside the demo.

## The twelve cases

These are actual H01–H12 development records from the October 14 M1 run, not synthetic test outcomes. Four sources per reference class; all twelve sources are disjoint from the 48 v8 fitting sources. Their historical project exposure prevents a globally fresh-test claim.

| Case | Instruction / distinguishing issue | Reference | V8 demo replay |
|---|---|---|---|
| H01 | Remove the man; incomplete removal and collateral damage | No | No |
| H02 | Make the man partially stand up; requested partial endpoint and body-pose evidence | Partial | Partial |
| H03 | Move the mug to the right; preservation/materiality dispute | Yes | Yes |
| H04 | Thomas Kincaid painting style; incidental change versus style progress | No | No |
| H05 | Remove the tiny blue metallic cylinder; unrelated sphere disappearance | Partial | Yes |
| H06 | Remove two sharks; source-anchored absence | Yes | Yes |
| H07 | Remove the left bottle’s lid with a hand; identity/action uncertainty | No | Partial |
| H08 | Move hand/spoon right and drop powder; compound action and failed endpoint | Partial | No |
| H09 | Put a frog in the toilet; addition and spatial relation | Yes | Yes |
| H10 | Crayon style; incidental appearance versus requested transformation | No | No |
| H11 | Add a right-side gray ball; unrelated sphere-size change | Partial | Partial |
| H12 | Put a comb into the box; addition and containment | Yes | Yes |

H05, H07, and H08 remain disagreements. No observations or labels were edited to improve the demonstration. The M1 fixed uncalibrated diagnostic also scores 9/12, with two unresolved outputs; it is a different decision policy and a different pattern of errors.

## Provenance and implementation status

The export recomputes the bound M1 records, validates the existing instruction-relative interpretations, projects the v8 predicates, runs the real Python `PortableRuleExecutor`, and checks all 48 training predictions against the saved reviewed result. The browser traverses the same saved tree and checks exact prediction/trace parity for all twelve exported cases at startup. The source ledger includes artifact SHA-256 identities.

- **Recorded and replayed:** actual images, instructions, references, 90 bound questions, observations, semantic interpretations, current deployment tree, candidate-selection results, and v16 local policies.
- **Implemented in another path:** the legacy/modular prompt-tree builder supports TextGrad/GEPA plans, raw/decomposed evaluation, guarded multi-child merges, residual promotion, and immutable stage artifacts. These are not presented as empirical v8 hierarchy results.
- **Illustrative:** semantic merge proposals/parents, source-disjoint synthetic validation metrics, and counterfactual predicate flips. The merge acceptance gates follow the roadmap’s proposed defaults, with separate legacy scope/served mechanics explained.
- **Not established:** semantic hierarchy transfer, final fifty-case results, repeated/paraphrased model robustness, or production qualification.

No training, optimizer, image extraction, or final-set prediction runs are launched by this demo. The exporter does not read the reserved final-set records. Historical experiment files remain untouched.

## Rebuild and verify

From the repository root:

```sh
.venv/bin/python demos/calitree_meeting/build_demo.py
node demos/calitree_meeting/check_demo.cjs
```

The exporter needs the existing experiment artifacts and local AURORA images. The interaction check uses the repository’s already installed `web/node_modules/jsdom`. The generated single-file demo needs neither Python nor Node.

For an optional local preview, serve **only this directory**:

```sh
python3 -m http.server 8765 --bind 127.0.0.1 --directory demos/calitree_meeting
```

Open `http://127.0.0.1:8765/`. The standalone file remains the presentation deliverable and works after the preview server stops.
