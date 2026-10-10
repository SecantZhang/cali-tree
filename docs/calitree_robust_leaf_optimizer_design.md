# Robust casewise leaf-judge optimization

Status: v3 implementation added 2026-10-07; opt-in missing/nested evidence repair added 2026-10-08; v4 independent scheduling and adaptive proposer added 2026-10-09. The user-selected current v5 default disables semantic auditing and uses flat all/some/none counting. See [implementation and usage](calitree_robust_leaf_optimizer.md) for versioned contracts and pilot commands. Historical audited designs below remain references rather than the current default.

## Goal and scope

### Degree of fulfillment (v7, 2026-10-09)

The user-selected change measures degree of fulfillment, independently of reported confidence or repeat agreement.
Observe each required condition on a factual 0/.5/1 anchored scale. Preserve exact requirement budgets across edits:
equal initial requirement/facet weights, equal conserved splits, zero auxiliary weight, no positive-mass deletion.
The authoritative weighted score >=.9 means satisfied, <=.1 nonsatisfied, and intermediate values partial. Unknown
components contribute [0,1] bounds; the label resolves only when the full aggregate interval has one category. This can
leave a resolved overall label with an uncertain atom, which still fails strict confidence gates until evidence exists.

V7 stores and hashes its roots, rational allocations, anchors, thresholds and scoring mode. Both comparison arms use
the same label-free seed and Luna grading calls; binary derives strict fully-complete votes (score 1) and fulfillment
uses the weighted bounds. Independent optimization/repeat histories plus both same-observation readouts separate
aggregation changes from newly sampled model behavior. Historical boolean-prompt comparisons remain descriptive.
Labels and feedback reach only optimization, not compilation or scoring. Auditing and parent construction remain deferred.

### Endpoint repair corrections (v6, 2026-10-09)

The audit-free counting variant now has an explicit `--scoring endpoints` runtime: preferred two-to-three distinct
endpoint dimensions, exact original quotes and necessity explanations, rejection of explicit progress/helper votes,
and targeted all-pass/all-fail diagnosis. Repairs declare predicted per-condition observations; measured outcomes return
to the next proposer instead of hiding valid but ineffective additions. Single irreducible conditions remain allowed,
with their inability to represent partial reported explicitly. Literal provenance and model explanations do not certify
semantic necessity or sufficiency.

Qualification requires all five labels match, all five runs resolve and the existing confidence/consistency gates.
One predeclared transport-only recovery check per report uses a new slot and preserves all original observations/costs;
valid wrong/uncertain, schema-invalid and interrupted attempts are not resampled. Recovery selection excludes labels.
Raw and effective accurate-and-repeatable case ratios are separate. Auditor/readout remain disabled, source-relative
visual evidence remains essential, and stable reference disagreements are reported without relabeling. See usage for
artifact versions, reservations and the fresh same-twelve-case comparison.

### User-selected counting variant (2026-10-09)

Compile flat, independent necessary conditions from the original instruction, each with a positive fulfillment meaning:
pass means that condition is satisfied. All pass yields satisfied, all fail yields unsatisfied, a known mixture yields
partial. Unknown, invalid or failed observations and an empty applicable set remain unresolved. Code computes this count;
there is no semantic audit and no model readout. Confidence and repeat stability still govern empirical robust acceptance.

This changes the scoring interpretation: partial means some required conditions hold, rather than a model judgment about
how much editing progress occurred. Supporting inventories, progress checks and unvisited tree alternatives cannot be
silently treated as required-condition votes. Fresh v5 compilation and explicit artifact dispatch preserve historical
v2/v3/v4 behavior. Structural/provenance validation remains, while semantic preservation is deliberately not model-audited.

Optimize one CaliTree leaf for one instruction and its source/edited evidence so that it returns the reference label reliably across repeated executions, while preserving the meaning of the instruction.

Each leaf contains a decomposed decision program that can be a flat set or an ordered conditional tree, its executable checks, a fixed aggregation rule, and an auditable repair history. The optimizer operates locally. Parent construction, cross-case sharing, and generalization remain future CaliTree responsibilities.

Here, **reference label** means the supplied case label (`yes`, `partial`, or `no`). Agreement with the original undecomposed scorer is a separate fidelity measurement. If the desired target is instead the original scorer, record that choice explicitly; reproducing that scorer does not establish agreement with the case label.

## The proposed idea

1. Decompose the instruction and judging prompt into individual scoring decisions, arranged as a flat set or an ordered tree with explicit branch conditions.
2. Execute those decisions and combine their observations into a case label.
3. If the combined label matches the reference, identify individual decisions whose confidence or repeat agreement is too low. Repair them, or remove them when removal preserves the requirements.
4. If the combined label differs from the reference, inspect the component decisions and their dependencies to locate plausible causes. Repair or safely remove the implicated rules.
5. Generate bounded structural edits from TextGrad-style textual feedback, then re-execute each candidate program.
6. Maintain a GEPA-inspired Pareto frontier of candidates with complementary agreement, coverage, stability, and cost. Choose frontier parents for subsequent repair rather than always editing a single incumbent.
7. Select a candidate that passes the acceptance policy, freeze it, and verify it with fresh repeated executions before declaring the leaf locally robust.

The idea makes sense: it turns whole-prompt optimization into targeted repair of an inspectable program. Its two acceptance conditions are **agreement with the reference** and **repeatable execution**. Neither condition alone certifies that every component is semantically correct.

## What a leaf contains

| Element | Purpose |
|---|---|
| Original instruction and rubric | Immutable source of the requested semantics |
| Requirement ledger | Exact instruction provenance and coverage obligations |
| Requested outcomes | Edits whose fulfillment determines the final label |
| Supporting checks | Evidence needed to identify targets, references, or relations |
| Bindings and evidence dependencies | Keep checks about the same objects and pass required observations |
| Ordered tree and branch policy | Define the entry node, child order, activation conditions, and false/unknown branch behavior |
| Applicability | Record whether each requested outcome applies to this case |
| Checker criteria and templates | Define what each executable decision measures |
| Aggregation | Convert requested-outcome states into the overall label |
| Thresholds and execution configuration | Fix how robustness is assessed |
| Traces, textual feedback, frontier and lineage | Explain visited paths, node feedback, transactions, objective vectors, dominance decisions, audits, and selection |

A supporting observation is not a completed edit. For “close her jacket fully,” detecting a woman and a jacket supplies context but does not earn completion credit. Supporting observations may legitimately be negative, depending on their question wording.

Preserve the existing runtime's outcome states: `complete`, `partial`, `absent`, and `unknown`. Applicability is separate. Binary evidence checks can feed a fulfillment decision, but must not erase the distinction between partial progress and absence. An instruction with one requested outcome can still be partially fulfilled.

For applicable requested outcomes, use the fixed reducer:

- All complete → `yes`.
- All absent → `no`.
- Otherwise, known progress → `partial`.
- Required unknowns, invalid observations, unknown applicability, or no applicable requested outcomes → unresolved.

Do not replace this reducer with an average over all checks. Changes to the reducer would be a separate experiment.

## Flat decisions and ordered conditional trees

The executable program inside one CaliTree leaf can be a flat collection of checks or an ordered decision tree. This internal tree evaluates one case; it is separate from future CaliTree parent nodes that may generalize across cases.

For example, “Make the car red and remove its roof rack” can use:

```text
1. Identify the same target car in the source and edited images.
   PASS: evaluate 2, then 3 using the saved target binding.
     2. Assess whether the requested car-color change is complete, partial, or absent.
     3. Assess whether the requested roof-rack removal is complete, partial, or absent.
   FAIL / UNKNOWN: record why the target cannot be established;
                   dependent outcomes remain unresolved unless an explicit,
                   semantically justified rule determines their states.
4. Aggregate the requested outcomes using the fixed reducer.
```

Here, 1 passing enables **both** 2 and 3; they are not mutually exclusive alternatives. The first implementation should execute eligible siblings in saved order. A mutually exclusive branch must be declared separately. Flat execution is the special case where all required checks are eligible without a gate.

Every node stores its role, predicate/checker, binding, evidence dependencies, ordered children, and transitions for each possible observed state, including unknown. Boolean gates use explicit pass/fail/unknown results; fulfillment nodes retain complete/partial/absent/unknown. A fulfillment node used as a gate must name exactly which states activate each child. Do not treat partial or unknown as an implicit pass.

Keep two edge types distinct:

- **Evidence dependency:** a child needs an ancestor's binding or observation to interpret its question.
- **Control-flow condition:** a child executes only when a specified ancestor result occurs.

The initial representation is a rooted, acyclic ordered tree, with evidence references to valid ancestors. Shared checks with multiple parents would require a separately specified DAG extension; do not silently duplicate observations or introduce ambiguous traversal.

Branch behavior must distinguish these cases:

| Branch event | Effect on execution and scoring |
|---|---|
| Gate passes | Activate the declared children and preserve inherited bindings |
| Gate fails, but entails a requested outcome state | Record that state as an explicit inference with its rule and parent evidence; do not pretend a child was queried |
| Gate fails without such an implication | Mark dependent required outcomes unresolved; do not remove them from aggregation |
| Gate is unknown, invalid, or failed in transport | Preserve the uncertainty and block dependent execution as declared |
| An instruction-defined condition genuinely does not apply | Record justified non-applicability, distinct from an execution skip |
| Another independent branch remains eligible | Evaluate it normally; failure in one branch cannot silently discard other requirements |

For instance, an absence of the target jacket does not mean “jacket closure is not applicable.” A false support observation may be useful evidence, while failure to identify the target may be uncertainty. Each node's contract determines the implication; there is no universal false-parent rule that fits every edit.

Every terminal execution path must account for every requirement through observation, a justified inference, legitimate non-applicability, or an explicit unresolved result. Static validation rejects paths that drop required coverage. Routing on a reference label, expected answer, or optimizer feedback is forbidden.

Optimization may add a gate, revise a branch condition, reorder siblings, split a node into a subtree, replace a subtree, repair a binding, or flatten an unnecessary gate. These are immutable transactions subject to the same semantic audit. A shortcut is acceptable only if its declared inference preserves the outcome semantics; reducing calls by leaving required checks unaccounted for is invalid.

Save the full visited path, each transition, eligible and queried nodes, inferred states, skip reasons, and each node's dependency context. Hash traversal and branch policies as part of the executable program. Topology, ancestor, or routing edits invalidate affected descendants and final aggregates in the cache.

## Confidence, repetition, and correctness

These are different measurements and should remain separate in the artifact.

| Signal | Meaning | Limitation |
|---|---|---|
| Reported confidence | A check's generated confidence in its answer | A confident answer can be wrong |
| Label-token probability, when available | Model probability of the encoded output category | Not automatically a calibrated probability of correctness |
| Repeat agreement | How often a decision produces a particular state across repeated executions | Consistency does not establish correctness |
| Final target agreement | How often the whole program returns the case reference label | Several incorrect component judgments can yield the right final label |

Do not average these signals into one unexplained “probability,” and do not multiply component confidences as though the checks were independent. Checks share images, models, wording, and dependencies.

For a fixed program and check i, record R scheduled draws and counts for every state, including unknowns and failures:

    observed_frequency_i(state) = count_i(state) / R
    modal_consistency_i = max(count_i(valid_state)) / R
    final_target_agreement = count(final_label == reference_label) / R
    final_coverage = count(final_label is resolved) / R

If there is a justified expected state for a check, also record its observed frequency. Otherwise report the full distribution and modal consistency; do not manufacture an atomic ground-truth label from the case label.

A check that returns the wrong state in all R draws has perfect modal consistency but is a repair candidate for label mismatch. A check that varies despite the correct final label is a robustness candidate. These correspond to the two branches of the proposal.

Start each repeat at the program entry point and execute the entire applicable control flow; do not independently sample children while holding uncertain parents artificially fixed. Save the upstream observations used by dependent checks. Distinguish checks that were queried from those blocked or inferred by dependency handling. A skipped check is not an independent successful observation. For conditional nodes, use two explicit denominators:

    activation_rate_i = eligible_draws_i / scheduled_program_draws
    conditional_frequency_i(state) = queried_count_i(state) / eligible_draws_i

An eligible call that fails stays in the denominator. A node with zero eligible draws has unavailable conditional consistency, not perfect consistency. Store justified inferences separately from queried observations. The earlier frequency over all R draws describes how often the whole execution produced that node's observed state, not its conditional repeatability.

Require a preset minimum number of eligible observations before claiming a reached node is repeat-stable. Low activation cannot be used to hide a weak required check. Report per-requirement end-to-end resolution across all R draws alongside conditional node statistics. A node on an unvisited alternative branch remains untested; local verification does not certify every possible path. Do not force an impossible branch open merely to manufacture evidence.

## Preset robustness policy

Freeze the following before optimization:

- Screening, confirmation, and final-verification repeat counts.
- Minimum repeat agreement for each required decision.
- Minimum final target agreement and resolved coverage.
- Confidence source and confidence threshold, if confidence is part of the experiment.
- How repeated confidence values are summarized, for example their minimum or a chosen lower quantile.
- Search-round, candidate, frontier-size, proposal, call, token, total-node, maximum-depth, and worst-case executed-check limits.
- Minimum eligible observations for conditional-node assessment, node activation semantics, and allowed terminal-path coverage.
- Pareto objective definitions, comparison draw counts, parent-sampling policy, tie/pruning rules, and any epsilon tolerance for dominance.

Thresholds are configuration, not values chosen after observing which candidate passes. For illustration only, four agreeing draws out of five gives an observed frequency of 0.8. That small sample does not establish an underlying success probability of at least 0.8.

If a required repeat-agreement or configured confidence gate fails, mark the decision as not yet meeting the local robustness criterion. Missing confidence is recorded as unavailable. A protocol requiring confidence cannot silently pass that check; a repeat-only protocol must be selected explicitly in advance. Do not silently switch between reported confidence and token probabilities.

Low confidence triggers investigation. It does not itself justify deleting a requirement or forcing a different answer.

## Branch A: combined label already matches

The matching label is provisional until repeated execution confirms it.

1. Run the planned repeated whole-program executions.
2. Inspect component state distributions, confidence where available, bindings, and dependencies.
3. Identify weak required decisions, including unstable supporting checks that block fulfillment.
4. Diagnose ambiguity, over-compound criteria, inconsistent target identity, irrelevant constraints, missing progress evidence, or contradictory upstream observations.
5. Propose a bounded repair: clarify criteria, repair bindings, split a compound check, add missing evidence checks, or remove a redundant/unjustified rule.
6. Validate requirement coverage and dependencies; conduct a label-blind semantic audit.
7. Re-evaluate the entire candidate with fresh draw slots. A candidate with a quality regression cannot replace a qualifying incumbent merely because it is cheaper; a valid tradeoff candidate may remain on the exploratory frontier under the policy below.

A correct aggregate can hide compensating errors. Therefore, matching the reference is not a reason to skip component inspection.

## Branch B: combined label differs or is unresolved

First distinguish execution failures from semantic mismatches. A failed request, invalid response, or unresolved dependency must not be described to the proposer as proof that a visual property is absent.

For a resolved mismatch, use the final-label constraints to identify plausible offending outcomes:

| Reference | Implication under the fixed reducer | Investigation |
|---|---|---|
| `yes` | Every applicable requested outcome must be complete | Inspect each non-complete requested outcome and its evidence/dependencies |
| `no` | Every applicable requested outcome must be absent | Inspect reported progress or completion and whether it is supported |
| `partial` | Known progress exists, but not every requested outcome is complete | Inspect how progress and incompleteness are represented; the label does not identify a unique faulty check |

The intuition “a satisfied label means every decision must say yes” holds only when those decisions are applicable, necessary fulfillment conditions with positive wording. It does not hold for arbitrary supporting or diagnostic questions.

Trace a suspected error through the dependency graph before editing the final fulfillment rule. A mistaken target binding can invalidate several downstream judgments; changing their thresholds independently would hide the cause.

Use the images, instruction, reference label, component observations, and prior rejected-edit diagnostics to propose a repair. The proposer may see the reference label. Executable checkers must not see it, desired answers, or optimization feedback. The semantic auditor compares the candidate with the original instruction without seeing the reference label or target-conditioned repair rationale.

The case label is a constraint, not a verdict on each component. If faithful visual judgments consistently contradict it, retain the evidence and return an unresolved reference conflict for review rather than weakening requirements until the label matches.

## Missing and nested evidence repair

When supporting checks pass but the final result disagrees with a `partial` reference, investigate whether the checks record sufficient evidence for the requested **property, relation, and extent**. Passing weak proxies is not equivalent to establishing the complete requested outcome. The repair may add an overlooked evidence check or refine a broad support with a nested visual investigation; criterion revision is not the only option.

For “Turn the image into a drawing made from chalk,” the saved forced-decomposition experiment observed chalk-like treatment and drawing-like forms, then scored complete. A proposed refinement is:

```text
n1: Is chalk-like treatment present?                 [support; images]
n2: Are drawing-like forms present?                  [support; images]
  n2a: Does the conversion cover the image as a whole,
       or does substantial photographic appearance remain?
                                                    [support; images + n2 evidence]
n3: Judge the original requested transformation.     [fulfillment; n1/n2/n2a evidence only]
```

This is a proposed diagnostic question, not a new observation from the live experiment. A broad parent may pass while its finer child fails. If verified evidence establishes genuine progress and incomplete conversion, the original fulfillment can become partial. If necessary evidence is unknown, it remains unresolved. All four calls count toward the execution cap; supporting checks do not become new requested edits or receive completion credit. No particular chalk technique or removal of the pictured subjects is required.

The instruction, rubric, requirement ledger, requested outcome and its target/reference bindings remain frozen. Each added or revised support records its node-to-requirement mapping and an exact source phrase in the transaction history. This prevents unanchored additions structurally; it does not prove that an anchored criterion is semantically justified. Atomic validation checks the entire edited graph, updated readout dependencies, activation states, coverage and four-check/depth limits. A label-blind semantic audit must still approve the full candidate.

### Visual discovery and model-family review

Use one or at most two explicitly configured visual reviewers per parent batch. A reviewer receives source/edited images, original instruction/rubric, saved program and observations, excluding the reference label, aggregate agreement, gradients and rejection feedback. It proposes at most two instruction-grounded hypotheses: missing evidence, nested evidence, or composition problems. It may find no justified repair and must investigate possible overclaiming and underclaiming rather than seek a negative answer.

Different multimodal families can supply complementary hypotheses. Persist reviewer name/family, requested model identity, durable execution reference, returned identity and usage, raw findings and validation failures. Their outputs are hypotheses, not verified check outcomes; do not splice their answers into inference, turn consensus into an optimization reward, or claim independent correctness evidence from family diversity. The structural proposer receives these hypotheses together with native node-level TextGrad feedback, labels, traces and prior diagnostics. Only subsequent label-blind execution supplies candidate observations.

Reviewers use the primary ledger and case scope, frozen model routes, existing single-attempt transport rules, and search/token ceilings. Their calls cannot consume the reserved final allowance. Provider rejection stops the run without substitution; failed or interrupted slots are retained on resume. The default new runner uses its primary model for discovery; alternative families require explicit configuration.

### Audit-rejected seed diagnosis

The completed chalk follow-up never reached visual backward feedback during search because its seed failed the semantic audit. In the new opt-in path, a structurally executable audit-rejected parent can receive **one diagnostic-only program draw**, cached in a separate namespace. Those actual observations support visual discovery and native backward feedback. Persist schema, transport and dependency failures as failures, never as negative visual evidence.

Diagnostic reports remain separate from screening and confirmation evidence. They cannot enter either frontier, qualify a candidate, or replace an audited incumbent, even when their label matches perfectly. Invalid compilation still produces an unresolved leaf without fabricated observations. Repaired candidates must pass structural validation and their own semantic audit before normal screening and fresh confirmation. Freeze selection before final verification; final outcomes cannot trigger another repair.

The new `nested-evidence-readout-v1` checker contract explicitly permits ancestor evidence context in support calls and keeps the fulfillment readout image-free. Historical `forced-evidence-readout-v1` programs retain their independent-support behavior. Explicit promotion creates a new template/hash and requires a fresh audit; saved artifacts are never silently reinterpreted. The v3 executable container and existing prompt/hierarchy APIs remain compatible.

## Rules for removing and revising decisions

### Typed structural edits and deterministic construction

The `typed-evidence-v1` proposal protocol separates semantic decisions from executable wiring. The model proposes focused questions, criteria, bindings, existing requirement IDs and ancestor evidence context. Code constructs the graph. It does not silently repair archived raw-node proposals or treat structural validity as semantic approval.

Transactions contain a reason and one to four actions: `insert_support`, `replace_support`, `revise_support`, `revise_readout`, and `remove_support`. Insertion names an existing direct `after → before` edge, a unique new check ID, evidence context and explicit readout criteria. The executor inserts the check, reparents its consumer, reconstructs saved chain order and makes the readout consume every support. For the rejected chalk proposals, insertion on `n2 → n3` deterministically produces `n2 → n4 → n3`.

Replacement preserves the support's ID and position; splitting combines replacement and insertion. Removal reconnects the chain, but cannot silently discard surviving support evidence references: the same transaction must explicitly revise those references. Validate the final transaction atomically, preserve the complete immutable instruction/outcome contract, and reject over-cap programs without truncation. Retain two or three supports plus one image-free fulfillment readout. This initial typed mode uses all-state ordered chains; general conditional restructuring and DAG execution remain deferred.

Models do not emit `parent`, `active_on`, `role`, `outcome_id` or `node_order`. Code derives exact source provenance from the identified original requirement, stores the typed request and expanded executable transaction, and records both program hashes. Support polarity and readout interpretation remain explicit model-proposed semantics; no automatic all-pass reducer is introduced. Every candidate still requires a label-blind semantic audit and fresh robustness measurement.

The typed compiler likewise accepts ordered support specifications, earlier-support indices and fulfillment criteria, then assigns IDs `s1…sN` and `fulfillment`, roles, outcome identity, chain routing and dependencies. Invalid specifications remain recorded single-attempt failures. The v3 executable/leaf formats and their frozen checker contracts remain authoritative and unchanged; the new proposal protocol is explicitly selected rather than applied to historical artifacts.

Graph validation raises structured `ValueError`-compatible diagnostics identifying missing parents/dependencies, cycles, non-ancestor or sibling consumption, and depth/check limits. Rejection feedback includes the offending node and dependency. Semantic-audit rejection and checker/transport failures remain separate stages.

The fresh chalk experiment compares criterion-only revisions with nested-required typed repair. The nested arm may explore criterion-only intermediates, but cannot qualify or select them as a successful nested result. It requires an added support with ancestor evidence context, sufficient actual execution, complete qualifying confirmation and fresh final verification. Absence of an eligible audited nested candidate produces explicit structural failure and an unoptimized seed fallback.

The current typed search has a maximum of **fifteen repair rounds**, each with one parent batch and at most two proposals. A candidate that fails its full confirmation becomes the next repair parent; its repeated observations and rejection diagnostics remain available for revising, replacing or investigating the inserted component. A passing component is not assigned an expected failure simply because the aggregate label disagrees. Empty/invalid/duplicate proposals do not end the bounded loop; unchanged candidates are not remeasured to manufacture success.

Stop early only after an audited, structurally eligible program satisfies the complete confirmation policy, or when the independently enforced call/token/provider limit is reached. Otherwise exhaust all fifteen rounds. Record rounds started and completed separately, including partial rounds stopped by budgets. Confirmation remains provisional: selection freezes before independent final verification. The new schedule is versioned in experiment configuration, while historical two-round results and runtime snapshots remain unchanged. Longer search does not silently increase an approved model-call budget.

Removal is appropriate when a rule is redundant, unsupported by the instruction, or replaced by another rule that preserves its necessary semantics. Low confidence or disagreement with the reference alone is insufficient.

Every transaction must preserve coverage of the immutable requirement ledger. Replacements record explicit mappings from old outcomes to their successors. Validate the entire transaction atomically for coverage on every terminal path, dependency references, cycles, bindings, applicability, ordered traversal, branch semantics, and execution limits.

Examples:

- Remove “the closed jacket must have a visible zipper” if the instruction only asks for closure and a zipper is an invented requirement.
- Repair “is the jacket closed?” into a precise closure criterion tied to the same jacket in both images when ambiguity causes variation.
- Do not delete the closure criterion merely because it returns no while the case label is yes.
- Do not change “fully closed” into “somewhat more closed” to obtain a stable yes.

A label-blind semantic audit provides additional evidence of preservation; approval is not a proof. Empty programs and uncovered requirements cannot qualify as successful leaves. Never truncate requirements to satisfy a check cap.

## Hybrid optimizer: textual feedback proposes, Pareto selection explores

This is a proposed hybrid, not a claim that either library already implements this entire workflow. [TextGrad](https://arxiv.org/abs/2406.07496) propagates natural-language feedback to components of a computation. [GEPA](https://arxiv.org/abs/2507.19457) uses reflective proposals and maintains complementary candidates for subsequent search. Here, feedback drives changes to executable tree nodes and structure, while a candidate frontier decides which complete programs to develop next.

### TextGrad-style feedback and structural proposals

Treat editable node criteria, target bindings, branch predicates, and subtree specifications as optimization variables. Keep the original instruction, requirement ledger, scoring reducer, reference label, and frozen experiment policy outside the editable variables.

For each chosen candidate:

1. Execute the applicable tree and collect the aggregate prediction, confidence diagnostics, node observations, and visited paths.
2. Construct an evaluation critique from final-label mismatch, weak component repeatability, unresolved coverage, and unnecessary cost.
3. Propagate that critique backward through the **executed** dependency and control-flow trace. Attribute a downstream problem to a parent binding or gate when the trace supports that hypothesis, instead of changing every child independently.
4. Produce node-addressed textual feedback: affected node/path, supporting trace IDs, suspected failure, proposed semantic change, requirements to preserve, and uncertainty in the diagnosis.
5. Convert the feedback into a bounded set of alternative immutable transactions. Each proposal states the expected benefit and possible tradeoff; it does not receive automatic acceptance from its critic.
6. Validate and audit each full candidate, then measure its performance through forward execution.

The “gradient” is a natural-language diagnosis and suggested change, not a numeric derivative or a guarantee of improvement. Do not claim backpropagation evidence about an unexecuted child. Such a child can still receive static structural critique, explicitly distinguished from observed behavioral feedback. Contradictory feedback is retained rather than silently converted into a confident edit.

Example feedback: “Node 1 alternates between two cars. Nodes 2 and 3 inherit different targets across draws. Bind the target using source-image location and carry that binding into both child checks; preserve both the color and rack-removal requirements.” Possible proposals can repair the binding, add a disambiguation gate, or restructure the subtree. Their tradeoffs must be evaluated.

The proposer can see the case reference and traces. The forward checkers and semantic auditor remain label-blind. Neither a desired answer nor the textual critique may leak into an executable checker prompt as an instruction to produce the target result.

### Candidate objective vector and Pareto frontier

Keep complete executable programs as candidates, each with its own graph hash, parent IDs, edits, feedback, audits, and evaluation record. Do not choose the best-looking answer independently for each node and combine those answers into an unevaluated program.

For this single-case optimizer, use a predeclared multi-objective vector:

| Objective | Direction | Definition |
|---|---|---|
| A: final target agreement | Maximize | Fraction of scheduled program draws matching the reference |
| Q: resolved coverage | Maximize | Fraction of scheduled program draws with a resolved final label |
| S: requirement-level repeat consistency | Maximize | Minimum valid modal-state frequency across the fixed original requirement ledger, counting unknowns/failures as non-agreement |
| K: executed checks | Minimize | Mean number of checks actually executed per scheduled draw |
| T: completion-token cost | Minimize | Mean measured or conservatively reserved completion tokens per scheduled draw |

For S, compile a fixed mapping from requested outcomes back to each original requirement; a split must preserve that mapping and its reducer. Use canonical requirement states so adding easy supporting nodes, splitting a requirement, or changing node count cannot inflate the metric. Where a requirement cannot be assigned a valid state, its unresolved draws remain in the denominator. Conditional node metrics and confidence gates are still reported and checked separately. High S with poor A is stable error, not success.

An eligible candidate P dominates Q when P is no worse on every objective and strictly better on at least one. The frontier contains candidates not dominated by another eligible candidate. For example, a more accurate but more expensive tree and a cheaper, slightly less stable tree can both survive. Semantic validity, complete path coverage, and resource limits are admission gates; a cheap tree that drops a requirement cannot enter the frontier.

Hypothetical candidates evaluated with the same ten-draw schedule illustrate the tradeoff:

| Candidate | A | Q | S | Mean checks K | Mean tokens T | Decision |
|---|---:|---:|---:|---:|---:|---|
| Tree A | 0.9 | 1.0 | 0.9 | 4 | 300 | Keep: stronger quality |
| Tree B | 0.8 | 1.0 | 0.8 | 2 | 150 | Keep: lower cost |
| Tree C | 0.8 | 1.0 | 0.8 | 4 | 300 | Dominated; exclude from active frontier |

A and B can both generate the next textual-gradient proposals. If the target-agreement acceptance threshold is 0.9, B remains exploratory even though it is non-dominated. These numbers are illustrative, not pilot measurements.

This is **GEPA-inspired multi-objective selection**, with an explicit distinction from GEPA's default per-key strategy. The [GEPA selection guide](https://gepa-ai.github.io/gepa/guides/candidate-selection/) describes tracking the best candidates for each key and sampling in proportion to key wins; that can exclude balanced candidates that never win an individual key. This design instead keeps the full non-dominated set before bounded pruning. A future native-library integration would need an appropriate custom selector, not just an assumption that `pareto` implements this exact policy.

A single case supplies little diversity for a per-example frontier based only on its scalar accuracy. Our dimensions describe different properties of that same case's program. Repeat slots are not additional independent cases, and mutable tree nodes are not interchangeable validation instances. Raw self-reported confidence is not a reward axis that candidates can improve simply by asserting greater certainty.

### Comparable evidence and bounded parent selection

Compare candidates only within the same evaluation tier, using the same preset draw count, evidence, model settings, requirement basis, and cost accounting. A one-draw screen cannot dominate a candidate with a full confirmation record. Every candidate uses its own fresh slots; naming corresponding repeat indices does not make provider samples identical.

Maintain a provisional screening frontier and a confirmed frontier separately. Promote shortlisted candidates by running the fixed fresh confirmation schedule. Near-ties can receive a predeclared additional evaluation batch if budget permits; otherwise preserve the uncertainty. Do not selectively rerun a failed candidate until it obtains a favorable frontier position. Observed dominance remains an estimate from small samples.

Bound the stored active frontier. Retain objective extremes, then candidates separated in normalized objective space using a frozen deterministic pruning rule and hash-based tie-breaks. Persist the full archive and pruning reasons; the active set is a bounded subset of the measured frontier. Keep the seed separately even if dominated.

Choose a bounded number of parents each round using a seeded policy that gives every retained frontier member nonzero probability. One possible policy assigns weights for objective-best performance plus a uniform exploration floor. This preserves balanced candidates that a best-per-key-only sampler might never choose. If too few frontier parents exist, a separately bounded pool of audited neutral intermediates may supply structural exploration; pool membership is not evidence of success.

Optionally propose a subtree combination from complementary frontier parents. Treat it as a new immutable transaction: check shared bindings, requirement mappings, branch contracts, and conflicts, then audit and evaluate the whole combined program. Parent scores and observations cannot be inherited as the child's performance. This is local candidate recombination, not cross-case CaliTree parent merging.

## Search, acceptance, and stopping

Retain the seed, the best candidate satisfying the acceptance policy, both evaluation-tier frontiers, and a bounded intermediate pool. Frontier membership is permission to explore a tradeoff, not permission to deploy that candidate or call the leaf robust.

Proposed control flow:

    seed = compile_ordered_program(instruction, rubric)  # reference excluded
    validate_and_audit(seed)
    screen(seed, fresh_slots=True)
    screening_frontier = nondominated(screened_valid_candidates)
    confirmed_frontier = empty

    for round in bounded_search:
        parents = sample_bounded_parents(screening_frontier,
                                         confirmed_frontier, intermediates)
        for parent in parents:
            traces = parent.saved_search_traces
            diagnose_execution_failures_separately(traces)
            if aggregate_matches_reference(traces):
                critique = diagnose_weak_component_robustness(traces)
            else:
                critique = diagnose_outcome_mismatch_and_dependencies(traces)
            feedback = propagate_textual_feedback_along_executed_trace(critique)
            children = propose_bounded_tree_transactions(parent, feedback)
            validate_and_audit_without_reference_labels(children)
            screen_valid_children_with_fresh_slots(children)

        update_screening_frontier_with_comparable_screening_records()
        shortlist_frontier_candidates_under_budget()
        confirm_shortlist_with_fixed_fresh_draw_schedule()
        update_confirmed_frontier_with_comparable_confirmation_records()
        retain_seed_qualified_incumbent_and_bounded_intermediates()
        stop_if_confirmation_policy_passes_or_search_budget_is_exhausted()

    winner = select_qualified_candidate_or_best_explicitly_unsuccessful_fallback()
    freeze(winner)
    final_traces = execute_reserved_fresh_verification_draws(winner)
    return_artifact_and_status_without_using_final_traces_for_more_repairs()

If seed compilation or validation fails, record an unresolved leaf and compilation diagnostics; do not fabricate visual-error feedback.

Only a candidate meeting the preset agreement, coverage, required-node evidence, confidence-if-required, and audit gates can become the qualifying incumbent. A faster candidate that fails those gates may remain exploratory but cannot replace that incumbent. Among qualifying confirmed candidates, use the frozen final selector: higher target agreement, then coverage, then requirement consistency, then fewer executed checks and lower measured cost. If none qualifies, return the best available candidate with an explicit unsuccessful status.

The frontier may therefore preserve temporary quality/cost tradeoffs that greedy selection would discard, while final acceptance continues to prioritize a robust case judgment. All final selection occurs before reserved final verification. The final traces never update the frontier, textual feedback, or candidate choice within this experiment.

A finite budget replaces an unbounded “repair until it passes” loop. Reserve final-verification calls before search. Fresh confirmation and final draws must not reuse cached search observations. Cached replay supports reproducibility but supplies no new statistical evidence. Failed/interrupted durable slots are retained, not repeatedly sampled until successful.

Suggested output statuses are `locally_robust`, `label_matched_but_unstable`, `stable_but_mismatched`, `unresolved`, `reference_conflict_suspected`, and `budget_exhausted`. Save the metrics separately so a single status cannot hide multiple problems. These names are proposed additions, not current runtime guarantees.

`locally_robust` means the frozen leaf passed the declared final policy on the fitted case and its exercised paths, with preserved requirement coverage and an accepted audit. Unvisited branches are explicitly untested. It does not claim generalization or certified atomic correctness. Final verification failures end the current experiment; they do not silently re-enter its search loop.

## Examples

### Correct aggregate, weak component

Instruction: “Make the car red and remove the roof rack.” Reference: `yes`.

Suppose the seed's first aggregate is yes, but five whole-program draws produce:

- Red car: complete, complete, complete, complete, complete.
- Roof rack removed: complete, complete, unknown, complete, absent.

The second outcome's complete frequency is 3/5. Inspect whether the checker mistakes roof rails for the rack, uses the wrong car, or lacks a precise removal criterion. Repair the relevant binding or wording, then repeat the whole program. Both requested outcomes must remain covered.

### Wrong aggregate, unnecessary restriction

Instruction: “Close her jacket fully.” Reference: `yes`.

A decomposition requires both “jacket fully closed” and “zipper visibly fastened.” If the second requirement was invented, removing that restriction can be legitimate. If the actual closure check is failing, investigate its visual evidence and meaning; deleting closure would invalidate the program.

These are hypothetical illustrations, not results from the completed pilot.

## Fit to the repository and verification plan

The existing [casewise optimizer](calitree_program_optimizer.md) already provides immutable programs, requested/support roles, fixed aggregation, structural transactions, label isolation, semantic audits, durable calls, and saved leaf execution. This proposal extends its decision-level diagnostics, ordered conditional execution, candidate selection, and acceptance policy rather than replacing those foundations. The [existing GEPA/TextGrad adapters](calitree_optimizer_comparison.md) remain separate baselines: their current integration does not implement this proposed hybrid or node-wise feedback propagation.

Proposed implementation areas:

- `critical/core/decision/`: define ordered-tree nodes and transitions, branch/path validation, traversal, explicit inference versus skip handling, canonical requirement states, confidence sources, conditional statistics, and topology-aware cache identity.
- `critical/core/optimization/program/`: add the preset robustness policy, two diagnosis branches, node-addressed textual feedback, structural proposers, tier-specific objective records, Pareto dominance/pruning, seeded parent selection, and confirmation gates.
- `CaliTreeBuilder.build_program_leaves(...)`: save the selected ordered decomposition, transitions, branch support status, per-component robustness evidence, frozen thresholds, frontier lineage, and final verification status. Use a new artifact version for conditional execution; do not reinterpret existing saved programs.
- Experiment runners: record seed/selected comparisons, active and archived frontiers, dominance/pruning reasons, parent sampling, node feedback, all edits and rejected proposals, path traces, confidence availability, conditional repeat counts, coverage, and usage.

Tests should distinguish stable-wrong from unstable-correct behavior, preserve required checks during removal, prevent supporting facts from earning edit credit, cover partial labels and dependency errors, isolate labels from checker/audit requests, reject threshold changes on resume, and verify fresh confirmation/final slots. Include a regression where removing the only failing requirement would make the aggregate match, but must be rejected.

Additional tests should cover ordered sibling execution, pass/fail/unknown transitions, reference-label-free routing, skipped versus inferred outcomes, coverage of all terminal paths, unvisited-branch support, minimum activation counts, and subtree cache invalidation. Test dominance direction, equal-objective ties, preservation of balanced non-dominated candidates, bounded pruning, separate screen/confirmation tiers, seed retention, immutable subtree recombination, and rejection of invalid but low-cost trees. Verify that final draws cannot alter the frontier or generate proposals.

A future pilot should compare the seed, the current casewise optimizer, and this hybrid component-focused optimizer under a frozen case set and matched budgets. To isolate contributions, predeclare matched-budget comparisons of flat versus ordered execution and single-incumbent textual repair versus textual repair with a Pareto frontier. Keep the requirement ledger and reducer fixed across arms. Report final label agreement, coverage, requirement and conditional-node consistency, branch activation, executed checks, cost, confidence/error association, and semantic-audit outcomes separately. Repeats do not increase the number of independent cases. Calibrating confidence as correctness would require additional independent labeled examples; it cannot be established by repeatedly fitting the same leaf.

The [DSG fidelity experiment](experiments/calitree_dsg_fidelity.md) motivates explicit outcome aggregation, consistent bindings, and progress-sensitive checks. Its results do not establish that this proposed repair loop will succeed; that remains to be tested.

## Implemented v4 uncertainty handling and adaptive proposals

`decision-leaf-v4` and `typed-evidence-v2` separate three relationships that earlier forced evidence chains conflated: saved ancestor context (`dependencies`), genuinely required known facts (`required_dependencies`), and explicit activation (`activation.check_id` / `activation.states`). Code retains deterministic ordered topology, but scheduling never propagates an independent question's blockage to later questions. Context can be unknown, invalid, or skipped; the checker sees an honest missing-evidence marker rather than an invented negative fact. The fulfillment call always has an explicit scheduling decision and receives no images.

For a jacket, uncertainty about whether closure increased must not prevent direct edited-image closure inspection. A resolved fulfillment result can use a legitimate alternate rule despite optional uncertainty. This does **not** relax robustness: an executed uncertain support still fails known-answer consistency. A subsequent audited repair may reorder endpoint inspection first and conditionally omit progress when the endpoint establishes completion. Skipped questions remain untested, and required unknown evidence remains unresolved.

The immutable instruction, rubric, requirement ledger and requested outcome/bindings remain authoritative. Typed edits add deterministic support reordering and activation configuration to insertion, replacement, revision and safe removal. One to three supports plus fulfillment are allowed; compilation starts with two supports. All edits validate atomically, including surviving references after removal. The auditor must ground rejection in an exact original clause and a concrete unsupported interpretation; its approval remains fallible evidence.

The local greedy search uses at most 15 rounds and two proposed transactions per round under an enforced budget. Both arms retain valid intermediate candidates and comparable screening/confirmation evidence. Unresolved or mismatching candidate screens do not receive five-draw confirmation. The audited seed does receive five fresh confirmation draws. A selected candidate cannot regress agreement or coverage against an equally measured audited seed; a qualifying incumbent cannot be replaced by a failing cheaper candidate.

`luna_then_sol` begins with Luna and permanently changes only the proposer to GPT-6.1 Sol after three consecutive completed rounds without improvement in the frozen screening objective. Empty, duplicate and rejected proposals can contribute to this streak. Transport/invalid-response failures and interrupted rounds do not. Improvement resets the streak. The parent, counter, policy, route and logical slot are persisted before dispatch and validated on replay. Compilation, discovery, native TextGrad backward calls, checking and semantic auditing remain on Luna.

The paired experiment uses the original 12 saved cases with fresh common label-free seeds and independent arm observations. Both arms use the corrected v4 runtime, so the paired comparison measures proposer escalation. The 3,600-call / 4,608,000-completion-token ceiling includes preparation, search and final verification; 960 calls and 983,040 tokens are reserved before search. All 24 selections freeze before any final draw. Existing v2/v3 programs are neither migrated implicitly nor reinterpreted under v4.
