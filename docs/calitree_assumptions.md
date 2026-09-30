# CaliTree: system design and assumption register

CaliTree aims to turn specialized judgments into a compact, reusable calibration system. The proposed path is:

~~~text
cases → fit groups → leaf prompt optimization → decision sets
                                          ↓               ↓
                                  prompt index     shared semantic features
                                          ↓               ↓
                                  clustering       learned decision trees
                                          └───────┬───────┘
                                              joint merges
                                                  ↓
                                      validated tree or forest
                                                  ↓
                                   target-blind routing and judging
~~~

This is a **design and research map**, not a claim that every arrow is implemented or validated. Decomposition is one part of the system. The whole design also depends on fit-group construction, optimization, concept alignment, learned rules, prompt indexing, clustering, merge synthesis, acceptance, routing, and artifact integrity. The immediate case-level objective is to make each named decision correct and explainable. The broader hierarchy objective is to compress compatible decisions and use them on further cases without losing protected behavior.

The [CaliTree goal](calitree_goal.md) defines specialization and bottom-up compression. The [structure document](calitree_structure.md) describes current modular nodes and canvas APIs. This document collects the **whole-system assumptions**, the proposed additions, and the experiments needed to test them.

## 1. Separate the two trees

A **learned decision tree** is a model inside a node or compatible group. It takes condition-level features measured from SOURCE and EDITED and learns a mapping to the human target. Its splits may improve a prompt's decision, but a fitted tree is not automatically a faithful execution of that prompt.

The **CaliTree hierarchy** is a graph of leaf and merge nodes. Each leaf has a specialized prompt and measured case scope. Each merge accepts two or more leaf/merge children, proposes a parent, and is retained only after measuring the parent against the descendant scope and configured guards. The hierarchy decides which node should handle a future case. It does not arise automatically from the learned tree's feature splits.

A **decision set** bridges them. For one case it contains the prompt-bound rubric, decomposed instruction, atomic observations, preservation findings, label, and trace. Across cases it yields a catalog of reusable criteria. Local condition IDs are not reusable feature names: the first condition in two cases may mean different things.

Keep three prediction arms separate throughout development:

| Arm | What decides the label | What it can establish |
| --- | --- | --- |
| Raw optimized prompt | Direct model judgment with the chosen prose rubric. | Performance of that prompt on the named cases. |
| Faithful decomposed policy | Condition checks aggregated under a policy compiled from that exact prompt. | Whether explicit execution can preserve and expose the prompt's decisions, plus its measured case accuracy. |
| Learned decision tree | Rules fitted from condition features and human training labels. | Whether those features can support a useful calibrated mapping; it may intentionally depart from the prompt. |

A corrected human-label prediction is not by itself evidence that compilation was faithful. A learned tree that fits known cases is not by itself evidence that it will repeat or route correctly.

## 2. End-to-end design

### Step 0 — Fix the task and data contract

Define the human target, case/task IDs, instruction, SOURCE/EDITED roles, image-byte identities, and allowed inference inputs. Keep all editor outputs of the same source/instruction together when making a reserved split. Record whether a cohort is a named-case fitting set, reserved validation, or untouched test set. A known label used to revise that same case is training feedback, not independent validation. Human annotations are fallible: label agreement is not automatically semantic correctness. Explicitly disputed or ambiguous annotations belong in a review cohort and must not drive fitting until adjudicated.

Compare all candidate paths on the exact same pixels, prompt version, and model settings. A case's accuracy is 0 or 1; invalid decisions remain visible and count as incorrect when reporting a case-level result.

**Assumptions D1–D2:** the record identifies the right image pair and the annotation is an appropriate provisional target for that case. Neither is guaranteed. A scalar label does not provide the raters' reason; records that fail review are quarantined rather than forced into the target mapping.

### Annotation uncertainty and data eligibility

Use separate states for the dataset annotation and the model's observation. **Uncertain annotation** means the task, evidence, or recorded label does not currently provide a defensible training target. **Unknown observation** means this execution lacks evidence to resolve a condition. A legitimate partial edit is neither automatically an uncertain annotation nor a model failure.

| Axis | States | Meaning and action |
| --- | --- | --- |
| Annotation review | `unreviewed`, `usable`, `uncertain` | Unreviewed labels are provisional. An explicitly uncertain case is retained for review and excluded from fitting, acceptance calibration, population priors, and primary agreement metrics. Usable means reviewed for the stated task, not infallible truth. |
| Condition observation | `complete`, `partial`, `absent`, `unknown` | Preserve what the evidence supports. Unknown does not imply the human annotation is wrong. |
| Decision support | Supported; insufficient; conflicting | Distinguish uncertainty permitted by a partial criterion from a gap that prevents choosing a status. Report the latter as unknown. |

A review should consider mismatched image/instruction records, instructions admitting incompatible readings, essential evidence that is not observable, conflicting annotator judgments, or a label inconsistent with a documented rubric. **Model disagreement alone is not grounds for exclusion.** Do not label difficult cases uncertain merely to raise reported agreement. Repeated model failures trigger review; they do not resolve the review.

Store the original annotation, reviewer identity, reason, supporting evidence, and any later adjudication. Preserve versions when correcting a label. Report the eligible and quarantined denominators separately, with uncertainty by task/editor/class where support permits. Never convert `uncertain` into the grading label `partial`, manufacture a replacement target, or feed quarantined labels into TextGrad/GEPA feedback, learned-tree targets, merge acceptance, or routing calibration. Unlabeled diagnostic inspection remains possible without using the disputed target.

Implemented workflow metadata uses a separate annotation field:

```json
{
  "target_label": "partial",
  "annotation_review": {
    "status": "uncertain",
    "reason": "Two plausible readings of the instruction imply different grades",
    "reviewed_by": "reviewer-id"
  }
}
```

The shared partition retains original records and official test membership while excluding uncertain training records from fit/reserved selection. Automatic Train also excludes flagged population annotations; Eval lists quarantined records outside its primary agreement denominator. Manual nodes reject flagged fit/validation assignments even when given an older partition. For direct Python use, `CaliTreeBuilder.build(annotation_reviews={case_id: review})` rejects uncertain requested targets; callers may explicitly create an eligible cohort with `partition_annotations(...)`. `CasewiseExperiment.fit(annotation_review=review)` also rejects uncertain fitting labels before calls. These are metadata/API controls; no new review-editor UI or automatic adjudicator is claimed.

An explicit `target_label: "uncertain"` is also quarantined; its original record is retained and a missing reviewer is recorded as missing rather than invented. Missing review metadata on ordinary no/partial/yes annotations remains `unreviewed` and provisionally eligible to preserve existing workflows, not automatically certified usable. No existing experimental case has been quarantined solely because of model disagreement. A stricter reviewed-only experiment must select that cohort explicitly and report the resulting coverage.

**Weird-case handling is part of the CaliTree process.** Persistent model–label disagreement, an implausible edited object, incompatible readings of the instruction, or inconsistent condition evidence can flag a case for inspection. Agreement across model runs is useful review evidence, but repeated outputs from related models/prompts are not independent proof that the dataset target is wrong. The review may confirm the original target, explicitly correct it, or classify the case as `uncertain` with an optional `category: weird_case`. Do not keep revising a leaf prompt or decomposition until it memorizes an unresolved annotation.

After an explicit uncertain review, preserve the original target and all predictions; exclude the case from optimization feedback, learned-tree targets, merge calibration, and primary agreement metrics. Keep it in a separate diagnostic/review collection. Report both the original cohort results and the reviewed eligible/quarantined counts, so removal cannot hide failures or appear to improve the model. Reinstatement requires a new documented review, not model confidence alone. The generic metadata gates above implement exclusion; automatic weird-case detection is not yet implemented.

**J16 review outcome:** after seeing the image pair, original `partial` annotation, and model `yes` predictions, the user classified J16 as a weird case. The pilot registry [calitree_case_reviews.json](experiments/calitree_case_reviews.json) records it as user-reviewed `uncertain`, bound to the exact images and instruction. Its original target stays `partial`; no replacement `yes` target is created. The pending additional J16 relation experiment was withdrawn. The current two-case pilot therefore has one provisionally eligible case (J01) and one quarantined case (J16). This is a change in cohort eligibility, not evidence that decomposition accuracy improved. The separate J16 region and projected-position reviews remain valid within their original scope; they do not adjudicate the overall target. The registry applies to this pilot; unrelated AURORA workflow records must receive the same review metadata explicitly to use the existing exclusion gates.

### Step 1 — Form fit groups and leaves

Choose leaf granularity explicitly: one case, one task's editor outputs, an operation family, or a coherent semantic/error group. Record members, overlap, labels used for grouping, and the rule that created the group. A leaf may specialize aggressively to fit cases, but its scope and degree of support must be visible. Maintain a global fallback and permit leaves that cannot merge to remain separate.

Training may use labels to choose groups or fit prompts. Inference cannot route by an unknown human label, a memorized case ID, or a failure category derived from that label. Any specialization expected to handle new cases needs an observable routing description.

**Assumption G1:** the grouping captures a meaningful shared decision pattern. Groups that are too broad mix conflicting policies; single-case leaves offer little evidence for reuse.

### Step 2 — Optimize each leaf prompt

Start with a seed rubric. Generate bounded candidates with the selected optimizer, including TextGrad, GEPA, a combined plan, or evaluation-only operation. Retain the seed, every candidate, measured fit predictions, usage, stop reason, and final prompt revision. The optimizer may score raw-prompt or decomposed judgments as an explicit choice; record that choice and keep the two measurements separate. Score the final raw prompt before attributing any later change to decomposition.

A prompt change invalidates prompt-bound compiled policy and derived measurements. A successful case-specific patch may be too narrow or contradictory for a parent; do not hide that specificity when indexing or merging.

**Assumption P1:** optimization discovers a useful criterion rather than an item-specific answer shortcut or an unrelated change to the grading boundary.

### Step 3 — Produce decision sets

Compile the **final** selected prompt into a versioned policy bound to its exact hash. Independently parse each edit instruction into observable requested actions, targets, references, counts, relations, and scope. Compare SOURCE and EDITED for each condition; inspect preservation separately; aggregate under the policy. Save the intermediate plan, observations, validity flags, and cited decision trace.

Faithful mode excludes human labels from compilation, image checks, and aggregation. Explicit casewise-fitting mode may use a known label for bounded criterion revision after an initial decision; mark those rules as fitted and retain conflicts with the earlier prompt. The structured-evidence and image-pair strategies have different input boundaries and reducers, so their results must not be conflated.

**Assumptions X1–X4:** compilation preserves the rubric; instruction decomposition preserves intent without extras; target binding and observations are true; preservation and requested effects are scoped correctly. Parsing success and verbatim source coverage do not prove these semantic claims.

Keep this stage small: compile the rubric, decompose the instruction, check the images, and aggregate. Retain unknown when evidence is insufficient. Review unusual or disputed cases before adding new observation stages or repeatedly repairing their prompts. A case-specific failure is not enough reason to add a new default component.

### Step 4 — Align local criteria to reusable concepts

Create a versioned semantic concept schema. A concept should distinguish operation, requested delta, target identity, reference role, relation and frame of reference, quantity, status, preservation dimension, and permitted effects. Map each local condition and rubric unit to a canonical concept while retaining its source wording. A condition that cannot be aligned safely remains local or explicitly unmapped.

For example, “move the bowl left of the flower” is a spatial relation with a reference object, whereas “move the bowl left” may depend on a scene or source-position frame. Text similarity must not merge these into one criterion without checking that boundary. Likewise, descriptors that identify the removed object are not extra requested edits.

**Assumption C1:** criteria from different optimized prompts contain reusable equivalences that can be aligned without erasing distinctions important to human labels.

### Step 5 — Build a case-by-feature matrix

Build one row per image-pair case from aligned condition observations and preservation findings. Keep at least four separate states: complete, partial, absent, and unknown. A concept that was not requested is **not applicable**, which is different from absent or unknown. Store human labels in a separate target column, never as features. Record whether optional features such as raw-prompt prediction or editor identity are allowed and available at inference.

Rows retain links to image bytes, prompt/policy revision, condition plan, checker settings, concept schema, and original observations. Group related outputs by task/source when assessing a learned model. A schema revision rebuilds feature rows and dependent trees; it must not silently reinterpret old cached results.

**Assumption C2:** the measured features contain enough information to distinguish cases with different correct labels. Identical feature vectors with different labels expose an information gap that a deterministic tree cannot solve by adding depth.

### Step 6 — Learn interpretable decision rules

Fit a small decision tree or rule list from the feature matrix, with human training labels as targets. Predeclare feature set, tree complexity, class weighting, unknown-value handling, and fallback. Preserve split support, class counts, and the cases behind every rule. Do not hard-code a universal mapping from one absent condition to no or from one partial finding to partial unless that mapping is the chosen policy being tested.

Compare a leaf-local tree, a shared concept tree across compatible leaves, and a parent tree learned after merging as separate candidate models. If a group has too little support or no feature variation, mark the learned model unavailable and use its configured policy/raw fallback. Do not claim a fitted tree is the compiled prompt.

**Assumptions T1–T2:** the features support a compact, stable mapping to human judgments, including the difficult partial boundary. The [ten-case assumption pilot](experiments/assumptions_10_case_pilot.md) found condition instability and conflicting labels for identical measured vectors, so this remains a research stage rather than an established component of the modular execution path.

### Step 7 — Index prompt and decision artifacts

Add a **versioned prompt index** whose record includes prompt hash/revision, node and lineage IDs, operation tags, criterion/concept signatures, embeddings, measured behavior profile, fit support, strategy identity, and policy/tree references. Candidate prompt revisions remain distinct records. Updating a prompt or concept schema invalidates derived index entries. The index can also expose near-duplicate prompts and retrieve a candidate seed for a new leaf; a retrieved seed must be remeasured on that leaf's own cases.

Maintain two logical views. The **construction index** proposes leaf seeds and merge candidates using semantic proximity, concept overlap, policy compatibility, behavior, and bidirectional transfer measured on permitted training cases. It may contain label-derived training diagnostics. The **inference index/router** uses only target-blind observable inputs and validated support. Retrieval is a shortlist, never proof that a seed, merge, or node will work.

Measure candidate recall, false-match rate, version freshness, and the reasons a pair was excluded. Indexing should make a large leaf pool searchable without turning nearest-neighbor similarity into an unvalidated decision rule.

**Assumptions I1–I2:** the index retrieves meaningfully compatible candidates and remains synchronized with prompt, policy, concept, and learned-model revisions.

### Step 8 — Cluster and group merge candidates

Rank pairs using prompt/criterion similarity, aligned concepts, observed decision behavior, conflict checks, and bidirectional transfer. Shared vocabulary can conceal opposite thresholds; different wording can express the same rule. Check operation scope, preservation exceptions, and partial boundaries before synthesis.

For a multi-child group, start with an eligible pair, then add a candidate only when it is compatible with every member. Respect the child limit and deterministic tie-breaks. Preserve manual grouping for meaningful abstractions the ranking misses. Record exact attempted and rejected groups; do not repeatedly propose an unchanged rejected group.

**Assumptions K1–K2:** pairwise semantic/behavioral signals help predict compatibility, and pairwise checks are useful filters for joint groups. They cannot prove a three-child parent will work.

### Step 9 — Propose and relearn a joint parent

A merge takes at least two distinct leaf/merge nodes and makes one joint proposal from all child prompts, policies, concept summaries, learned rules, and recorded conflicts. It is not an implicit binary fold. Deduplicate overlapping scope IDs, preserve every child ID, and reject cycles or conflicting case records. Prompt-only candidates may contribute to synthesis; missing decision artifacts remain explicitly missing.

Compile the parent's **own** prompt. Recheck or rederive observations when the parent changes criterion meaning. Align a parent concept set and optionally fit a new tree on the union of child feature rows. A parent might use conditional rules to retain a distinction between children, but the condition must be observable without the target. Shorter prose or fewer nodes alone does not constitute successful compression.

**Assumption M1:** a coherent parent can share criteria while preserving distinctions responsible for each child's correct decisions.

### Step 10 — Accept, reject, or partially retain

Evaluate the parent on the full deduplicated union of descendant scopes, not only the cases it serves correctly. Compare each case's child, parent-raw, parent-policy, and parent-learned-tree predictions. Apply fit, reserved-validation, class-specific, and baseline-regression guards to the **actual output path** that would be deployed. Record complexity, cost, and latency alongside correctness.

If the parent fails, retain the children. For a partial merge, assign only measured-correct current cases to the parent and keep residual cases on freshly measured promoted leaves. Preserve the full scope denominator and lineage. **Partial merge** means incomplete coverage; it is unrelated to the prediction label **partial**.

**Assumptions M2–M3:** acceptance guards reject destructive compression and residual specialization preserves cases the parent cannot handle. The possibility of a successful merge must be demonstrated case by case rather than inferred from similarity.

### Step 11 — Route and judge

Route a new case using its instruction and permitted observable context, with validated thresholds and support. Select a supported specialist only when justified; otherwise use the global fallback. Record the selected node, route path, prompt revision, execution arm, evidence identity, and any referral. Execute that node's persisted policy or learned tree with a fresh instruction plan and current image evidence. A manual canvas connection to one node judges that exact node without automatic rerouting.

If essential evidence is unknown, checks conflict, or routing support is weak, retain the underlying three-class prediction while allowing an explicit needs-human decision. Referral for model uncertainty is different from disagreement among human raters.

**Assumptions R1–R2:** routing can find useful specialization without target leakage, and uncertainty signals can identify risky automatic decisions.

### Step 12 — Persist, inspect, and revise

Store immutable artifacts and dependency links from case pixels through prompt, policy, instruction plan, observations, feature schema, learned model, index entry, merge, and route. Freeze only completed compatible stages. A metrics-only action reuses predictions; a genuinely fresh evaluation reruns unfrozen evidence and judgment with a new cache identity. Display original settings and changed inputs.

When a case fails, locate the earliest responsible boundary: data, grouping, optimization, compilation, plan, target binding, observation, concept alignment, tree rule, index retrieval, merge, acceptance, or route. Fix that boundary and invalidate descendants. A corrected final label with no explanation does not show which system assumption was repaired. Repeated failures or uncovered concepts can suggest new cases for annotation or a new leaf, but those additions begin a new fit/version cycle; they do not retroactively become independent validation for the revised system.

**Assumption E1:** provenance is complete enough to trace a result and prevent stale artifacts from appearing valid.

## 3. Artifact contracts

| Artifact | Required information | Invalidated by |
| --- | --- | --- |
| Case | Stable case/task identity, instruction, SOURCE/EDITED byte hashes, protected human target, partition, provenance. | Image or instruction change. |
| Fit group | Member IDs, construction rule, label-feedback status, overlap, revision. | Membership or grouping-rule change. |
| Leaf | Seed/selected prompt, candidate history, scope/served/correct IDs, strategy, policy/evaluation references. | Prompt or fit-data change. |
| Decision set | Prompt-bound rubric, instruction plan, condition and preservation findings, label, trace, validity. | Prompt, instruction, evidence, template, or engine change. |
| Concept map | Canonical concept IDs, local mappings, exceptions, unmapped cases, version. | Mapping or definition revision. |
| Feature matrix | Case-by-feature states with not-applicable and unknown distinct; target stored separately. | Concept map, observations, evidence, or checker revision. |
| Learned tree | Rules, fit cases/labels, split support, complexity, missing-value logic, fallback. | Feature schema, fit data, target, or learner configuration change. |
| Prompt index | Immutable prompt revisions, embeddings, concept/behavior signatures, support and candidate diagnostics. | Prompt, concept, behavior, or embedding version change. |
| Merge node | Every child ID, full scope union, parent proposal, per-case comparison, acceptance and residual assignments. | Child/parent revision or measurement change. |
| Router | Eligible nodes, target-blind features, thresholds, support, global fallback. | Node acceptance, index, or routing-calibration change. |

The hierarchy and learned tree need separate version identifiers. Saved inference must restore the exact selected prompt, policy, concept schema, and learned model without depending on a transient run path. Human labels may train a model but may never appear as inference-time features.

## 4. Whole-system assumption register

**Implemented contract** means code enforces a boundary, not that model quality is proven. **Exploratory** means an isolated experiment exists. **Open** means the key test is missing. **Challenged** means recorded cases already show counterexamples.

| ID | Assumption | Status | Decisive check |
| --- | --- | --- | --- |
| D1 | Case, image, instruction, and label identities are correct. | Hash contracts implemented; input-layout issues have occurred. | Reconcile disputed pairs with source archive and panel roles. |
| D2 | Released labels capture the desired semantic target. | Open; labels lack explanations. | Blind adjudication of disputed and partial cases. |
| G1 | Fit-group granularity creates coherent specializations. | Existing task/manual groups; optimal grouping open. | Compare one-case, task, operation, and semantic-cluster leaves. |
| P1 | Prompt optimization learns criteria, not answer shortcuts. | Candidate histories implemented; semantic effect open. | Prompt-clause audit and per-case before/after predictions. |
| X1 | Compiled policy preserves the exact prompt's decision boundaries. | Hash/source coverage implemented; semantic fidelity open. | Audit direct/policy disagreements and rubric exceptions. |
| X2 | Instruction decomposition is complete without added constraints. | Lexical coverage implemented; invented strictness observed. | Annotate missing, duplicate, and added conditions. |
| X3 | Image target binding and atomic checks are true and repeatable. | Challenged by wrong-object/movement observations. | Independent concept annotations and fresh repeats. |
| X4 | Preservation is separated from permitted edit effects. | Challenged in style/collateral-change cases. | Annotate permitted effects and severity. |
| C1 | Local conditions map to stable reusable concepts. | Proposed. | Blind concept-equivalence audit and mapping disagreement. |
| C2 | Concept features suffice to separate correct labels. | Challenged by identical-feature/conflicting-label pilot rows. | Count collisions after independent feature annotation. |
| T1 | A compact learned tree adds useful calibrated decisions. | Exploratory ten-case pilot; not integrated. | Compare local/shared trees with raw and policy baselines. |
| T2 | Learned rules handle partial, unknown, and not-applicable states. | Open. | Inspect split support and replay boundary cases. |
| I1 | Prompt indexing retrieves compatible merge candidates. | Embeddings and pair ranking exist; unified index proposed. | Measure compatible-pair recall and false positives. |
| I2 | Index entries stay synchronized with prompt and concept revisions. | Policy hashes exist; full cross-artifact contract proposed. | Mutate each dependency and require targeted invalidation. |
| K1 | Semantic, behavior, and transfer signals predict merge success. | Existing clustering/probes; predictive strength open. | Rank candidates and compare scores with joint-parent outcomes. |
| K2 | Pairwise compatibility helps form valid multi-child groups. | Deterministic grouping implemented; higher-order effects open. | Compare pair eligibility with three-plus-child outcomes. |
| M1 | A parent compresses without losing material child distinctions. | Merge synthesis/guards implemented; case-dependent. | Full-scope parent-versus-child trace and complexity audit. |
| M2 | Acceptance guards block destructive merges. | Full-scope fit and reserved guards implemented. | Inspect every corrected and regressed child assignment. |
| M3 | Promoted residual leaves retain measured behavior. | Implemented contract. | Verify residuals after repeated partial merges. |
| R1 | Target-blind routing selects supported specialists. | Routing/fallback exists; tree-aware routing proposed. | Per-case route versus fallback and oracle comparison. |
| R2 | Referral can catch unsafe automatic decisions. | Related referral policies exist; integrated use open. | Report error capture, precision, and coverage. |
| E1 | Artifact identities prevent stale or mismatched execution. | Stage/hash contracts implemented. | Dependency mutations and independent-cache repeats. |

## 5. Minimum required assumptions — simplified table

For the proposed pipeline — **leaves → optimized prompts → decision sets → learned decision tree → merge** — the first five assumptions below are the minimum working hypotheses. The sixth is needed when CaliTree automatically selects a node. They are requirements to test, **not established facts or guarantees of generalization**.

| # | Minimum assumption | Smallest concrete demonstration | Detailed register |
| --- | --- | --- | --- |
| **1** | **Enough cases have usable targets.** The selected fitting records have coherent instructions, image pairs, and defensible annotations; disputed records are quarantined. | Review the selected records; retain uncertain cases separately and report eligible/quarantined counts. Do not exclude cases just for model disagreement. | D1–D2 |
| **2** | **A useful leaf rule exists.** A selected case group can be handled by an explicit prompt; optimization can find or retain that rule. | Keep a seed or optimized prompt that makes the intended decisions on that group's named cases, without embedding case answers. | G1, P1 |
| **3** | **Decision sets carry reusable signal.** Their observations are reliable enough, and corresponding conditions across cases can be compared without losing distinctions needed for the label. | Inspect atomic findings, repeat fresh checks, and verify that aligned features distinguish the selected cases' different targets. | X1–X4, C1–C2 |
| **4** | **A small learned tree can use that signal.** Observable decision-set features support rules that reproduce the intended judgments. | Fit and inspect a small tree on those features; show each named case's prediction and the rule responsible, without labels or case IDs as inputs. | T1–T2 |
| **5** | **Some leaves can share a parent.** At least two compatible leaves admit a joint rule that reduces duplication while preserving protected decisions. | Propose one parent, compare it with every child on the full scope union, and retain measured residual leaves where needed. Count the parent and residuals when assessing compression. | I1, K1–K2, M1–M3 |
| **6** | **The right node can be selected without the answer.** When selection is automatic, available inputs suffice to choose a useful node or fallback. | Route the named cases without their targets and inspect the resulting decisions against the same cases' fallback decisions. | R1–R2 |

**Scope of the minimum.** A manually connected demonstration can choose groups and merge candidates by hand and judge a specified node directly; it does not yet test assumption 6. Automatic operation requires that additional test. Neither demonstration establishes performance on unseen cases. Claims of generalization need separate reserved-case evaluation; the existing modular merge API still requires its configured reserved-validation guard.

**What is not required as an assumption.** Every leaf need not improve over its seed, every pair need not merge, and decomposition need not correct every raw-prompt mistake. A particular optimizer, clustering algorithm, embedding model, prompt index, tree depth, or UI is replaceable. Manual grouping or exhaustive candidate comparison can establish the small-scale mechanism first; indexing and clustering then need to make that search practical at larger scale.

**Engineering prerequisites apply to every row.** Preserve exact case/prompt/policy/evidence identities, keep labels out of inference inputs, record feedback used during fitting, and invalidate incompatible cached artifacts. These are enforceable conditions for a valid experiment (I2, E1), rather than extra scientific assumptions. Cache replay establishes reproducibility of stored results; fresh checks are needed to measure repeatability.

## 6. Evaluation program

The unit of inspection is the image-pair case with its full trace. Aggregate scores index the case records; they do not replace them.

1. **Optimization ablation:** compare seed and optimized raw prompts on exactly the same cases; record corrected and regressed labels and prompt-clause changes.
2. **Decomposition ablation:** freeze the optimized prompt and compare direct judgment with faithful policy execution; audit the first divergent stage without label feedback.
3. **Concept audit:** independently label condition pairs as equivalent, incompatible, or context-dependent; test the canonical map before using it in a tree or index.
4. **Feature sufficiency audit:** build feature rows, inspect identical rows with conflicting human targets, and add missing evidence before increasing learner complexity.
5. **Tree ablation:** compare fixed reducer, local tree, pooled concept tree, raw prompt, and faithful policy on the same case rows. Preserve fit and reserved partitions; show rules and per-case wins/losses.
6. **Index/grouping ablation:** at a fixed proposal budget, compare semantic-only, behavior-only, concept-aware, and combined ranking. Measure missed compatible pairs and incompatible high-ranked pairs.
7. **Merge ablation:** compare child and joint-parent outputs on every case in the full scope union; report complexity, residuals, class-specific losses, and rejected groups.
8. **Routing ablation:** compare deployed target-blind route with the global fallback and each eligible specialist; separate routing error from judgment error.
9. **Repeatability/cost:** use independent cache namespaces for fresh draws; record variation in plans, observations, tree outputs, labels, usage, and latency. Frozen cache replay is not a robustness replicate.

The [64-case paired table](calitree_casewise_vision_results_20260926.md) tests only direct-versus-default-vision decomposition and contains both corrections and regressions. The [32-case fitted study](../tests/unit/calitree/reports/casewise_decomposition32_20260926.md) shows that explicit conditions can fit named cases after disclosed label feedback. The [ten-case pilot](experiments/assumptions_10_case_pilot.md) found condition instability and feature collisions. None tests the full chain from decision sets through shared concepts, learned trees, indexing, grouping, merging, and routing.

The [historical assumption-3 report](../tests/unit/calitree/reports/assumption3_smallset_20260928.md) preserves the two-case experiments and their limitations. The J16 follow-up branches—evidence-only citation checks, localization/detector work, focused crops, and special spatial-relation observers—have been removed from active code at the user's request. The retained baseline supports frozen criteria, image-based condition checks, optional neutral observations, and ordinary artifact/checkpoint bindings. J16 remains explicitly reviewed as weird/uncertain and excluded from the pilot's fitting and primary comparisons. Its original label and all historical results are preserved. Assumption 3 remains unproven; simplicity and case review take priority over extending the system to fit this outlier.

**Fifty-case expansion:** the [larger Luna study](experiments/calitree_fresh_observation_expanded50.md) completed 19 initial compilations and 218/224 planned observation calls, retaining six transport failures. Of 106 conditions with two valid responses, 95 repeated their status (89.6%); 89/112 planned condition pairs were stable and known. Thirty of 50 cases had complete stable known vectors, but the audit found that this includes condition-scope errors and contradictory descriptions. Reference-label agreement was 57/100 planned case draws, with labels explicitly provisional. This supports an exploratory tree prototype only on semantically reviewed features; it does not verify assumption 3 for unchecked training, nor justify automatic relabeling or quarantine. The production checker and frozen historical criteria were not changed.

**Five-repeat extension:** the [same 50 cases with three additional Luna draws](experiments/calitree_five_repeat_agreement.md) now give a five-draw comparison. A resolved final answer repeats at least 3/5 times in 39/50 cases (78%), at least 4/5 in 36/50 (72%), and 5/5 in 23/50 (46%). The stricter complete known condition vector reaches these thresholds in 35/50 (70%), 30/50 (60%) and 17/50 (34%). Unknown and missing outcomes remain in the denominator and do not vote. There were 199 resolved predictions out of 250 planned; 40 were unknown-driven and 11 were affected by missing observations. Eight-worker execution completed the remaining slots after the user's parallelization request, retaining one interrupted call without retry. This reinforces the distinction between repeatable final judgments and dependable condition features; assumption 3 remains unverified for unchecked training. No labels were changed.

## 7. Implementation sequence

**Earlier next-stage check:** the [small fresh-observation prototype](experiments/calitree_fresh_observation_reliability.md) freezes three existing case plans and measures three new image-based observations per condition. It separates status consistency, unresolved evidence, visual-description review, and provisional human-label agreement. It does not add special-case decomposition machinery. New CaliTree experiments use **GPT-6 Luna** as the main model for cost reasons, per the user's 2026-09-29 instruction; historical artifacts keep their original model identities. A successful small repeatability screen is only permission to explore a tiny feature/tree prototype, not verification of all of assumption 3. **Observed outcome:** the approved Luna pilot completed 13 condition measurements before a transport failure. Across available repeats, 5/6 conditions kept the same status, but only 4/6 were consistent and known. Laundry-scene preservation changed from unknown to absent despite similar visible descriptions. The fresh-reliability screen therefore did not pass; retain the simple baseline and review the generic absent/unknown and preservation boundaries before treating these states as dependable training features. Provisional human labels were not changed.

1. **Stabilize decision-set exports** and show validity, prompt binding, condition findings, and case-level traces in the existing modular canvas.
2. **Define the shared concept schema** with local-to-canonical mappings and explicit unknown/not-applicable states; validate it against independent annotations.
3. **Build feature tables and a small transparent tree learner** with a no-tree fallback for sparse groups. Keep its decisions separate from faithful policy execution.
4. **Add a first-class prompt index** over immutable revisions, with candidate explanations, stale-entry invalidation, and separate construction/inference views.
5. **Use concept-aware clustering and joint merging** while retaining pairwise compatibility probes, full-scope evaluation, measured residuals, and rejection preservation.
6. **Calibrate routing and referral** for the chosen node/model combination with a validated global fallback.
7. **Run the full ablation ladder** with frozen manifests and budgets, so any improvement can be attributed to a particular stage.

The current modular implementation has leaf and multi-child merge controllers, prompt-bound policies, stage freezing, semantic/behavioral clustering options, and target-blind routing. A **shared concept vocabulary, first-class prompt index, and learned decision tree integrated between decision sets and merge acceptance are proposed design work**. Keep this distinction explicit in implementation plans and research claims.
