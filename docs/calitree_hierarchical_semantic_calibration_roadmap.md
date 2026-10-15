# CaliTree roadmap: learn local semantic rules, merge, and validate transfer

**Date:** October 14, 2026\
**Status:** Proposed research and implementation plan. The hierarchy described here is not yet implemented or validated.\
**Scope:** Image-edit satisfaction judging on AURORA, using one editing-model category, one fixed judge-model profile, and one image presentation per case.

**M0 update, October 14:** M0 is complete with a sealed fifty-case, study-relative final test, following explicit approval to disclose historical exposure. The split is 48 training / 12 development / 50 final, with no source overlap. The final class counts are 17 No / 17 Partial / 16 Yes; 49 cases have historical project references, so this is not a globally untouched holdout. No final-set inference was run. See the [M0 protocol and verification](calitree_m0_fifty_case_protocol.md).

**M1 update, October 14:** M1 is implemented in `bound_evidence_v2.py` and audited on the twelve development cases: twelve valid two-stage records, ninety verified question bindings, preserved uncertainty, explicit absence polarity, and separate preservation/intermediate roles. The uncalibrated diagnostic scores 9/12 with two unresolved cases; this is not a learned-policy or final-test accuracy claim. Both development versions and visual disputes are retained. See [M1 evidence and limits](calitree_m1_bound_evidence.md).

**M2–M4 update, October 14:** Scalable fitting, pooled/local baselines, and instruction-only routing are implemented and independently audited. M2 passes 12/24/48/96-row checks and exact reference scoring. Grouped OOF performance is still poor: pooled 16/48, routed 18/48, with routed Partial recall 2/16. The twelve-case development comparison regresses from 7/12 to 6/12. These are verified experimental implementations, not deployment-qualified models. See [milestone evidence and limitations](calitree_m2_m4_semantic_baselines.md). M5–M9 remain future work; the final fifty remain unevaluated.

**Subsequent M2 v4 revision, October 14:** At the user's request, mandatory label gates were removed, check-distribution conflict diagnostics were added, and supervised grouping over M1 evidence replaced the original batch membership for this experimental learner. Local fit improves from 29/48 to 47/48, with the missing observation retained. Held-out-group performance is 23/48 and supplementary development performance 9/12. This establishes local fitting capacity, not reliable transfer. The evidence-dependent groups are a declared extension beyond the earlier instruction-only M4 router. See [v4 implementation and soundness limits](calitree_m2_conflict_regrouping_v4.md).

**M2 portability clarification and v8, October 14:** The user clarified that generalizability means reusable rules that are not specific to case inputs, and accepted local accuracy above 90%; held-out accuracy is not the current acceptance gate. The reviewed v8 policy scores 44/48 (91.7%) using fourteen rules over thirteen semantic predicates. It excludes case/object/instruction literals, image coordinates, raw check-count/majority shortcuts, and observed-case signature routing. A deployment-only artifact contains no training records. A contradictory Yes exception was pruned; rule-level duplicate/ID/order invariance and source-ID-independent fitting were verified. This is semantic portability, not a claim of improved statistical transfer. See [v8 rules and verification](calitree_m2_portable_semantic_v8.md). The final fifty remain unevaluated.

## 1. Goal and central hypothesis

Build a system that learns reusable satisfaction policies from several batches, combines compatible policies using their original examples, and applies a frozen hierarchy to new edits.

The hypothesis is that broader training support will expose shortcuts in local policies, while a hierarchy can retain useful distinctions that one shared policy cannot express economically. Merging is valuable only if it improves new-case decisions or reduces complexity without losing validated performance.

The desired training flow is:

```text
Labeled training examples
  → instruction-bound physical requirements and observations
  → local candidate policies with explicit scopes
  → candidate merges and pooled recalibration
  → validation of policies together with their router
  → frozen inference bundle
```

The desired inference flow is:

```text
Instruction + source image + edited image
  → compile the requested physical checks
  → observe those exact checks
  → determine the applicable frozen policy
  → execute deterministic rules
  → Yes / Partial / No / Unresolved, with a trace
```

The benchmark must distinguish three claims:

1. **Fitting capacity:** a policy can explain the examples used to fit it.
2. **Transfer:** the frozen system performs well on different source images and instructions.
3. **Compression:** a parent can replace children with less complexity while retaining their validated behavior.

A successful local fit establishes only the first claim. The primary study will not measure repeated-model robustness.

## 2. Starting point and observed limitations

The current v16 system already has label-blind physical extraction, instruction-only postcondition compilation, intermediate-state extraction, an executable rule learner, immutable policy artifacts, and a frozen transfer runner.

| Saved policy | Original local accuracy | New shared 12-case accuracy | New Partial recall |
|---|---:|---:|---:|
| G1 | 10/12 | 6/12, 50.0% | 0/4 |
| G2 | 12/12 | 9/12, 75.0% | 1/4 |
| G3 | 10/12 | 9/12, 75.0% | 1/4 |
| G4 | 10/12 | 8/12, 66.7% | 2/4 |

The new set was source-disjoint from all 48 fitting cases and the 144 earlier recorded exclusions. All 48 extraction calls succeeded, and all four policies resolved all twelve cases. These are twelve independent test examples, not 48 independent examples.

The results and underlying records must remain unchanged:

- [Current semantic pipeline](calitree_grounded_semantic_distillation.md)
- [Original local experiment](../logs/exps/261014-instruction-semantic-distillation-v16/report.md)
- [Frozen transfer report](../logs/exps/261014-frozen-semantic-transfer12-v1/report.md)
- [Detailed transfer failures](../logs/exps/261014-frozen-semantic-transfer12-v1/failure_analysis.md)

Five problems constrain the roadmap:

| Problem | Evidence from the saved experiment | Required response |
|---|---|---|
| Local shortcuts | G1 accepts the spoon's rightward displacement despite a failed grasp | Evaluate complete requirement interactions on other examples |
| Relevant facts ignored | All policies accept cylinder removal despite observed disappearance of another sphere | Include instruction-relative collateral conditions in candidate policies |
| Intermediate progress lost | The rising-man case has observed posture change but no accepted intermediate witness | Represent progress toward the specific requested configuration |
| Weak progress overcredited | Slight style changes produce Partial for No-reference edits in G1/G4 | Distinguish relevant intermediate evidence from incidental change |
| Check meanings disagree | `target_result_visible` means powder release in one stage and hand/spoon visibility in another | Bind every observation to the exact question it answers |

There is also a hard engineering blocker: [the current learner](../critical/core/calibration/instruction_semantic_rules.py) accepts only 6–16 rows and builds a population-count lookup table of length `2**n`. A merged pair of twelve-case batches cannot simply be passed to it. Its exact-integer objective scaling also needs a numerical review before increasing sample size.

## 3. Decisions that stay fixed for the primary study

- Use the same AURORA editing-model category as the existing experiments.
- Keep the judge at the existing GPT-6.1 Sol/high profile for the primary comparison. Changing the judge is a separate experiment.
- Use one SOURCE-first image presentation per case. Do not rerun failed slots to obtain a preferred result.
- Use the released mean-score mapping already in the repository: `<0.5 → No`, `[0.5,1.5) → Partial`, `≥1.5 → Yes`.
- Preserve the continuous mean alongside the derived label. Do not call these labels majority votes or infer individual annotator agreement.
- Learn new calibration policies primarily against **dataset reference labels**. Existing teacher policies may seed candidates; their predictions are not replacement ground truth.
- Keep label-bearing fitting and scoring separate from instruction compilation and image observation.
- Freeze a common evidence representation across all policy arms within an experiment.
- Treat a batch as a sampling unit. An inference branch must have a meaningful, observable scope.
- Preserve unsuccessful merges, extraction failures, unresolved outputs, and all original denominators.
- Use an opt-in experimental implementation until the full inference system has passed the final evaluation.

This roadmap does not require perfect local accuracy, a single final root policy, one expert per task category, or a new model call at every tree node.

## 4. Objects the system must represent

### 4.1 Case and reference

A case has an instruction, source image, edited image, source-group identity, task metadata, and dataset reference. Only the instruction and images are ordinary inference inputs. Identifiers belong in caches and audit records, not rule conditions.

Source groups must keep all edits of the same underlying source image together. Use decoded-pixel identity as well as task identifiers and file hashes to catch differently encoded copies.

### 4.2 Bound check program

The compiler produces a versioned instruction-specific program. Each check contains:

- A check ID and the exact physical question.
- The instruction span supporting the requirement.
- Target and reference bindings.
- Its role: requested outcome, identity condition, supporting intermediate, or collateral change.
- Applicability and authorized-change information.
- Dependencies on other checks, where necessary.
- A content hash covering the question, bindings, roles, and schema version.

The scope of a condition must be explicit. A color identifying the source object is different from a color required in the edited result. Moving an existing object is different from adding another object of that category.

### 4.3 Observation record

The observer receives the compiled program and the image pair. It answers those exact checks, returning a physical state, factual evidence, and the matching program/check hashes.

Use `true`, `false`, `unknown`, and `not_applicable` for physical propositions. Keep these separate from the final satisfaction label. A required check marked not applicable is a binding problem or unresolved requirement, not an automatic pass.

Illustrative payload shape, not an existing API:

```json
{
  "program_ref": "content-hash-of-bound-program",
  "observations": [
    {
      "check_id": "requested_powder_release",
      "check_ref": "content-hash-of-this-exact-question",
      "state": "false",
      "evidence": "No falling powder or resulting deposit is visible."
    }
  ]
}
```

The system must reject an observation of hand visibility as an answer to this powder-release question, even if an earlier generic predicate bank used one shared name for both.

### 4.4 Reusable policy

A policy operates on roles, physical states, and supported interactions. It must not branch on a case ID, exact instruction, image hash, object name, or a known answer.

Record the distinction between:

- **World state:** whether a physical proposition is true, false, or unknown.
- **Evidence status:** whether supporting evidence was recorded.

“No supporting evidence recorded” must not silently become “the requested change did not happen.” Resolve unknowns only when their admissible values cannot change the final label. Otherwise return Unresolved.

### 4.5 Policy node and hierarchy bundle

A node needs a policy reference, an applicability scope, child references, complete training-source lineage, validation summaries, complexity, and rejection/acceptance history. A parent's training lineage is the deduplicated union of every descendant's training sources, including failures.

A deployable bundle needs the schema and prompt versions, model profile, policies, router, fallback behavior, and hashes. Training metadata may remain available for audit, but runtime routing cannot inspect membership in the training batches.

## 5. Data and evaluation protocol

### 5.1 Audit exposure before choosing another test set

The original 48 cases and the latest 12 cases are now development material: their failures have informed this design. Preserve their historical reports, but do not reuse them as an untouched final test of the revised system.

The last sampling manifest had 90 No, 66 Partial, and 24 Yes eligible rows before selecting the latest twelve. Subtracting that set leaves 86/62/20 candidate rows under that sampler's exclusions. These are not guaranteed distinct fresh sources and are not a complete audit of earlier project exposure.

Audit earlier manifests and prediction artifacts before declaring any remaining set untouched. If public AURORA does not have enough genuinely unused eligible sources, report the limitation. Do not silently change editor category, relabel cases, or describe a reused set as fresh.

### 5.2 Separate three uses of labels

| Partition | Allowed uses | Excluded uses |
|---|---|---|
| Training | Fit policies, propose checks, discover scopes, train routing | Final generalization claim |
| Development validation | Select candidates, choose merges, tune bounded protocol settings | Calling selected results untouched test performance |
| Final test | Evaluate the single frozen study configuration and predeclared comparison arms | Repairing checks, tuning routes, selecting merges |

All splits are source-grouped. Within development, use grouped cross-validation to reduce dependence on one arbitrary batch assignment. A fold prediction is out-of-fold only if its examples were excluded from fitting that policy and any learned router used for that prediction.

Because the historical sixty examples already informed representation design, cross-validation over them is a development estimate. It is useful for selecting a design, but is not a substitute for the final fresh cohort.

### 5.3 Initial scale

- Use the existing sixty examples for the first engineering and development comparison.
- Start with twelve-case training batches when class and source support permit. Do not create duplicate cases to force balance in a narrow semantic scope.
- Use class weighting and class-specific metrics when a scope is naturally imbalanced. If a scope cannot support a three-label policy, expand it or use the broader fallback.
- The approved M0 reservation is fifty distinct sources, with 17 No / 17 Partial / 16 Yes. Strict global freshness was infeasible; the user explicitly selected a study-relative holdout with historical exposure disclosed. This supersedes the original suggested 36-case pilot, and all final claims must retain the exposure limitation.
- Report operation-family coverage alongside label balance. Synthetic logical fixtures test semantics but do not add human-labeled accuracy observations.

## 6. Milestone roadmap

Each milestone must produce an inspectable artifact and a pass/fail decision. Later stages should not conceal a failed prerequisite.

### M0 — Freeze the research contract and data inventory

**Purpose:** make the experiment answer a fixed question.

Work:

1. Preserve the four original v16 policies, extraction records, and all transfer reports.
2. Create a source-level exposure ledger across previous experiments.
3. Assign training, development-validation, and final-test roles.
4. Predeclare comparison arms, metrics, budgets, and merge tolerances.
5. Record the model, label mapping, presentation, and single-attempt policy.

Deliverables: `study_protocol.json`, `exposure_ledger.json`, split manifests, source hashes, and a baseline snapshot.

**Exit gate:** no source crosses a declared partition; every exclusion and insufficient-data condition is explained. The final test is reserved before new candidate search.

### M1 — Make check binding and uncertainty trustworthy

**Purpose:** ensure calibration operates on the intended evidence.

Work:

1. Introduce the bound-check and observation contracts from Section 4.
2. Make the observer consume the compiler's exact checks, rather than independently rebinding generic predicate names.
3. Include outcome, identity, collateral disappearance/deformation, and relevant intermediate configurations.
4. Add physical intermediates for body pose and compound actions, while preserving distinctions between incidental change and requested progress.
5. Preserve unknowns through derived features. Treat applicability conflicts explicitly.
6. Audit a development subset against the images and instruction. Record disputed judgments instead of silently treating model-produced facts as human annotations.

The target implementation is one instruction-only compilation call followed by one visual observation call that answers all bound checks, including intermediates. This two-call design is proposed; the current v16 experiment uses an image observation plus three text stages. Measure the refactor separately before attributing any improvement to merging.

Deliverables: versioned schemas and prompts, bound observations, rejection diagnostics, and semantic regression fixtures.

**Exit gate:** mismatched question hashes cannot execute; source/edited ordering is explicit; required unknowns do not automatically become No; absence checks cannot pass vacuously. Relevant facts in the five saved failure families remain available to downstream rules.

### M2 — Make rule learning scale beyond one small batch

**Purpose:** support a pooled baseline and merged parents.

Work:

1. Implement a new, versioned learner instead of changing the frozen v16 artifact contract.
2. Replace the `2**n` lookup with row-wise Boolean arrays or packed coverage bitsets whose storage grows with examples and candidates.
3. Review exact-integer scaling for overflow; recompute shortlisted objectives with a reliable reference calculation and deterministic tie-breaking.
4. Keep a bounded grammar and candidate-search budget. Start with the existing maximum of three tests per clause and three clauses per label boundary as a comparison point.
5. Track support by distinct sources and originating batches, not repeated rows.
6. Support quantified conditions over required checks, with explicit dependencies and unknown handling.

The first objective should optimize macro-F1 with class-collapse protection, then consider worst-class recall, accuracy, and complexity. Dataset labels are the primary targets. Teacher agreement is an optional diagnostic or separately declared ablation.

Deliverables: scalable fitter, deterministic evaluator, serialization, candidate-search trace, and reference-scoring tests.

**Exit gate:** fitting and restore/predict work at 12, 24, 48, and 96 rows without exponential allocation in the number of examples. Existing small fixtures agree with reference evaluation under an equivalent grammar. The 96-row fixture can be synthetic; it is a scaling test, not an accuracy result.

### M3 — Establish pooled and local-policy baselines

**Purpose:** determine whether specialization is needed at all.

Work:

1. Freeze the corrected shared extraction representation for this study round.
2. Fit one pooled policy on all training examples, allowing instruction-role interactions.
3. Fit a small set of local candidates per training batch; retain several useful alternatives rather than only a perfect-fit winner.
4. Evaluate candidates with grouped out-of-fold predictions.
5. Record accuracy, every class's recall, coverage, complexity, and error identities.
6. Characterize each candidate's supported scope using instruction requirements rather than the batch ID.

Deliverables: pooled baseline, candidate registry, scope proposals, and out-of-fold result table.

**Exit gate:** both pooled and local inference execute against the same cached evidence. Local candidates that collapse a supported label or have no measurable applicable scope are not promoted as specialists.

### M4 — Build and evaluate routing before accepting merges

**Purpose:** measure the policy a real unseen case will actually receive.

Start with a shallow, inspectable router using instruction-derived roles: operation, whether the original instance must be retained, whether a relation is required, and whether the request has multiple dependent outcomes. Add evidence-state routing only as a separate declared extension.

Work:

1. Learn or select scope predicates using training/development data only.
2. Define behavior for overlapping scopes, mixed-operation instructions, and unsupported scopes.
3. Use a validated pooled policy as the default fallback.
4. Predeclare whether an unresolved specialist result falls back or remains unresolved; evaluate that entire path.
5. Measure actual routing performance, fallback frequency, and an oracle-routing upper bound separately.

Training-batch membership, dataset category labels unavailable at deployment, and true satisfaction labels are prohibited routing inputs. Do not run every expert and choose the most favorable answer.

Deliverables: frozen router schema, routed-local baseline, and routing traces.

**Exit gate:** a new case with no reference label can be routed reproducibly. Reported system accuracy uses actual routing; oracle routing is clearly diagnostic. Adding a tree node does not require another visual observation.

### M5 — Propose candidate merges from semantics and behavior

**Purpose:** spend recalibration effort on plausible parent policies.

Work:

1. Compute structural overlap in required roles, dependencies, and policy conditions.
2. Construct a transfer matrix on training/development probes, retaining class-level counts and uncertainty.
3. Separate agreement on correct cases from agreement on mistakes.
4. Include complementary-error pairs that may benefit from joint recalibration even when mutual transfer is imperfect.
5. Rank a bounded number of pairs with deterministic tie-breaking.

Semantic similarity proposes a merge; it does not authorize it. Mutual transfer is evidence, not an absolute prerequisite. Shared failures, such as all four policies ignoring collateral disappearance, are a reason to examine a missing condition rather than evidence of successful compatibility.

Deliverables: candidate-pair list, compatibility diagnostics, and rejected-pair reasons.

**Exit gate:** every proposal can be explained using reusable structure and measured behavior. No final-test labels or outcomes participate.

### M6 — Fit parents on the full union and validate replacement

**Purpose:** turn merging into supervised learning over broader support.

For each candidate pair:

1. Deduplicate and pool all descendant training examples, including failures.
2. Use child conditions as warm-start candidates, alongside the common grammar.
3. Fit the parent against original dataset references, not a vote of child outputs.
4. Derive an applicable parent scope from the children's supported domains.
5. Compare the candidate replacement with the existing routed system on development validation.
6. Check global metrics, each label, and predeclared descendant scopes.
7. Accept, reject, or mark insufficient evidence. Preserve all children and candidate history.

A parent may share a common condition while retaining instruction-dependent interactions. For example, relocation can require identity and no unauthorized duplication, while addition permits an increased count. A collateral-change condition may be shared, but its materiality must remain instruction-relative.

Deliverables: candidate parent artifacts, union manifests, before/after routing traces, and acceptance decisions.

**Exit gate:** the selected parent passes the predeclared merge rule in Section 8. Higher union training accuracy alone never accepts a merge.

### M7 — Iterate into a bounded hierarchy

**Purpose:** discover useful abstraction without forcing complete collapse.

Work:

1. Repeat proposal, pooled fitting, and validation for accepted parents and remaining leaves.
2. Recheck all affected descendant scopes after every promotion.
3. Retain children when their distinctions remain useful.
4. Stop when no candidate passes, evidence is insufficient, or the search budget is exhausted.
5. Allow the deployable result to remain a small forest plus pooled fallback.
6. Record cumulative model-selection effort; repeated use of validation remains development.

Suggested initial search limits are depth three, at most two active local candidates per initial batch, and at most 24 parent proposals across the study round. These are proposed engineering defaults, to be sealed before the run, not established optimal settings.

Deliverables: hierarchy bundle, provenance graph, final router, and complete rejected-merge log.

**Exit gate:** every active node has validated scope and support, the graph is acyclic, and restoring the bundle reproduces all saved development predictions.

### M8 — Run the decisive frozen comparison

**Purpose:** establish whether hierarchy improves transfer over simpler alternatives.

Required arms:

| Arm | Role in the comparison |
|---|---|
| Strong flat judge | End-to-end reference using the same model and image presentation |
| One pooled semantic policy | Tests whether more training data alone solves the problem |
| Routed local policies without merging | Measures specialization and routing without parent induction |
| Merged and recalibrated hierarchy | Tests the added value of merging |

All three semantic arms use the same bound evidence, training sources, label mapping, and evaluator. Share extraction across arms. Match search budgets where possible and report both per-policy and total system capacity. Include a pooled policy with a comparable total rule budget so extra capacity is not mistaken for a benefit of hierarchy.

Select the study configuration on development data, then freeze all arms before observing final-test results. Report the entire predeclared comparison; do not pick a new winner and claim a second independent result on the same test.

Deliverables: paired case-level results, class recalls, macro-F1, accuracy, coverage, confusion matrices, source-level uncertainty estimates, route traces, and cost/latency counts.

**Exit gate:** the outcome is classified as improved transfer, comparable compression, inconclusive, or negative using Section 10. Any repair prompted by the final test starts another development round with a different final set.

### M9 — Integrate the validated strategy into CaliTree

**Purpose:** reuse existing infrastructure without conflating different executors.

Integrate only after the standalone system is reproducible and its value is understood. Reuse durable node lineage, acceptance interfaces, and serialization patterns where their contracts fit. Add a separately versioned adapter for physical semantic rules; existing prompt/ordinal executors must not silently interpret the new artifact.

Deliverables: opt-in builder configuration, executable artifact adapter, load-time validation, CLI entry points, and user-facing inspection of policy scope and decision traces.

**Exit gate:** saving/restoring a tree preserves routing and decisions; inference does not depend on training-time Python objects or labels; legacy pipelines still load unchanged. A negative research result should be preserved as an experiment rather than made the default.

## 7. Proposed implementation map

Existing components to examine and reuse:

| Component | Existing location | Intended use |
|---|---|---|
| Physical vocabulary | [observable_facts.py](../critical/core/decision/observable_facts.py) | Seed concrete questions, with corrected binding |
| Instruction compiler | [postcondition_binding.py](../critical/core/decision/postcondition_binding.py) | Basis for instruction-only compilation |
| Intermediate evidence | [intermediate_facts.py](../critical/core/decision/intermediate_facts.py) | Extend through a new version and explicit question bindings |
| Role interactions | [instruction_role_facts.py](../critical/core/decision/instruction_role_facts.py) | Preserve useful relocation/addition distinctions |
| Local rule learner | [instruction_semantic_rules.py](../critical/core/calibration/instruction_semantic_rules.py) | Reference implementation; not a scalable parent fitter |
| Durable calls | [calls.py](../critical/core/decision/calls.py) | Single-attempt budgets, histories, and exact replay |
| Calibration registry | [registry.py](../critical/core/calibration/registry.py) | Immutable policy publication |
| Frozen evaluation | [calitree_semantic_transfer.py](../run/calitree_semantic_transfer.py) | Reuse audit and shared-evidence patterns |
| Modular tree infrastructure | [structure documentation](calitree_structure.md) | Node lineage, merge coordination, adapters, and routing |

Suggested new modules, **not existing APIs**:

```text
critical/core/decision/bound_evidence_v2.py
    Implemented M1 bound program, exact-question observation, validation, and hashes

critical/core/calibration/semantic_hierarchy/
    schemas.py       Node, scope, policy, and bundle contracts
    rule_search.py   Scalable bounded candidate fitting
    evaluation.py    Grouped scoring and uncertainty-aware execution
    scopes.py        Observable applicability predicates
    routing.py       Frozen routing and fallback behavior
    similarity.py    Structural and behavioral proposal ranking
    merge.py         Parent fitting and replacement evaluation
    builder.py       Bounded hierarchy construction and lineage

run/calitree_semantic_hierarchy.py
    Prepare, extract, fit, evaluate, replay, and report modes

run/audit_calitree_semantic_hierarchy.py
    Independent payload, partition, routing, policy, and metric checks
```

A pure scoring interface should accept records and a frozen policy. Fitting should explicitly require targets and source groups. Those separate signatures make label leakage and accidental inference-time refitting easier to detect.

## 8. Proposed merge acceptance protocol

Seal actual thresholds in M0. The following are starting defaults for development, not claims that these thresholds guarantee generalization.

**Structural gates:**

- All artifact and bound-question hashes match.
- Parent source lineage equals the full deduplicated child union.
- The candidate and current system are evaluated on identical validation cases.
- Routing uses only permitted inference inputs.
- Every positive clause has distinct-source support; an accepted parent's claimed shared conditions must have support across more than one originating batch.
- Missing evidence, unsupported applicability, and contradictory observations retain explicit handling.

**Empirical replacement gates:**

- Macro-F1 does not decrease relative to the current routed system.
- Accuracy loses no more than one case over the aggregated selection cohort.
- Partial recall does not decrease.
- No other label or predeclared descendant scope loses more than one correct case.
- Coverage does not decrease in the primary experiment. A coverage/accuracy tradeoff belongs in a separate selective-prediction arm.
- Require either a measured improvement or a strict reduction in active rule complexity with no loss of accuracy, macro-F1, or class recalls.

Apply class and subgroup regression allowances only when their denominators are adequate; initially target at least eight reference cases per label in the aggregated validation view and eight cases per protected scope. With smaller support, mark the merge exploratory or insufficiently supported rather than treating a noisy pass as established evidence.

Validation may consist of aggregated grouped out-of-fold predictions. Every such prediction must exclude that case from policy fitting and learned routing. Selection over those predictions is still development, not final evaluation.

Threshold changes require a new protocol revision and a disclosed development comparison. Do not loosen a gate after seeing the final-test result.

## 9. Training and inference pseudocode

These describe the proposed behavior, not callable functions already in the repository.

```python
# Training: no final-test cases are available to this routine.
evidence = extract_bound_evidence(training_cases + development_cases)
pooled = fit_pooled_policy(evidence.training, references.training)
locals = fit_local_candidates(training_batches, references.training)
router = select_router(locals, pooled, development_protocol)
system = freeze_candidate(locals, router, fallback=pooled)

for pair in bounded_merge_proposals(system, development_protocol):
    fit_sources = union_of_all_descendant_training_sources(pair)
    parent = fit_policy(
        evidence.for_sources(fit_sources),
        references.for_sources(fit_sources),
        warm_candidates=pair.policies,
    )
    candidate = replace_with_parent(system, pair, parent)
    decision = compare_actual_routed_systems(
        before=system, after=candidate,
        validation=development_protocol.validation,
    )
    log_candidate_and_decision(candidate, decision)
    if decision.accepted:
        system = candidate

return export_frozen_bundle(system)
```

```python
# Inference: neither targets nor training memberships are accepted.
program = compile_instruction(instruction, frozen_schema)
observations = observe_exact_checks(source_image, edited_image, program)
record = validate_and_derive(program, observations)
node = frozen_router.choose(program.roles, permitted_record_fields(record))
decision = execute_frozen_policy(node.policy, record)
return decision.label, decision.trace
```

If extraction fails, preserve the failure and return Unresolved under the declared fallback policy. Do not change the prompt, choose another model, or resample during scored inference.

## 10. Metrics, success criteria, and negative outcomes

Always report accuracy over the full sample, macro-F1, all three recalls, confusion counts, coverage, actual routed performance, and distinct-source counts. Include case-level paired differences against the pooled policy and routed-local baseline.

Use source-level paired uncertainty estimates for system differences. Report confidence intervals and raw discordant counts; a favorable point estimate from a small test is not conclusive evidence. Balanced-set accuracy also does not estimate deployment accuracy under a different class distribution without an additional representative evaluation.

Classify the outcome as follows:

| Outcome | Interpretation |
|---|---|
| Better macro-F1, protected label performance, and convincing paired evidence | Evidence supporting improved transfer |
| Favorable point estimates but wide uncertainty | Promising, inconclusive pilot |
| Comparable decisions with fewer active rules or lower cost | Successful compression; no claim of higher accuracy |
| Pooled policy matches or beats the hierarchy | Prefer the simpler pooled design unless another measured benefit matters |
| Oracle routing helps, actual routing does not | Routing remains the bottleneck |
| All policy arms fail on the same missing/misbound facts | Repair representation on development data before further merging |
| Accuracy increases by sacrificing Partial or dropping cases | The primary three-label objective has not been achieved |

Do not set 100% local accuracy as the completion criterion. Do not select a new policy separately for each final-test case. Do not count repeated source variants or multiple policy predictions as independent observations.

## 11. Required tests and audits

| Area | Required behavior |
|---|---|
| Exact question binding | Powder-release observations cannot be replaced by object-visibility observations |
| Compound requests | A spatial success cannot bypass a required grasp/action outcome |
| Preservation | Observed disappearance and deformation remain separate, available conditions |
| Instruction roles | Extra instances mean different things for relocation and authorized addition |
| Intermediate states | Body-pose progress is representable; incidental style changes are not automatically meaningful progress |
| Unknowns | Lack of proof is not silently rewritten as a negative physical observation |
| Source independence | Sibling edits and pixel-identical source files cannot cross partitions |
| Scalability | Parent fitting works beyond sixteen examples without exponential row-index tables |
| No inference fitting | Replacing fitting APIs with exceptions does not affect frozen prediction |
| Label isolation | Changing evaluation labels cannot change compiler payloads, observations, routes, or predictions |
| Merge lineage | Failed descendant examples remain in the parent scope and metric denominator |
| Routing | Reported scores reproduce the actual deployable route and fallback |
| Serialization | Export/restore reproduces policies, applicability, and predictions exactly |
| Leakage audit | Reference labels, case answers, and policy-selection feedback never reach inference model calls |
| Cost accounting | Replays make zero calls; each scored stage retains its first attempt |

Logical fixtures establish program behavior, not human satisfaction accuracy. Observational errors require image-based inspection on development examples, with disputed interpretations recorded.

## 12. Experiment sequence and attribution

Run these in order, preserving a separate result for each change:

1. **Representation study:** old evidence pipeline versus exact-bound evidence on development cases, using declared comparable readouts.
2. **Scalable learner study:** verify search and execution, then establish the pooled reference.
3. **Locality study:** pooled policy versus local policies with actual routing.
4. **Merge study:** routed locals versus merged/recalibrated parents, holding evidence fixed.
5. **Capacity control:** compare against a pooled policy with a comparable total rule/search budget.
6. **Frozen final comparison:** all predeclared arms on the reserved new set.

Useful later ablations include semantic-only proposal ranking versus behavioral ranking, one candidate per batch versus several, and shared-parent-only versus parent-with-retained-children. Choose the ablation budget before observing their validation outcomes. Do not launch every possible combination by default.

## 13. Calls, caching, and execution budget

The current v16 fresh-case path has up to four model stages per case: one image observation and three text stages. The proposed bound-evidence path targets two stages: instruction compilation and one visual observation. It is not valid to assign v16 accuracy to that untested consolidation.

For `N` unique new examples and a validated two-stage extractor, the proposed extraction ceiling is `2N` calls. All semantic policy arms reuse those records, so the number of branches does not multiply image calls. A matched flat-judge arm adds `N` calls. If a new prompt/schema changes the evidence, it requires a new cache version and explicit accounting.

Initial rule search, transfer matrices, routing evaluation, and parent fitting should be offline over cached evidence. An LLM proposal stage is optional later; if introduced, log and bound its training-only calls separately.

Preflight must show sample counts, stage counts, completion-token caps, concurrency, and expected cache reuse before live execution. Retain the existing durable ledger and endpoint configuration. Report returned token usage rather than inventing a fixed dollar estimate in this roadmap.

Parallelize independent cases and offline candidate evaluations. Keep dependent stages sequential within a case and ensure concurrent workers do not share a mutable policy or call-budget ledger unsafely.

## 14. Delivery order and decision checkpoints

| Work package | Contents | Decision before moving on |
|---|---|---|
| A | M0 protocol, exposure audit, reserved partitions | Enough data and a reproducible comparison exist |
| B | M1 bound evidence and semantic regression fixtures | Checks mean the same thing across stages |
| C | M2 scalable fitter and M3 baselines | Larger pooled policies can be fit and assessed |
| D | M4 routing and M5 merge proposals | Specialization has a measurable scope and deployable route |
| E | M6 parent fitting and M7 bounded hierarchy | Parents earn broader scope or compression through validation |
| F | M8 frozen evaluation and independent report | Evidence supports improvement, compression, or a documented negative result |
| G | M9 opt-in integration | Artifact/runtime compatibility is demonstrated |

The first implementation slice should complete B and C before building a large hierarchy. Otherwise the project risks adding a merge mechanism around inconsistent observations and a learner that cannot handle the pooled data.

## 15. Completion checklist

- [ ] A bound observation always answers the exact compiled physical question.
- [ ] Missing proof, physical contradiction, and not-applicable are handled distinctly.
- [ ] The fitter supports combined batches with bounded computation and stable metrics.
- [ ] Local policies have observable scopes and distinct-source support.
- [ ] The pooled policy is a real, competitive baseline using the same data.
- [ ] Merge candidates are refit on original reference labels and full descendant unions.
- [ ] Acceptance evaluates the actual routed replacement and protects all three labels.
- [ ] Failed merges retain children and complete audit history.
- [ ] Inference loads a frozen bundle without targets or refitting.
- [ ] The final study uses reserved source-disjoint cases and reports all predeclared arms.
- [ ] Independent replay reproduces routes, labels, metrics, and policy hashes.
- [ ] The final conclusion distinguishes transfer, compression, uncertainty, and failure.

## 16. Research context

The general idea is related to [hierarchical mixtures of experts](https://www2.bcs.rochester.edu/sites/jacobslab/abstracts.html), which combine specialized models in a tree, and [model-based recursive partitioning](https://research.wu.ac.at/en/publications/model-based-recursive-partitioning-20/), which fits models within data-dependent partitions. These provide architectural context; they do not establish that this particular semantic decomposition, bottom-up merging, or acceptance protocol works.

The proposed contribution to test is a shared physical evidence representation, instruction-dependent satisfaction rules, and parent recalibration whose additional scope is justified by measured transfer. The experiment should be allowed to conclude that one pooled conditional policy is sufficient.
