## 260729-16:38:20 — Preregister multi-lane human review
- Type: docs
- Scope: Rubric-Lite selective-policy protocol and CaliTree research report
- What: Froze simple target-blind `no` and `partial` acceptance candidates, cross-dataset development/confirmation gates, input hashes, and a zero-call stopping rule.
- Why: Increase useful automation beyond exact `yes` without adding architecture or tuning a policy to one dataset.
- Details: logs/updates/details/260729-16:38:20-updates.md

## 260729-16:01:41 — Add explicit human-review decisions
- Type: feature
- Scope: CaliTree judge/eval, selective metrics, frontend workbench, workflow example, docs and tests
- What: Added an optional `needs_human` deployment outcome while preserving honest three-class labels, with coverage, error-capture, partial-review, and auto-decision reporting.
- Why: Turn ambiguity into an auditable human-review lane instead of forcing confused cases into `yes`, `no`, or `partial`.
- Details: logs/updates/details/260729-16:01:41-updates.md

## 260729-15:40:21 — Stop the v6 evidence ledger after stage 1
- Type: feature
- Scope: v6 prompt/parser/artifact/workflow, frontend registration, live result, CaliTree report and tests
- What: Added and exercised the one-call evidence-ledger negative control; 80/80 schemas were valid, but accuracy fell to 71.25% and partial F1 to 10.00%, so the preregistered gate stopped all final calls.
- Why: Test whether retaining condition-level achieved/missing evidence improves partial without architectural complexity, and reject it cleanly when the judge still collapses nuanced cases into complete.
- Details: logs/updates/details/260729-15:40:21-updates.md

## 260729-15:31:09 — Diagnose Rubric-Lite score information loss
- Type: docs
- Scope: partial progress gate, cross-dataset score-collision audit, v6 evidence-ledger protocol, CaliTree report
- What: Rejected the two-threshold progress/completion rule and showed that over 94% of partial cases collide with outer classes in the complete three-score representation; preregistered a one-call evidence-ledger prompt.
- Why: Stop trying downstream calibrators that cannot reconstruct discarded evidence and move rubric learning to the representation while preserving the simple architecture.
- Details: logs/updates/details/260729-15:31:09-updates.md

## 260729-15:23:02 — Preregister the progress/completion partial gate
- Type: docs
- Scope: Rubric-Lite partial-boundary experiment protocol
- What: Froze a two-threshold, three-candidate test of partial as visible edit progress without complete fulfillment, with task-grouped cross-dataset advancement gates.
- Why: Test a semantically grounded one-call alternative before inspecting results, without adding another classifier, router, or verifier.
- Details: logs/updates/details/260729-15:23:02-updates.md

## 260729-15:06:41 — Correct task-grouped Rubric-Lite validation
- Type: fix
- Scope: Rubric-Lite grouped cutpoint CV, monotone-feature audit, workflow, frontend, docs and tests
- What: Added non-leaking five-fold task-grouped validation and rejected all 30 monotone scalar alternatives; the minimum-score rule remains the strongest cross-dataset partial classifier.
- Why: Prevent task leakage and empty validation folds, and avoid promoting a dataset-specific result caused by a preliminary allocator defect.
- Details: logs/updates/details/260729-15:06:41-updates.md

## 260729-14:49:06 — Stop stronger-judge A/B after failed partial gate
- Type: docs
- Scope: gpt-4.1 live A/B result, CaliTree metrics report, experiment provenance
- What: Recorded that gpt-4.1 improved ordinary accuracy to 82.50% but reduced balanced accuracy to 59.47% and partial F1 to 30.77%, so confirmation was stopped.
- Why: Enforce the preregistered rule and avoid promoting a larger judge that follows the dominant class rather than improving partial.
- Details: logs/updates/details/260729-14:49:06-updates.md

## 260729-14:43:54 — Preregister stronger-judge Rubric-Lite A/B
- Type: docs
- Scope: EditInspector experiment protocol and CaliTree research notes
- What: Frozen the 80-case gpt-4.1-mini versus gpt-4.1 protocol, dataset and prompt hashes, exact call budget, cutpoint fitting, and advancement thresholds before live execution.
- Why: Test whether better visual signal improves partial without adding architectural complexity or post-hoc model selection.
- Details: logs/updates/details/260729-14:43:54-updates.md

## 260729-14:39:17 — Expose partial-label reliability and reject soft calibration
- Type: feature
- Scope: CaliTree evaluation metrics, workbench reliability table, nested calibration audit, docs and tests
- What: Added per-target rater reliability to every evaluation and documented that nested soft-label models reduce partial F1, leaving the one-rubric/two-cutpoint model as the supported candidate.
- Why: Distinguish judge errors from intrinsic partial-label disagreement without adding another overfit classifier.
- Details: logs/updates/details/260729-14:39:17-updates.md

## 260729-14:20:48 — Audit simple generalization and test core-completion rubric
- Type: feature
- Scope: Rubric-Lite v5 negative control, cross-dataset audit, parser, workflow, docs and tests
- What: Rejected an overfit 89.80% score rule after it collapsed cross-dataset, and stopped v5 after its 80-call test reached only 72.50% accuracy and 10.53% partial F1.
- Why: Identify the simplest calibration that actually transfers and avoid adding complexity based on calibration-half accuracy.
- Details: logs/updates/details/260729-14:20:48-updates.md

## 260729-13:58:08 — Add two-cutpoint Rubric-Lite domain adaptation
- Type: feature
- Scope: two-cutpoint calibration, EditInspector final split, workflow backend/frontend, frozen artifact, docs and tests
- What: Replaced tree adaptation with one rubric score plus two fitted cutpoints; five-fold out-of-fold accuracy is 81.12% and partial F1 is 35.44% on 392 calibration cases.
- Why: Improve external partial calibration with a minimal interpretable model while preserving a genuinely untouched 391-case final evaluation.
- Details: logs/updates/details/260729-13:58:08-updates.md

## 260729-13:33:53 — Add external Rubric-Lite validation and selective deployment
- Type: feature
- Scope: EditInspector data source, frozen simple model, selective confidence, workflow UI, live validation, docs and tests
- What: Added a pinned external benchmark pipeline and confirmed 97.62% accuracy at 53.85% coverage on 312 untouched cases; full-coverage and partial-class failures remain explicit.
- Why: Test whether the simple image-judge calibration transfers beyond ImagenHub and replace broad generalization claims with a reproducible, narrowly supported result.
- Details: logs/updates/details/260729-13:33:53-updates.md

## 260729-12:37:30 — Promote simple Rubric-Lite partial-progress verification
- Type: feature
- Scope: partial-specific rubric, global fusion policy, workflow defaults, live confirmation, docs and tests
- What: Replaced broad partial overrides with a learned yes-only partial-progress verifier; confirmed 82.33% accuracy and 31.01% partial F1 on 600 cases using 51 conditional calls.
- Why: Retain full Cali-Tree-level accuracy with a general, auditable architecture and improve the partial boundary without tree routing or dataset-specific features.
- Details: logs/updates/details/260729-12:37:30-updates.md

## 260729-12:01:39 — Add ordinal Rubric-Lite and boundary verification
- Type: feature
- Scope: Rubric-Lite v3/v4, ordinal calibration, partial-boundary verifier, workflow UI, tests
- What: Added a general three-score ordinal rubric with train-fitted global cutpoints and a score-gated second-pass verifier for ambiguous partial cases.
- Why: Preserve the simple one-rubric architecture while improving class balance and enabling targeted partial-class recovery without task/editor features.
- Details: logs/updates/details/260729-12:01:39-updates.md

## 260729-10:37:37 — Add and validate Rubric-Lite calibration
- Type: feature
- Scope: global rubric learning, workflow backend/frontend, live validation, tests and docs
- What: Added a one-prompt Cali-Tree alternative and evaluated two frozen rubric forms on the 10% held-out development slice.
- Why: Determine whether a simpler, more general calibration method can retain accuracy while improving the partial class.
- Details: logs/updates/details/260729-10:37:37-updates.md

## 260728-16:23:59 — Document Cali-Tree v1–v4 metric comparison
- Type: docs
- Scope: Cali-Tree prompt versions, archived experiments, full held-out report
- What: Added v1–v4 design differences plus accuracy, balanced/class/editor metrics, confusion matrices, merge behavior, usage, and the full v2 report.
- Why: Make version tradeoffs and experiment comparability explicit instead of citing only the selected v2 result.
- Details: logs/updates/details/260728-16:23:59-updates.md

## 260728-15:13:57 — Add reliability-calibrated Cali-Tree and confirm publishable accuracy
- Type: feature
- Scope: task-grouped sampling, semantic Cali-Tree, agreement filtering, selective calibration, workbench, live validation
- What: Added a training-fitted selective policy and confirmed 93.33% on an untouched 600-case half and 92.87% across all 1,200 held-out cases at 64.25% coverage.
- Why: Reach a leakage-safe publishable calibration result while reporting full-coverage limits and human-label disagreement transparently.
- Details: logs/updates/details/260728-15:13:57-updates.md

## 260728-02:14:49 — Add consensus calibration and complete 10% validation
- Type: feature
- Scope: Cali-Tree consensus/pruning, agreement metrics, 10% live validation, tests and docs
- What: Added deterministic three-judge consensus and training-only editor priors; reached 88.33% held-out accuracy and 94.79% on unanimous labels on a 10% development sample.
- Why: Improve general calibration, bound redundant merge work, and quantify performance under human-label disagreement.
- Details: logs/updates/details/260728-02:14:49-updates.md

## 260728-00:37:47 — Guard Cali-Tree optimization and validate larger samples
- Type: feature
- Scope: Cali-Tree optimization/routing, stratified sampling, workbench metrics, E2E portability, live validation
- What: Added leakage-safe warm-start/merge/routing guards and prediction reuse; improved train/test accuracy on 1% and 5% billable ImagenHub runs.
- Why: Improve general prompt calibration while rejecting specializations that fail internal balanced validation.
- Details: logs/updates/details/260728-00:37:47-updates.md

## 260727-23:11:56 — Add Cali-Tree PyCharm compound launcher
- Type: chore
- Scope: local PyCharm project and run configurations
- What: Added dedicated backend, frontend, and compound launchers with Cali-Tree dataset/credential paths and non-conflicting ports.
- Why: Run the complete Cali-Tree workbench directly from PyCharm like the existing prompt-calibration worktree.
- Details: logs/updates/details/260727-23:11:56-updates.md

## 260727-15:26:37 — Reconcile public ImagenMuseum data and validate Cali-Tree live
- Type: fix
- Scope: public ImagenHub setup/defaults, prompt templates, live experiment artifacts, tests and docs
- What: Aligned setup with the eight editor outputs actually published, fixed JSON prompt interpolation, downloaded and hash-verified 1,432 cases, and completed a billable 1% end-to-end run.
- Why: Make the public dataset reproducible as it exists today and verify Cali-Tree against real image, optimizer, and embedding calls.
- Details: logs/updates/details/260727-15:26:37-updates.md

## 260727-14:39:41 — Add workflow-native Cali-Tree image calibration
- Type: feature
- Scope: ImagenHub data, image judging, hierarchical prompt calibration, interface workbench, tests and docs
- What: Added a resumable nine-editor image dataset, official-TextGrad Cali-Tree train/route/eval nodes, rich hierarchy diagnostics, and an explicit-model example workflow.
- Why: Reproduce the paper's image-judge calibration workflow inside VEJudge without changing the existing video annotation path or allowing silent live-model selection.
- Details: logs/updates/details/260727-14:39:41-updates.md

## 260724-16:33:20 — Add recursive workflow folders
- Type: feature
- Scope: workflow storage/API, interface folder tree, compatibility and browser tests
- What: Recursively exposes nested workflow JSON as a collapsible folder tree and supports safe `folder/name` save, load, run lookup, and delete operations.
- Why: Make bundled examples and organized experiment workflows visible without flattening the repository structure.
- Details: logs/updates/details/260724-16:33:20-updates.md

## 260724-11:20:28 — Add edit-aware evidence judging and calibration
- Type: feature
- Scope: evidence storage, video decomposition, area judging, calibration, workflow interface, tests and docs
- What: Added an additive four-area evidence pipeline with content-addressed storage, scoped judging, severe-aware aggregation, optional unit feedback, held-out calibration, uncertainty, active labeling, and a complete mocked interface workflow.
- Why: Calibrate video-editing scores from localized, traceable evidence while preserving the existing whole-video baseline and preventing held-out leakage.
- Details: logs/updates/details/260724-11:20:28-updates.md

## 260723-12:09:15 — Stream adversarial debates live and preserve completed content
- Type: feature
- Scope: debate progress events, run websocket/store, adversarial secondary tab, tests and interface docs
- What: Streams each completed proxy/judge turn into a cumulative live chat and keeps completed calibration content visible while downstream nodes execute.
- Why: Let users watch agents negotiate in action without the secondary tab going blank between node and workflow completion.
- Details: logs/updates/details/260723-12:09:15-updates.md

## 260722-14:36:42 — Compress mentor update into five slides
- Type: docs
- Scope: mentor-facing weekly project update
- What: Reorganized the detailed weekly report into five presentation-length slides covering the project overview, framework, algorithms, pipeline/interface, and results/next steps.
- Why: Make the draft concise enough for a short mentor presentation while preserving the main evidence and limitations.
- Details: logs/updates/details/260722-14:36:42-updates.md

## 260722-14:30:04 — Draft weekly mentor project update
- Type: docs
- Scope: mentor-facing project status and experiment summary
- What: Added a slide-ready July 15–22 summary covering system architecture, calibration/evaluation fixes, experiments, interface improvements, limitations, and next steps.
- Why: Provide a concise but complete draft for reporting the week's progress to project mentors.
- Details: logs/updates/details/260722-14:30:04-updates.md

## 260722-14:24:24 — Align calibration metrics and contain tree labels
- Type: fix
- Scope: semantic/rule calibration secondary tabs, decision-tree SVG, frontend tests
- What: Aligned training and held-out MAE headers with their numeric columns and compacted long semantic feature keys inside decision-tree split boxes while preserving full hover details.
- Why: Make calibration results easier to scan and prevent semantic split titles from overflowing their node borders.
- Details: logs/updates/details/260722-14:24:24-updates.md

## 260722-14:16:11 — Add topological auto-layout for workflow nodes
- Type: feature
- Scope: graph layout/store, canvas viewport, top-bar action, groups and frontend tests
- What: Added a one-click Layout action that arranges nodes by topological depth, separates parallel branches, preserves group membership, and refits the canvas.
- Why: Make large workflows readable without manually dragging apart nodes that are squeezed together.
- Details: logs/updates/details/260722-14:16:11-updates.md

## 260722-14:07:00 — Add exploratory deeper semantic-tree selection
- Type: feature
- Scope: semantic capacity selection, node parameter/UI, offline rerender, tests and derived run
- What: Added an opt-in strategy that selects the richest semantic tree inside the training-CV tolerance and registered a five-node, zero-score-split deep rerender.
- Why: Let users inspect deeper semantic distinctions without changing the safer default or permitting score shortcuts.
- Details: logs/updates/details/260722-14:07:00-updates.md

## 260722-13:50:14 — Register offline semantic rerenders as interface runs
- Type: fix
- Scope: offline semantic rerender utility and interface-run persistence
- What: Added a no-call registration mode and created a discoverable derived run for the latest semantic-first tree and Rule Comparison outputs.
- Why: Supplemental JSON inside an old run directory cannot appear in the VEJudge Runs column.
- Details: logs/updates/details/260722-13:50:14-updates.md

## 260722-13:44:00 — Make semantic evidence define tree decisions
- Type: fix
- Scope: semantic model tree, training-only selection, calibration diagnostics/UI, offline rerender and tests
- What: Confined score features to leaf calibration, made learned branches semantic-only under fixed prompt routing, and selected three M3/M5/M6 semantic decisions with zero score splits.
- Why: Prevent raw-score shortcuts from displacing the ontology-backed meaning the semantic tree is intended to express.
- Details: logs/updates/details/260722-13:44:00-updates.md

## 260722-13:00:30 — Add joint prompt and temperature calibration
- Type: feature
- Scope: judge/debate provenance, joint semantic features and trees, critic reliability, evaluation UI, workflow and tests
- What: Added M3/M5/M6 and temperature-aware calibration with training-only meaningful-tree selection; the live frozen run improved held-out MAE by 0.22 while honestly rejecting unsupported debate-rule splits.
- Why: Improve calibration and tree depth without confusing prompt effects, temperature instability, or overfit semantic rules with generalization.
- Details: logs/updates/details/260722-13:00:30-updates.md

## 260721-23:55:28 — Add guarded graded semantic-tree calibration
- Type: fix
- Scope: graded critic extraction, semantic MAE tree, training-only capacity selection, calibration reports/UI, workflow, tests and research notes
- What: Added target-blind graded rubric evidence and deeper semantic-tree capacity, then guarded deployment with training-only grouped selection; the live frozen rerender improved semantic MAE by >0.05 in sample and held out while rejecting an overfit all-rule model.
- Why: Increase semantic calibration capacity without using validation labels or mistaking tree complexity for generalization.
- Details: logs/updates/details/260721-23:55:28-updates.md

## 260721-22:22:11 — Establish meaningful held-out calibration gain
- Type: fix
- Scope: negotiation stability, video-grounded critic, calibration comparators, resume identity, workflow, evaluation UI and tests
- What: Stabilized cyclic debates, preserved richer semantic rules, separated score-only calibration from rule increments, and verified a 0.062 held-out MAE gain over global bias with a positive bootstrap interval.
- Why: Obtain a statistically defensible calibration improvement while avoiding unsupported claims that semantic rules caused the gain.
- Details: logs/updates/details/260721-22:22:11-updates.md

## 260721-15:57:14 — Stabilize semantic calibration and held-out evaluation
- Type: fix
- Scope: weighted calibrators, adversarial negotiation, rule/semantic tree evaluation, calibration UI and tests
- What: Added equal-video raw-rating weights, fixed disagreement profiles and cycle stopping, leakage-safe frozen rule banks, deployment-only features, diagnostics, and uncertainty-aware verdicts.
- Why: Fix unstable polarized debates, repeated-rating pseudoreplication, label leakage, constant features/scores, and negligible gains being reported as meaningful.
- Details: logs/updates/details/260721-15:57:14-updates.md

## 260721-15:30:41 — Restore credential parser fixture
- Type: fix
- Scope: credential parser test fixture
- What: Restored the non-secret `.env-raw` sample expected by the credential parser tests.
- Why: Allow the complete backend suite to run without three missing-file failures.
- Details: logs/updates/details/260721-15:30:41-updates.md

## 260721-14:10:58 — Immediate hard stop for interface runs
- Type: feature
- Scope: interface run worker lifecycle, Stop/Resume API and UI, persistence, tests and documentation
- What: Runs now execute in killable spawned process groups; Stop terminates local in-flight work immediately, publishes terminal stopped state, preserves completed checkpoints, and resumes only missing work.
- Why: Eliminate the previous wait for a blocked node/model call to return after the user clicks Stop.
- Details: logs/updates/details/260721-14:10:58-updates.md

## 260721-13:34:24 — Toggleable semantic prompt distillation
- Type: feature
- Scope: debate prompts and semantic summarization, adversarial calibration execution/checkpoints, node UI, tests and documentation
- What: Added rule-based and dedicated-engine LLM distillation modes with shared structured semantics, strict leakage filtering, visible fallback, bounded rendering, separate summary caching, and compatible optimized-prompt output.
- Why: Preserve the reusable meaning and observable evidence from negotiation without forcing extra model calls in offline or legacy workflows.
- Details: logs/updates/details/260721-13:34:24-updates.md

## 260721-11:09:12 — Raw per-rater targets in calibration pipelines
- Type: fix
- Scope: calibration debate/fitters, human-proxy prompt, calibration secondary tabs, interface docs, tests
- What: Calibration now accepts Dataset `aggregation_method=none`, preserves raw ratings in grounded debates, and fits one observation per rating with item-grouped leave-one-out validation.
- Why: Let calibration use individual human scores without forcing an aggregate or leaking sibling ratings across validation folds.
- Details: logs/updates/details/260721-11:09:12-updates.md

## 260720-13:52:15 — Dataset node aggregation_method dropdown (mean/median/max/min/none)
- Type: feature
- Scope: dl_human_annotations/aggregate, node_db/dataset_node, node_eval/eval_node, node_calibration/{_templates,cl_adversarial,cl_rule_tree,cl_semantic_tree}, web/{paramSchemas,socketTypes,JudgeSamplePreview}, tests (pytest+vitest+e2e), interface.md
- What: Dropdown on the Dataset node to combine multi-annotator human scores: mean (default)/median/max/min, or none = no aggregation (scores null, per-rater values kept in raw_scores). Eval scores the judge against each rater under none; calibration nodes reject none with a clear message. Frontend shows a per-rater breakdown.
- Why: Let the user pick the aggregation and inspect/evaluate against individual annotator scores.
- Details: logs/updates/details/260720-13:52:15-updates.md

## 260720-12:12:11 — API-driven I/O schema header with expandable examples on the generic tabs
- Type: feature
- Scope: web/ (api/nodes, nodes/useNodeSchema, nodes/socketTypes, RightPanel/secondary/{SocketSchema,NodeInputsTab,NodeOutputsTab,NodeIOTabs.test}, App.css, e2e specs), CLAUDE.md, interface.md
- What: The generic Inputs/Outputs secondary tabs now open with a schema header (every socket as name:type + color swatch + fan-in tag + an expandable per-type example JSON payload). Sourced from the live node-type API (GET /api/nodes), so it covers every current/future node and auto-reflects backend socket changes with no frontend edit. Examples/colors are static per-socket-type enrichments (SOCKET_EXAMPLES/SOCKET_COLORS) with graceful fallback.
- Why: Give an at-a-glance, self-documenting I/O contract per node that stays in sync with the backend; the succinct name:type alone didn't show subfield structure.
- Details: logs/updates/details/260720-12:12:11-updates.md

## 260720-11:06:00 — Palette drag-and-drop + load a past run (inspect + resume)
- Type: feature
- Scope: web/ (NodesTab, GraphCanvas, RunsTab, LeftPanel, api/runs, store/{tabs,run}, App.css), vejudge/interface/server (run_manager, run_registry, routes/runs, schemas), tests (unit + vitest + e2e), interface.md
- What: Drag nodes from the palette onto the canvas at the cursor; a new Runs tab lists past runs under logs/exps and can Open one (graph + statuses + outputs reconstructed from disk) or Resume a stopped one from checkpoint. Terminal runs now persist a faithful run_results.json; GET /api/runs/{id} falls back to disk.
- Why: Let users place nodes where they want and revisit/continue previous runs after a server restart.
- Details: logs/updates/details/260720-11:06:00-updates.md
