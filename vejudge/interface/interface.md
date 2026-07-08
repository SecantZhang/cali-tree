# Judge Interface

Interface system so that users can directly use the interface to construct, run and monitor the judge system.

> **Status:** design spec for a future ComfyUI-style interface. `vejudge/interface/` is currently a
> placeholder (out of scope for v1 — see `docs/architecture.md`). The CLI (`vejudge-bench`,
> `vejudge-robust`, `run/*.sh`) is the supported entry point today; this document defines the
> node/workflow model the interface should implement on top of the same underlying modules, so
> the interface is a visual front-end for the CLI, not a divergent second pipeline. Every
> workflow described below must be expressible as (and exportable to) the equivalent `run/*.sh`
> invocation.

## Interface description

The interface should be based on the idea of comfyui with each components being the nodes, parameters as the configuration for the node. We can connect the components to assemble a workflow. There are open/hidable left panel that contains the directory for the node/workflows/dataset.

**Layout:**
- **Left panel** (hidable) — three tabs: *Nodes* (palette, grouped by category, drag onto canvas), *Workflows* (saved graphs as JSON, one file per workflow), *Datasets* (browsable pointers into `data/` and `evaluation/` per `docs/data.md`, independent of any one graph).
- **Canvas (center)** — the node graph. Connections are typed sockets; a socket only connects to a compatible type (see Node anatomy below). Invalid connections are rejected inline, not at run time.
- **Right panel** — inspector for the selected node: its parameters, current status, and a "view secondary tab" button.
- **Bottom panel** — console/log, mirroring the run's `run.log` (and, when a node is selected, that node's slice of `llm-histories.log`) in real time.
- **Top bar** — Run / Stop for the whole graph or a selected subgraph, a dry-run toggle, run history (links to `logs/exps/<ts>-exps/`), and an **API Credentials** button (see below) with a status dot showing whether a Judge Node currently has anything to authenticate with.

**Run controls** (bridges the interface to `CLAUDE.md` § Running the Benchmark, so the UI never
bypasses the CLI's safety rails):
- **Dry-run toggle** (default **on**) — matches `--dry-run`; no billable calls are made. Turning it
  off requires an explicit confirmation dialog (equivalent to `--live` / `VEJUDGE_ALLOW_LIVE=1`),
  since Judge/LM Engine nodes make real, billable gateway calls.
- **Cost estimate preview** — before a non-dry run starts, show matched item count and estimated
  call count per Judge node (mirrors `run/estimate_cost.sh`).
- **Checkpoint/resume indicator** — each Dataset/Judge node shows a small badge for
  cached-and-skipped vs. to-run items, backed by the same `CheckpointStore`
  (`judge_results.jsonl`) the CLI's `--continue` uses. Re-running a graph never redoes a
  completed `(item, judge)` pair.
- **Endpoint health** — an LM Engine node shows which gateway endpoint (primary/mirror) it
  resolved to, per `PlutoCreds.preferred`.
- **Progress bars** — three, at different granularity, all driven by the same live status/
  progress stream (per-node status + optional `{completed, total}` events over the run's
  websocket):
  1. **Per-node bar**, on the node itself (see Node anatomy's Status indicator below) —
     visible only while that node is `running`.
  2. **Overall workflow bar**, directly under the top bar's title row — `nodes completed /
     total nodes` in the current graph. Always determinate (the node count is known the
     moment a run starts) and visible only while the run is `running`.
  3. **Current-node bar**, directly below the overall bar — the same data driving (1) for
     whichever node is currently executing, labeled with that node's type + id, so the
     detail is visible without the node itself in view.

  Not every node type reports the same granularity: a node that runs as one atomic step
  (e.g. Dataset, Eval) has no sub-progress signal, so its bars render as an **indeterminate**
  animated bar rather than a fabricated percentage. A node that iterates a unit of work per
  call (Judge, one call per selected `(item, metric)` pair) reports a real `{completed,
  total}` and renders a **determinate** fill. This is a deliberate distinction, not an
  inconsistency — an honest "busy" indicator beats a precise-looking number with nothing
  backing it.

**API Credentials modal** — opened from the top bar's API Credentials button. Lets you enter
an LM-gateway token and base URL (plus an optional mirror URL, tucked behind an "Advanced"
disclosure) directly on the page instead of setting env vars or hand-editing `.env-raw` — the
exact gap that made a real `.env-raw`-path misconfiguration hard to diagnose from the browser
alone. Saved to a local gitignored file (`vejudge.lm_engine.creds.save_manual_creds`, default
path `.interface_credentials.json`) that the backend reads on every subsequent Judge Node
call, so it survives backend restarts. Resolution order is **manual override > env vars >
`.env-raw`** — explicit UI input wins over ambient config. The modal shows which source is
currently active and its base URL (never the token, which is never echoed back by the API);
"Clear" removes the manual override and reverts to whatever's next in that order.

**0-items warning** — a Dataset Node whose loader/filters matched nothing, or a live (non-dry-run)
Eval Node whose Judge and human-label item ids never overlapped, still reports `status: "done"`
(matching nothing isn't necessarily wrong) but adds a `meta.warning` string — surfaced as a log
line in the bottom console and as a highlighted line in that node's secondary tab, so a run that
silently did nothing doesn't look identical to one that actually worked.

### Interface themes

The themes can be choosen and modified, default to the light color style. Theme includes a dark variant and a user-defined custom theme (palette + node-category colors); the active theme is a persisted user preference, not per-workflow.

Theming covers the **whole** surface, not just the app's own panels: native form controls
(dropdowns, text inputs, buttons — these default to the browser's light UI chrome regardless of
the page's own palette unless explicitly styled and paired with a matching `color-scheme`
declaration) and the canvas library's own chrome (zoom controls, minimap) must switch with the
active theme, not remain stuck in their light defaults.

## Nodes

Each node represents a unit in the system, it could be represent the LM engine, data, optimization, pre/post processing, databases, agents etc.
Each node interface has its own secondary tab by double-clicking on it. The node-specific secondary tab is a more specific designed visualization of how things are working inside the node.

### Node anatomy

Every node shares the same chrome, regardless of category:
- **Header** — node name + a category color swatch (see below).
- **Input sockets** (left edge) — typed: `dataset` (stream of `JudgeSample`-shaped items), `engine`
  (an LM engine handle), `judge_result`, `labels` (human annotations), `model_artifact`
  (a calibration/ensemble fit). A socket only accepts its matching type.
  Dataset-shaped types
  (`JudgeSample`, `judge_result`, calibrated/aggregated results) all carry an `item_id` so nodes
  downstream can always re-join to earlier stages (e.g. an Eval node joining calibrated scores
  back to `labels`).
- **Output sockets** (right edge) — same type system. Both input and output sockets sit
  slightly outside the node's border (not flush with it) so a connection point reads as its
  own element rather than overlapping the header text or body content.
- **Inline parameter widgets** — the node's configuration, editable directly on the canvas
  (numbers, dropdowns, toggles) using the exact same widgets and store as the right panel's
  Inspector — editing a param on the canvas and editing it in the Inspector are the same
  action, not two parallel copies. A header chevron collapses the widget list down to a
  single one-line summary for a compact view; sockets stay visible either way.
- **Status indicator** — idle / queued / running / done / error, shown as a small dot in the
  header. While `running`, the node additionally gets a **highlighted border** (a distinct
  green, separate from the "done" status color, so "currently executing" is never confused
  with "finished") and a thin **progress bar** directly under the header — see the Run
  controls section above for the determinate/indeterminate distinction.
- **Double-click → secondary tab** — see each node's "Secondary tab" entry below.

**Node categories** (matching the `interface/` package layout in `docs/architecture.md`):

| Category | Package | Color |
|---|---|---|
| Database | `node_db` | blue |
| Preprocessing | `node_preprocessing` | green |
| Judge / core | `node_vejudge` | purple |
| Postprocessing | `node_postprocessing` | orange |
| Eval | `node_eval` | red |

### Nodes list

#### Peanut Source Node

*Category: `node_db`*

Description: wraps `dl_peanut_eval`'s `DataLoader` (`vejudge/database/dl_template/base.py`) —
loading only, no sampling/filtering. Loads every item's full `JudgeSample` up front so the same
source can feed multiple differently-sampled Dataset nodes without re-loading. Other model
outputs (`coconut`, `grapenut`, `loopedit` — see `docs/data.md`) would each get their own Data
Source node type alongside this one if/when they get real loaders; there's deliberately no
generic "pick a loader" dropdown, so each source node's identity is unambiguous on the canvas.

Input: None.

Output: `raw_dataset` — a stream of `JudgeSample`-shaped items:
`{item_id, project, prompt_idx, model, use_case, input: {user_prompt, a_roll_transcript_text, b_roll_captions_excerpt, initial_timeline_text, notes_path, asset_filepaths, ...}, algorithm, output: {output_video_path, assembly_json}}`.
`raw_dataset` is a distinct socket type from `dataset` (below) specifically so a source's raw
output can never be wired directly into a Judge node — sampling is always an explicit step.

Node parameters:
* **Model**: which rendered-output model directory to read (default `peanut`).
* **Projects**: multi-select project filter, default all.

Secondary tab: a summary header (loader, model, project filter, and — once this node has
actually run — the last run's item count and skipped-item count) above a table/grid browser of
the loader's items. Selecting an item shows a structured preview rather than a flat JSON dump:
the prompt/use_case pulled to the top, a real `<video controls>` player for
`output_video_path` (streamed through the path-confined `GET /api/media` route — see
`vejudge/interface/server/routes/media.py`), with the large embedded blobs (B-roll
captions, A-roll transcript, assembly JSON) each in their own collapsible section — a raw-JSON
fallback is still one click away. Shows a live (indeterminate) progress line while the node is
`running`. A frame-thumbnail-only fallback (for items whose video hasn't rendered) isn't
implemented — the video element is simply omitted when `output_video_path` is empty.

#### Dataset Node

*Category: `node_db`*

Description: samples/filters an already-loaded `raw_dataset` stream — the second half of the
old combined Dataset Node, split out specifically so a Peanut Source's raw output can be
sampled multiple different ways (e.g. compare `full` vs `stratified` in one graph) without
re-loading, and so sampling is always an explicit, visible step rather than bundled into
loading. It also looks up matching human-annotation labels (`dl_human_annotations`'s
loader/aggregator) **by item id, for exactly the items it just sampled** — an earlier design
gave human annotations their own standalone node with its own independent sampling
ratio/mode, which could silently select a different item set than whatever the Peanut side
sampled (human annotation item ids use the identical `project::prompt_idx::model` format, so
the two sides only lined up by coincidence, not by construction); joining by id off this
node's own sampled set closes that gap.

Input: `raw_dataset` (a Data Source node's output, e.g. Peanut Source Node).

Outputs: `dataset` — the sampled subset of the input, same item shape. `labels` — the
aggregated human-annotation record for each sampled item that has one (items with no
annotation yet are simply absent, not an error).

Node parameters:
* **Sampling ratio**: percentage, default to 100%.
* **Sampling mode**: stratified, or unified (uniform, the default). No separate "full"
  mode — a ratio of 100% under either mode already selects every item, so a mode that
  ignored ratio entirely was redundant and a footgun (silently no-oping ratio for anyone
  who changed it without also changing the mode off its old "full" default).
* **Category filter**: `use_case ∈ {visual montage, speech-driven, voiceover-heavy}`, multi-select, default all.
* **Item id filter**: optional glob/regex over `item_id` (e.g. limit to one project), for the quick-subset style of iteration (`run/run_quick_subset.sh`).

Secondary tab: sampling config (mode/ratio/filters) plus — once run — the resulting selection
count against the raw input's total count, and how many of those got a matching human label.
No item browser of its own (it has no loader to browse against); double-click the upstream
source node for that.

#### Preprocessing Node

*Category: `node_preprocessing`*

Description: derives cached artifacts from a dataset stream's source/output media — sampled frames, keyframes, short clips, ASR transcript, OCR text, captions, shot boundaries, audio event labels, blur/flicker metrics (`vejudge/preprocessing/pp_template/base.py`). Implements the input-strategy variants from `docs/research.md` § Judge Input Strategies (A–E) as one composable node rather than five separate ones.

Input: `dataset` (Dataset node output).

Output: `dataset` — the same items, enriched with artifact references. Artifacts are cached by `(item_id, preprocessing_config_hash)`; a node run never re-extracts frames/transcripts that already exist on disk for the current parameter hash.

Node parameters:
* **Artifact types** (multi-select): sampled frames, keyframes, short clips, ASR transcript, OCR text, captions, shot boundaries, audio event labels, blur/flicker metrics.
* **Input strategy**: A (direct video) / B (uniform frame sampling) / C (keyframe/shot sampling) / D (segment-level) / E (multimodal summary) — sets sensible defaults for the artifact-type multi-select above; still individually overridable.
* **Sampling rate / clip length**: numeric, only shown when the relevant artifact type is selected.
* **Cache policy**: reuse-if-present (default) / force recompute.

Secondary tab: per-item artifact viewer — a frame filmstrip, the ASR transcript with timestamps, detected shot boundaries overlaid on a scrub bar, and cache hit/miss counters for the current run.

#### LM Engine Node

*Category: `node_vejudge`*

Description: a reusable, swappable engine config — a Judge node no longer embeds its own
model/temperature/concurrency; it takes a required `engine_config` input from an LM Engine
Node instead, so the same graph can be re-pointed at a different model/version without
touching the Judge nodes, and one config can feed multiple Judge nodes at once. The output
is a **plain JSON-safe dict**, not a live `lm_engine.LMEngine` instance — an `LMEngine`
holds an open `LLMHistoryWriter` file handle and lazily-loaded credentials, neither of
which would survive the run-status HTTP route's per-poll JSON serialization or the
websocket's `partial_result` event, both hard JSON-encode boundaries every node output
already passes through. Judge nodes call `get_engine(**config)` themselves from this
dict's fields, exactly as they already did with their own inline params before this split
— only the source of those kwargs moved upstream.

Input: None (configuration-only node).

Output: `engine_config` — `{engine_kind, model, temperature, max_tokens, concurrency}`,
consumed by one or more Judge nodes.

Node parameters:
* **Engine kind**: gemini / gpt / qwen.
* **Model** (defaults to `config.DEFAULT_TEXT_MODEL`, shown directly rather than a blank
  field, since that's the actual value `LMEngine` falls back to when unset).
* **Temperature** (defaults to `0.3`), **max tokens** (defaults to `4096`).
* **Concurrency** (defaults to `1`; moved here from the Judge nodes' old
  `text_concurrency`/`video_concurrency` params, per this node's original spec).
* **Health-check toggle**: present but inert — `vejudge/lm_engine/health.py` exists at the
  engine layer but isn't wired into the interface's Judge nodes at all yet, matching the
  Preprocessing Node's existing precedent of shipping a param before its behavior lands.

Secondary tab: not implemented yet — a live tail of this engine's slice of
`llm-histories.log` (prompt hash, token counts, latency, retry/failover timeline) is the
eventual plan, but no route currently serves that log to the frontend. Today the tab just
points back at the params panel, which already shows everything this node carries.

#### Text Judge Node / Video Judge Node

*Category: `node_vejudge`*

Description: runs the M1–M6 judges (`vejudge/core/judge/base_judge.py`'s `Judge` class
parametrized by `metric_id`) over an incoming dataset stream, split into two node types along
the modality boundary that already existed internally (separate text/video engine configs,
separate concurrency knobs) — **Text Judge Node** covers M1/M3 (text modality), **Video Judge
Node** covers M2/M4/M5/M6 (video modality). Each builds the versioned prompt
(`vejudge/core/prompts/m{n}_*.py`) for each item, calls its own attached engine, parses the JSON
response, and validates it (score range 1–5, required fields, non-empty rationale — invalid
output is flagged, never silently defaulted). Both share one concurrent-execution helper
(`node_vejudge/_concurrent_judging.py`) rather than duplicating the (item, metric) thread-pool
loop, checkpointing, and streaming-batch-eval logic.

Splitting by modality (not per-metric — M1–M6 would need six nodes) keeps each node's engine
config unambiguous (one engine per node, not two conditionally-used ones) while avoiding the
much higher structural cost a full per-metric split would add (a six-way merge before Eval, and
six single-purpose nodes to wire for what's usually one judging step). The trade-off: today's
graph executor runs nodes strictly sequentially, so text and video judging — which used to
overlap within one node's two internal thread pools — now run one after the other unless a
future executor change adds concurrent sibling-node execution.

Input: `dataset` (post-Preprocessing, or directly from a Dataset node) and a required
`engine_config` (an LM Engine Node's output — see that entry above for why this moved out
of each Judge node's own params).

Output: `judge_result` — per item, per selected metric: `{judge, metric_id, prompt_version, prompt_system, prompt_user, parsed, raw_content, validation_flags, valid, promptTokens, completionTokens, totalTokens, model}`.
`prompt_system`/`prompt_user` are the exact text sent to the LM for that item/metric (not
just the parsed response) — shown in the secondary tab below.
A Text Judge Node's and a Video Judge Node's outputs are meant to both feed the same Eval Node
(on its separate `judge_result_text`/`judge_result_video` inputs), which merges them per item —
either one alone is also a fully supported shape (a text-only or video-only graph).

Node parameters (Text Judge Node): **Metrics** (multi-select, M1/M3 only, default all text
metrics), **batch size** (streaming batch-eval — see the Eval Node entry). Engine
kind/model/temperature/concurrency all come from the required `engine_config` input instead
of this node's own params.

Node parameters (Video Judge Node): **Metrics** (multi-select, M2/M4/M5/M6 only, default all
video metrics), **batch size**. Same as Text Judge Node, engine config comes from the
required `engine_config` input. There is deliberately no "skip video" toggle: unlike the
CLI's `--skip-video` flag (an orthogonal safety net alongside a single `--judges` list that
can span both modalities), a Video Judge node's `metrics` param is already restricted to
video-only options — "skip video entirely" is already fully expressed by not adding/wiring
the node at all (see Quick Subset below), so a second in-node toggle for the same state
would just be redundant, ambiguous surface (the automatic per-item skip when an item has no
`output_video_path` is unrelated and stays).

Secondary tab (both): a live-updating score-distribution histogram (recharts, sourced from
the node's own in-flight partial results while `running`, falling back to the terminal
result once done — the same batch-eval streaming mechanism the Eval Node uses, extended so
a Judge node's own tab benefits from it too, not just downstream previews) sits above a
summary strip (item count, valid-call count, invalid/errored count, average
`score_1_to_5`) and a per-item rationale viewer — score, `reasoning_lines`,
`evidence`/`issues`, validation flags, and a collapsible **Prompt** section (the exact
`prompt_system`/`prompt_user` text sent for that item/metric). A frame scrubber alongside
the rationale for video metrics is not implemented yet (tracked as a follow-up); today the
rationale text and the source item id are the way to cross-reference it against the actual
rendered video.

#### Ensemble Node

*Category: `node_vejudge`*

Description: combines multiple Judge node runs — different prompt variants, models, or A/B position-swapped pairwise runs (`vejudge/core/ensemble/base.py`) — into one per-item aggregate, and reduces position bias for pairwise setups by swapping A/B order and aggregating both directions.

Input: two or more `judge_result` sockets (from separate Judge nodes) sharing the same `item_id` space.

Output: `judge_result` — the aggregated per-item result, plus inter-member agreement stats.

Node parameters:
* **Aggregation method**: mean / majority vote / stacking.
* **Position-bias correction**: bool, for pairwise ensembles.

Secondary tab: an agreement matrix between ensemble members and a list of the items where members disagree most (drill-through to each member Judge node's rationale for that item).

#### Calibration Node

*Category: `node_vejudge`*

Description: maps raw judge sub-scores to a human-aligned `calibrated_score`
(`vejudge/core/calibration/`). Supports linear regression (default first baseline, currently
implemented in `linear.py`), plus the planned ordinal, isotonic, Platt-style, Bradley-Terry,
ensemble-stacking, and Bayesian variants from `CLAUDE.md`. Always trained on data disjoint from
the held-out test set — the node enforces this via the Dataset node's **Split** tag rather than
trusting the graph author to keep sets separate.

Input: `judge_result` (or `Ensemble` output) for the fit/apply set; `labels` (human annotations) — required in **fit** mode, optional in **apply** mode.

Output: `judge_result` (calibrated) in apply mode; a `model_artifact` (fitted calibration model) in fit mode, which is written to the calibration registry.

Node parameters:
* **Mode**: fit / apply.
* **Model type**: linear / ordinal / isotonic / Platt / Bradley-Terry / ensemble stacking / Bayesian.
* **Registry version**: version to save (fit) or load (apply).
* **Category bias term**: bool — per-`use_case` intercept, per the recommended baseline formula in `CLAUDE.md`.
* **Split assertion**: refuses to fit if the incoming stream mixes items tagged as held-out-test.

Secondary tab: fit diagnostics — residual plot (judge vs. human), the learned weights/coefficients table, and the registry's version history for this calibration model.

#### Aggregation Node

*Category: `node_postprocessing`*

Description: segment-level aggregation and final score alignment
(`vejudge/postprocessing/align.py`). Maps individual judge signals onto the human annotation
dimensions (the M1–M6 → human-dimension crosswalk in `docs/data.md`), derives an overall score,
and applies the severe-error cap: `overall_score = min(weighted_avg(segment_scores),
severe_error_cap)` so one catastrophic segment can't be hidden by many good ones.

Input: `judge_result` (raw or calibrated).

Output: `judge_result` — final structured per-item bundle (aligned dimension scores + overall + rationale), export-ready.

Node parameters:
* **Segment weights**: per-metric/dimension weight vector.
* **Severe error cap**: numeric ceiling on `overall_score`.
* **Output format**: JSON / CSV / report.

Secondary tab: per-item score breakdown showing each weighted segment and whether the severe-error cap was triggered (highlighted when it overrides the weighted average), plus an export preview.

#### Eval Node

*Category: `node_eval`*

Description: computes human-vs-judge agreement (`vejudge/core/eval/metrics.py`,
`vejudge/benchmark/human_gap/runner.py`) — Spearman/Kendall correlation, MAE, quadratic weighted
kappa, pairwise preference accuracy, and calibration error — always broken down per category
(`use_case`), since a judge can look strong overall while failing on one category.

Input: `judge_result_text` + `judge_result_video` (each optional — a text-only or video-only
graph only needs one wired; both are merged per item when both are present) + `labels`.

Output: a metrics report (per-category table) and, for the robustness workflow, bootstrap confidence intervals.

Node parameters:
* **Metrics**: multi-select over the metric list above.
* **Breakdown key**: `use_case` (default) or a custom category field.
* **Comparison baseline**: raw vs. calibrated, or judge A vs. judge B.
* **Bootstrap CI**: bool, with repeat count (mirrors `vejudge-robust`'s temperature × repeats grid).

Streaming preview: if a wired Judge node's **batch size** param is set, this node re-runs
(recomputing the whole report from scratch, not incrementally — Spearman/Kendall/QWK have no
simple incremental update, and at this data scale a full recompute is cheap) against each
in-flight batch and streams a live preview while the Judge node is still running, instead of
only ever showing the final report once the whole run finishes.

Secondary tab: a live-updating human-vs-judge scatter plot (recharts, one series per
dimension — sourced from `metrics_report`'s `rows` field, the raw per-item pairs
`build_aligned_rows` already computes) above the per-dimension metrics table, then a
per-item picker with a real `<video controls>` player for the selected aligned item.
Eval's own inputs (`judge_result_text/video`, `labels`) never carry a file path, so the
video is resolved client-side by tracing the wired graph backward — through whichever
Judge node(s) feed this Eval node, to the Dataset node upstream of *that* — and reading
that Dataset node's own cached `dataset` output by item id, rather than adding a `dataset`
input socket to Eval purely for this display lookup. If every dimension ends up with zero
aligned rows despite real item-id overlap (a metric that was never selected, an
invalid/skipped judge result, a non-numeric score, etc.), `meta.diagnostics` explains
exactly why per dimension instead of leaving the panel silently empty. A per-category bar
chart and a worst-disagreement item list (drilling through to the originating Judge
node's rationale) are not implemented yet.

## Workflows

A workflow is a saved node graph (JSON, stored under the left panel's *Workflows* tab). Every
workflow must round-trip to an equivalent CLI invocation — the interface is a visual layer over
`run/*.sh`, not a second implementation of the pipeline.

### Workflows list

* **Base Benchmark** — `Peanut Source` → `Dataset` → `Preprocessing` → `Text Judge` (M1–M6's
  text half) and `Video Judge` (M1–M6's video half) → `Aggregation` → `Eval`, plus `Dataset`'s
  own `labels` output → `Eval` directly, plus one `LM Engine` node (gpt) feeding `Text
  Judge` and a second (gemini) feeding `Video Judge`. Equivalent to `run/run_base_benchmark.sh`.
* **Robustness Sweep** — Base Benchmark with both LM Engine nodes' temperature and an outer
  repeat count swept as a grid, feeding the Eval node's bootstrap-CI mode. Equivalent to
  `run/run_base_benchmark_robust.sh` (`vejudge-robust`).
* **Quick Subset** — `Peanut Source` → `Dataset` (small sampling ratio or item-id filter) →
  `Text Judge` only (fed by one `LM Engine` node; no Video Judge node wired at all — a graph
  doesn't need a `skip video` toggle when the node itself is simply absent) → `Aggregation`.
  Equivalent to `run/run_quick_subset.sh --limit N` / `run/run_text_only.sh`.
* **Calibration Fit + Apply** — two linked subgraphs sharing one Calibration node's registry
  version: `Peanut Source(seed-calibration split)` → `Dataset` → `Text/Video Judge` →
  `Calibration(fit)` → registry; then `Peanut Source(held-out split)` → `Dataset` →
  `Text/Video Judge` → `Calibration(apply, same version)` → `Eval`.
* **Cost Estimate / Dry Run** — any of the above with the dry-run toggle on; runs item matching
  and reports estimated call counts per Judge node without contacting the gateway. Equivalent to
  `run/estimate_cost.sh`.
