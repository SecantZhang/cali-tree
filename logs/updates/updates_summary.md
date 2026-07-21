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
