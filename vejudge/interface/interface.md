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
- **Left panel** (hidable) — four tabs: *Nodes* (palette, grouped by category; drag a node onto the canvas to place it at the cursor, or click to drop it at the next grid slot), *Workflows* (saved graphs as JSON, one file per workflow), *Runs* (past runs found under `logs/exps/`; open to inspect a reconstructed run or resume one from checkpoint — see § Loading a past run), *Datasets* (browsable pointers into `data/` and `evaluation/` per `docs/data.md`, independent of any one graph).
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
- **Immediate Stop** — every graph run executes in a dedicated spawned worker process group.
  Stop hard-terminates that group and transitions directly from `running` to terminal
  `stopped`; it never waits for an in-flight HTTP/model call or local descendant process to
  return. Completed append-only checkpoints remain reusable, while the interrupted unit is
  deliberately absent and reruns on Resume. Closing the local client connection cannot
  guarantee that a remote provider cancels work it already accepted.
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
Eval Node whose Judge and human-label item ids never overlapped, still reports
`status: "done"` (matching nothing isn't necessarily wrong) but adds a `meta.warning` string —
surfaced as a log line in the bottom console and as a highlighted line in that node's secondary
tab, so a run that silently did nothing doesn't look identical to one that actually worked. The
Dataset Node also warns proactively, before Eval ever runs, when its sample lands on zero
human-labeled items despite the pre-sampling pool having some (naming the coverage gap and
pointing at the **require_labels** param, which guarantees a labeled sample).

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
- **Input sockets** (left edge) — typed: `samples` (stream of `JudgeSample`-shaped items,
  a Dataset node's sampled-item output — deliberately not named `dataset`, since that name
  collided with the node's own name and its sibling `labels` output), `engine_config`
  (an LM Engine node's config), `judge_spec` (a metric's identity as data — a builtin M1–M6
  preset or a custom free-text judge, from a Judge Prompt node), `judge_result`, `labels`
  (human annotations), `model_artifact` (a calibration/ensemble fit). A socket only accepts
  its matching type.
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
- **Run time** — a small, light-grey elapsed-time readout along the node's *bottom edge*
  (kept off the title bar): live-ticking while `running`, then the final backend-measured
  value after. This is **generic** — the executor stamps `meta.elapsed_ms` (+
  `meta.start_offset_ms`) on *every* node's result centrally (`server/executor.py::_run_node`),
  so all current and future node types get it with no per-node code (see the timing contract
  under Secondary tab below).
- **Execution-order badge** — top-left of the header, `[n]`: this node's 1-based position in
  the *most recently launched* run's actual scope, Jupyter-cell-style. Shown only for a node
  that was actually part of that run — a full-graph run badges every node; a per-node **Run**
  badges just that node's ancestor chain + itself; a **Re-run** badges only that one node.
  Replaced wholesale each time a new run starts, so it always reflects the latest run, never a
  running union of past ones.
- **Run (▶) / Re-run (↻)** — top-right of the header, next to the status dot. **Run** executes
  this node's full ancestor chain plus itself, from scratch (same "graph or a selected
  subgraph" mentioned in the Run controls section above, scoped by clicking a node rather than
  a canvas selection). **Re-run** executes *only* this node, reusing the most recently launched
  run's already-computed outputs for everything upstream — disabled, with a tooltip explaining
  why, until at least one run exists to reuse. Both respect the same dry-run/`--live`
  confirmation as the global Run button, since a per-node run is just as capable of making
  real, billable gateway calls.
- **Stale flag** — a dashed border + a small "stale" badge next to the status dot: this node's
  last real result predates a since-changed ancestor (an upstream node was Run/Re-run after
  this node last ran). The old result keeps displaying — this is an "outdated, not wrong"
  signal, not an error — and clears the moment this node itself completes a run, by any scope.
  Set immediately when a downstream node's ancestor is (re-)run, not once that run finishes.
- **Lock flag** — a padlock badge + a solid accent border: this node's result is *frozen and
  reused* on every run rather than recomputed. Toggled from the top-bar **Lock** button on the
  selected node (only enabled once the node **and all its ancestors** are `done`, since there
  must be a result to reuse). Locking a node also locks all its predecessors; unlocking a node
  cascades forward to its descendants (a downstream lock is only valid while its ancestors stay
  locked). A locked node is read-only (params disabled) and — on any run (global Run, per-node
  Run/Re-run) — is *seeded* from the most recent run and skipped, so execution starts at the
  first unlocked node past the lock frontier. Implemented by generalizing the executor's
  self_only seed mechanism to a set of seeded ids: the run request carries `locked_node_ids` +
  `seed_run_id` (`server/schemas.py`, `routes/runs.py`, `executor.py`'s `seed_node_ids`).
- **Double-click → secondary tab** — opens the secondary window, which has a **tab strip**:
  a per-type **Details** tab (each node's bespoke visualization, documented per node below)
  plus three **generic** tabs every node inherits automatically:
  - **Inputs** — a **schema header** at the top (the node's full input contract: every socket
    as `name: type` with a color swatch + a `fan-in` tag + an **expandable example payload**
    showing that socket type's JSON shape/subfields, shown regardless of runtime state), then
    the raw value on each input socket. Values are reconstructed client-side from incoming edges
    + upstream nodes' outputs (fan-in sockets show a list); large values are summarized, not
    dumped.
  - **Outputs** — a **schema header** (the node's `name: type` output contract + the expandable
    per-type example) at the top, then the raw value on each output socket, from the last run
    (live previews while running).
  - **Timing** — two parts: a whole-run **system waterfall** (every node's start offset +
    duration, this node highlighted) for the big picture, then a **This node** breakdown —
    per-item durations + summary stats from `meta.item_timings` for loop nodes, or the node's
    total run time for a single-phase node.

  **Enforced contract (why this is free for new nodes):** the Inputs/Outputs tabs — **including
  their schema header** — are driven by the **backend node-type API** (`GET /api/nodes`, which
  projects each executor's `input_sockets`/`output_sockets`/`multi_input_sockets` straight from
  `registry.py::type_info()`), read via `web/src/nodes/useNodeSchema.ts` and rendered by
  `SocketSchema.tsx`. The API is therefore the **single source of truth** for a node's I/O
  schema: declaring `input_sockets`/`output_sockets` on a new `NodeExecutor` is all that's
  needed — the schema header + socket lists show for that node and **auto-reflect** any later
  socket change with **no frontend edit**. (`socketTypes.ts` is now only the source for socket
  *colors*, the per-type **example payloads** (`SOCKET_EXAMPLES`, rendered expandably by
  `DataValueView`), and *synchronous connection validation*; these are keyed by socket *type*,
  so the one remaining manual touch is adding a `SOCKET_COLORS`/`SOCKET_EXAMPLES` entry for a
  brand-new socket type — display-only, it falls back to a neutral swatch / name+type only
  otherwise.) The value cards + timing still come from the run store and
  `NodeRunResult.meta` — `elapsed_ms` + `start_offset_ms` stamped centrally by the executor for
  every node, and optional `item_timings` a loop node adds in its per-item loop. A new node type
  gets Inputs/Outputs/Timing tabs and the on-node run-time badge with **no extra code**; it only
  writes a Details tab if it wants a bespoke view.

**Groups** (ComfyUI-style, purely visual) — right-click empty canvas → **Add group here**
drops a translucent, resizable rectangle *behind* the nodes with an editable title. Nodes
whose bounding box touches a group are its members (computed at drag-start via
`web/src/nodes/geometry.ts::nodesInGroup`); dragging the group moves its members rigidly with
it (fixed relative offsets), while resizing only changes which nodes it touches — it never
moves them. Right-click a group → **Remove group**. Groups are not executor nodes (they carry
no execution semantics): they live in a separate `groups` array on the graph, persisted
through save/load (`GraphSpecJSON.groups` ↔ `GraphIn.groups`), and rendered as a React Flow
`group`-type node with a negative `zIndex` (`web/src/nodes/GroupNode.tsx`).

**Node categories** — mostly matching the `interface/` package layout in
`docs/architecture.md`, with one deliberate exception: the LM Engine Node lives in the
`node_vejudge/` Python package (alongside the Judge nodes it configures) but is tagged with
its own `node_lm_engine` category so it gets its own palette grouping/color rather than
being visually lumped in with Judge nodes:

| Category | Package | Color |
|---|---|---|
| Database | `node_db` | blue |
| LM Engine | `node_lm_engine` (lives in the `node_vejudge/` package) | teal |
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
`raw_dataset` is a distinct socket type from `samples` (below, the Dataset node's sampled-item
output) specifically so a source's raw output can never be wired directly into a Judge node —
sampling is always an explicit step.

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

Outputs: `samples` — the sampled subset of the input, same item shape (named `samples`, not
`dataset`, so it can't be confused with the node's own name or with the sibling `labels`
output). `labels` — the human-annotation record for each sampled item that has one (items with
no annotation yet are simply absent, not an error), one record per item, reduced across
annotators per the **Aggregation method** below. Every record always keeps the individual
per-rater values in `raw_scores` alongside the (possibly-null) aggregate `scores`.

Node parameters:
* **Sampling ratio**: dual-purpose size control, default `1.0`. A value **≤ 1** is a *fraction*
  of the dataset (`0.5` = 50%); a value **> 1** is an *absolute item count* (`5` = five items,
  clamped to what's available). Deterministic selection within either mode (see `sampling.py`).
* **Full dataset**: bool toggle, default off. When on, selects the entire (filtered) pool and
  ignores **Sampling ratio** — an explicit "100%" control so `1` in the ratio field is never
  ambiguous between "the whole set" and "a single item". (With the toggle off, the default ratio
  `1.0` also selects everything, so default behavior is unchanged.)
* **Sampling mode**: stratified, or unified (uniform, the default). No separate "full"
  mode — a ratio of 100% under either mode already selects every item, so a mode that
  ignored ratio entirely was redundant and a footgun (silently no-oping ratio for anyone
  who changed it without also changing the mode off its old "full" default).
* **Category filter**: `use_case ∈ {visual montage, speech-driven, voiceover-heavy}`, multi-select, default all.
* **Item id filter**: optional glob/regex over `item_id` (e.g. limit to one project), for the quick-subset style of iteration (`run/run_quick_subset.sh`).
* **Require labels**: bool, default off. When set, the sampling pool is restricted to items
  with a human label *before* ratio/mode is applied — guarantees a downstream Eval node
  never lands on zero overlap by an unlucky small sample. `meta.n_pool_labeled` (the
  pre-sampling pool's label coverage) is always reported regardless of this toggle, and a
  warning fires when it's off and the sample happens to land on zero labeled items anyway.
* **Aggregation method**: dropdown, default **`none`** — how multiple annotators' scores for the
  *same* video are combined into each `labels` record's per-dimension `scores`: `mean` /
  `median` / `max` / `min` (a single point estimate), or **`none`** = no aggregation (the
  default, so individual annotator scores are preserved unless you opt into a summary). Under
  `none`, `scores` is left empty and only the individual per-annotator ratings are exposed (in
  `raw_scores`); the record stays keyed by `item_id` (one per video), so the join to `samples`
  is unchanged. Downstream: a wired **Eval** node detects `none` and scores the judge against
  *each rater individually* (one aligned row per rater, so agreement is judge-vs-rater, not
  judge-vs-consensus — reported as `aggregation: "none"` in its metrics report). **Calibration**
  fitters likewise preserve raw ratings: each rating remains a separate target observation,
  but receives weight `1 / ratings_for_video`, so every video contributes one unit regardless
  of annotator count. Validation stays grouped by video. The adversarial human proxy receives
  one immutable disagreement profile rather than switching between individual targets.

Secondary tab: sampling config (mode/ratio/filters) plus — once run — the resulting selection
count against the raw input's total count, and how many of those got a matching human label.
Below that, a collapsible **Schema** reference (collapsed by default) documenting every field
of a sampled item (`JudgeSample`) and of its joined human label, and — once this node has
completed a run — a list+detail **item browser** over this node's *own sampled/filtered
output* (not the raw loader): the item list flags which items carry a human label, and
selecting one shows the same structured preview the Peanut Source Node uses (prompt, video
player, transcript/captions/assembly-JSON sections, raw-JSON fallback) plus that item's
per-dimension human scores when a label exists — the aggregate score per dimension for
mean/median/max/min, or a **per-rater breakdown** (a column per annotator) when the
aggregation method is `none`. Unlike the raw source browser, this reads the
node's cached `samples`/`labels` outputs from the last run (via the run-status GET, no extra
`/api/datasets` call), so it reflects exactly what was sampled — the shared preview component
lives in `web/src/panels/RightPanel/secondary/JudgeSamplePreview.tsx`.

#### Preprocessing Node

*Category: `node_preprocessing`*

Description: derives cached artifacts from a dataset stream's source/output media — sampled frames, keyframes, short clips, ASR transcript, OCR text, captions, shot boundaries, audio event labels, blur/flicker metrics (`vejudge/preprocessing/pp_template/base.py`). Implements the input-strategy variants from `docs/research.md` § Judge Input Strategies (A–E) as one composable node rather than five separate ones.

Input: `samples` (Dataset node output).

Output: `samples` — the same items, enriched with artifact references. Artifacts are cached by `(item_id, preprocessing_config_hash)`; a node run never re-extracts frames/transcripts that already exist on disk for the current parameter hash.

Node parameters:
* **Artifact types** (multi-select): sampled frames, keyframes, short clips, ASR transcript, OCR text, captions, shot boundaries, audio event labels, blur/flicker metrics.
* **Input strategy**: A (direct video) / B (uniform frame sampling) / C (keyframe/shot sampling) / D (segment-level) / E (multimodal summary) — sets sensible defaults for the artifact-type multi-select above; still individually overridable.
* **Sampling rate / clip length**: numeric, only shown when the relevant artifact type is selected.
* **Cache policy**: reuse-if-present (default) / force recompute.

Secondary tab: per-item artifact viewer — a frame filmstrip, the ASR transcript with timestamps, detected shot boundaries overlaid on a scrub bar, and cache hit/miss counters for the current run.

#### LM Engine Node

*Category: `node_lm_engine`* (lives in the `node_vejudge/` Python package, but tagged with
its own category so it doesn't share Judge nodes' color/palette grouping)

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
* **Engine kind**: gemini / gpt / qwen / claude / deepseek / llama / kimi — one per real
  provider family (`vejudge/lm_engine/_ENGINES`), each a thin `LMEngine` subclass declaring
  only `name`/`default_model`/`supports_video`, all routed through the same shared
  OpenAI-compatible transport. `model` is never validated against `engine_kind`
  server-side (a pure pass-through string to the gateway) — the frontend dropdown groups
  the full model catalog by family purely for UI convenience (`web/src/nodes/
  modelCatalog.ts`), and switching **Engine kind** resets **Model** to the new family's
  first option whenever the current value isn't in its list, so the two params never drift
  out of sync (e.g. a stale `gpt-4.1` left over after switching to `claude`).
* **Model** (defaults to `config.DEFAULT_TEXT_MODEL`, shown directly rather than a blank
  field, since that's the actual value `LMEngine` falls back to when unset) — rendered as a
  dropdown scoped to the selected **Engine kind**, not a free-text input.
* **Temperature** (defaults to `0.3`), **max tokens** (defaults to `4096`).
* **Concurrency** (defaults to `1`; moved here from the Judge nodes' old
  `text_concurrency`/`video_concurrency` params, per this node's original spec).
* **Health-check toggle**: present but inert — `vejudge/lm_engine/health.py` exists at the
  engine layer but isn't wired into the interface's Judge nodes at all yet, matching the
  Preprocessing Node's existing precedent of shipping a param before its behavior lands.

Secondary tab: a light status panel — the effective config (engine kind/model/temperature/
max tokens/concurrency), a **Feeds** list of which Judge node(s) this engine is wired into
(traced off the live graph edges, so it updates as you rewire), and a **Test this engine**
button that probes the gateway endpoints via `POST /api/engines/health-check`
(`vejudge/interface/server/routes/engines.py`, wrapping `vejudge/lm_engine/health.py`'s
`healthy_order`). That probe is a real (billable) 1-token ping per endpoint, so it's gated
by the same `--live` confirm-then-`allow_live` path as any judge call — the button pops the
same real-call `window.confirm` the global Run button uses, and the backend refuses a
non-live request. Results show each endpoint's ok/status/latency with a status dot. Still a
planned future addition (noted inline in the tab): a live tail of this engine's slice of
`llm-histories.log` (prompt hash, token counts, latency, retry/failover timeline), which
would need a new log-streaming route that doesn't exist yet.

#### Judge Prompt Node

*Category: `node_vejudge`*

Description: a config-only node (no gateway call, like the LM Engine Node) that produces a
**`judge_spec`** artifact — a judge's whole identity as data (see
`vejudge/interface/node_vejudge/judge_spec.py`). A metric is no longer a dropdown *on* the
Judge node; it's a wired input, so each metric is its own graph path and a future optimizer
can *produce* a judge. Two kinds:

- **builtin preset** (M1–M6): `{kind: "builtin", metric_id, modality, label}`. Delegates
  entirely to the existing code — the versioned prompt (`vejudge/core/prompts/m{n}_*.py`),
  validation (`core/judge/validate.py`), and human-dimension alignment
  (`postprocessing/align.py`'s `ALIGNMENT`). Zero rewrite of the six existing prompts.
- **custom**: a free-text prompt template (`{placeholder}` fields filled from the sample) +
  a declared `expected_fields`, `score_path` (how to pull the 1–5 score out of the parsed
  output), and `target_dimension` (which human dimension it aligns to). For new/experimental
  judges and the future prompt optimizer.

Input: None. Output: `judge_spec`.

Node parameters: **preset** (M1–M6 or `custom`); the custom-only fields (**modality**,
**system**/**user_template**, **expected_fields**, **score_path**, **target_dimension**,
**spec_id**/**label**) are shown only when preset is `custom`.

### Calibration sub-categories (roles)

The `node_calibration` category splits into two **role sub-categories** (a node declares
one via `NodeExecutor.subcategory`; the palette renders them as sub-folders). Each role has
**one unified I/O contract**, defined once as an abstract template in
`node_calibration/_templates.py` — concrete nodes subclass a template and inherit its
sockets rather than declaring their own, so every node in a sub-category shares the same
input/output shape and new implementations conform by construction. (Nodes elsewhere leave
`subcategory = None` and render flat under their category.)

- **Agent Calibration** (`subcategory="agent"`, `CalibrationProducerNode`) — *producers*.
  Run LLM agents (a judge-vs-human-proxy debate) over a judged dataset to generate a
  calibration signal. Contract: `samples + judge_result + labels + judge_engine +
  human_engine` → `calibration_results + general_calibration`. Member: Adversarial
  Calibration.
- **Model Calibration** (`subcategory="model"`, `CalibrationFitterNode`) — *fitters*.
  Consume a producer's `calibration_results` and fit an interpretable calibration model (a
  rule/decision tree today; other `Calibrator` variants next). Contract: `samples +
  calibration_results + labels + critic_engine` → `judge_rule` (the fitted model/rule).
  Member: Rule/Tree Calibration.

A downstream evaluator (Rule Comparison, `node_eval`) reads a fitter's `judge_rule`. If a
new calibration node genuinely needs a different I/O shape, that is the signal it is a new
*role* (a new template), not a member of an existing one.

**Model Calibration members (fitters):**
- **Rule/Tree Calibration** (`cl_rule_tree`) — mines free-text `qN` rules, an independent
  critic answers them, fits a plain CART over `[base_score, q1..qK]`. New nodes mine the
  bank from a deterministic training partition and evaluate it on a frozen holdout;
  legacy nodes without the mode remain explicitly exploratory grouped LOO.
- **Semantic Tree Calibration** (`cl_semantic_tree`) — an ontology-grounded variant. Its
  deployable features combine fixed target-blind rubric facets with training-debate rules.
  A video-grounded independent critic records signed evidence strength in `[-1, 1]` for
  each decision, rather than collapsing all evidence into sparse booleans. Grounded
  transcript failure counts are excluded because they require held-out labels. It fits an
  **ontology-weighted MAE decision tree** (`SemanticDecisionTreeCalibrator`) with robust
  median leaves. Depth and minimum leaf mass are selected by item-grouped LOO entirely
  inside the training partition (up to the configured depth cap); validation labels never
  choose tree capacity. Rubric features receive direct dimension relevance and debate-rule
  importance comes from the calibration
  **knowledge base** (`vejudge/core/calibration/ontology.py`, built from
  `FAILURE_MODE_TAXONOMY` + `_TENDENCY` + the `ALIGNMENT` dimension crosswalk). Its
  `judge_rule` report adds a `semantic` comparator so the Rule Comparison node shows it
  head-to-head with the CART baseline on the same features. Same fitter I/O contract as
  `cl_rule_tree`; shares its secondary tab. A semantic feature set must improve training-only
  grouped-LOO MAE by at least `0.01` over the best base-only tree, otherwise capacity selection
  visibly falls back to the simpler tree; this prevents a larger rule bank from winning on a
  negligible search fluctuation.

#### Adversarial Calibration Node

*Category: `node_calibration` · Sub-category: Agent Calibration (producer)*

Description: runs a bounded judge-vs-human-proxy debate over a dataset
(`vejudge/core/calibration/debate/`, wired via `vejudge/interface/node_calibration/`) to
produce a **per-item** calibrated result — deliberately not one aggregate prompt for the
whole dataset. The anchor score comes from an upstream Judge Node's `judge_result`
(never computed by this node itself), so the natural graph shape is a visible sandwich:
`Judge (baseline)` → `Adversarial Calibration` → `Judge (calibrated)`, wiring the
calibration output's `calibration_results` into the second Judge Node's `calibration`
input to compare the two directly. Per item, the node then runs a bounded debate: a
human-proxy agent (a skeptical-annotator persona, optionally grounded in a retrieved
real human-annotation note from a *different* item — never this item's own label, to
avoid leaking the very ground truth a later evaluation would compare against) critiques
the judge's score, and the judge agent defends or revises it, converging once the score
stabilizes (a score-delta epsilon) or a round cap is hit — or, in the opt-in **Ground in
human labels** mode (see params below), once the score closes on this item's own real
human aggregate instead of merely stabilizing against itself. Only builtin M1–M6 judge
results are supported today — a `judge_result` produced by a *custom* Judge Prompt spec
is rejected with a clear error, since the debate prompts embed the builtin rubric text
(`core/rubric/definitions.py`'s `metric_definition`), which has no custom-spec
equivalent. A separate "aggregation node" that would combine many items' calibrated
results into one general-purpose prompt is a distinct, not-yet-designed follow-up.

Input: `samples` (a Dataset node's output); `judge_result` (a Judge Node's output —
supplies both the anchor score *and* the metric identity per item, the same "wired
artifact, not a dropdown" convention as everywhere else in this node system; an item
present in `samples` but missing, skipped, or errored in `judge_result` is excluded
from the debate rather than crashing); `labels` (optional — a Dataset node's `labels`
output, used only for the secondary tab's judge-vs-human score comparison, never for
the debate itself); `judge_engine` and `human_engine` (two separate `engine_config`
inputs from two LM Engine nodes — deliberately two distinct sockets of the same type,
so the two roles can run on different model families to mitigate self-bias; in
practice `judge_engine` is usually the same LM Engine Node feeding the upstream
baseline Judge Node, since the judge agent is defending its own prior answer). An optional
`summarizer_engine` is required when **Use LLM summarization** is enabled and controls the
model, temperature, concurrency, and cost of the extra per-item distillation call.

Output: `calibration_results` — `{item_id: {item_id, metric_id, original_score,
final_score, score_delta, converged, rounds_run, flags, optimized_prompt, reasoning,
transcript, human_scores, human_gap, grounded, semantic_summary, summary_mode_requested,
summary_mode_used, summary_version, summary_error}}`. `optimized_prompt` is per-item extra
guidance text (derived from that item's own debate, not a corpus-wide synthesis) meant
to be wired into a downstream Judge Node's `calibration` input (see below), which
injects it as that item's `extra_context` for a re-score. `reasoning` is the debate's
deterministic reasoning-trace text; `transcript` is the full per-round turn-by-turn
record (chat history), plus the upstream Judge run itself (`initial_judge_result`) as
the transcript's actual first message. `human_scores` — `{dim: {score, n}}`, `n` being
the rater count for that dimension — is populated via
`postprocessing.align.ALIGNMENT`'s reverse lookup (or the **Human dimension override**
param below) when `labels` is wired and the metric has a mapped human dimension.
Under aggregation `none`, each entry additionally carries `scores: number[]` while
`score` remains null, preserving the unreduced ratings.
`human_gap` — `{dim: |final_score - human_score| or null}` — is always computed
alongside `human_scores` (independent of **Ground in human labels** below), a raw
passive signal with no invented pass/fail threshold; a human reviewer judges severity
themselves, weighing it against `n`; under `none`, the gap is also a list, one per raw
rating. `grounded` is `true` when this item's debate used either a scalar human anchor
or unreduced raw human ratings (and grounding was opted in). The optimized prompt uses a
shared semantic structure (principle, applicability, observable evidence, scoring guidance,
and optional counter-consideration), with strict removal of human-rating and target-score
content.

Node parameters:
* **Epsilon**: score-delta convergence threshold (default 0.25).
* **Max rounds**: hard cap on debate rounds (default 4, maximum 6).
* **Retrieval enabled**: bool, default on — grounds the human-proxy's critique in a
  similar real human-annotation note when one exists; falls back to persona-only
  otherwise.
* **Batch size**: streaming batch-eval, same convention as the Judge Node.
* **Human dimension override**: optional — overrides the automatic `ALIGNMENT` lookup
  for metrics (M1/M2/M4) with no direct human-dimension mapping.
* **Ground in human labels**: bool, default off — with an aggregated Dataset mode, opts
  into letting the debate's own convergence require closing the gap to this item's score (a
  **rater-count-weighted mean** across the metric's mapped human dimensions, so a
  well-supported dimension counts more than an n=1 one; `core.calibration.debate.runner.DebateRunner.run`),
  instead of merely stabilizing
  against itself round-to-round (which is what let a self-consistent-but-wrong debate
  report as a clean, validated result with nothing flagging the miss). When on, the
  human-proxy's own prompt also cites the real score explicitly as ground truth. With
  Dataset aggregation `none`, the proxy instead receives one immutable histogram/range/
  median/mode disagreement profile with required lower- and higher-rating considerations;
  because there is intentionally no scalar target, convergence remains semantic/score
  stability while the debate is still marked grounded. (The
  judge agent never sees it directly — it only ever reacts to the proxy's argued
  critique, preserving the adversarial debate structure). Off by default since this
  changes what the debate optimizes for; an item with no usable human evidence for this
  run falls back to blind debate automatically regardless of this setting.
* **Use LLM summarization**: bool, default on for newly created nodes — makes one extra
  call per calibrated item through `summarizer_engine`. Invalid, unsafe, or failed output
  visibly falls back to the deterministic rule-based summary. Saved legacy workflows that
  lack this parameter remain rule-based and make no new calls.

Negotiation stops after two rounds without a new normalized semantic finding and detects
`A-B-A-B` score cycles. An oscillating debate is marked unresolved and retains the original
score rather than whichever position happened to speak last. Rule/Tree and Semantic Tree
nodes expose **Evaluation mode**, **Validation fraction**, and **Split seed**. Frozen holdout
defaults to 20% at seed 0, mines only from validated training-item semantic summaries, drops
questions constant on training data, weights raw ratings equally per video, and requires at
least five validation videos plus a ≥0.05 bootstrap-supported MAE improvement before the UI
claims that semantic rules beat global bias.

Secondary tab: a summary strip (item count, converged count, average `|score_delta|`)
above a left item list (score-delta indicator + converged check) and a right detail
panel for the selected item — a chat view opening with the upstream Judge run itself
(metric/score/model/reasoning/tokens + a collapsible full prompt), followed by the
judge-vs-human-proxy debate turns (alternating bubbles, each showing round/score/
reasoning/whether it was grounded in a retrieved note), a score-comparison strip
(original/calibrated/human scores + rater count + gap + delta + flags, plus a
**grounded** tag when this item's debate used real human evidence), and per-item
**Calibrated reasoning**/**Optimized prompt** collapsible sections. The score strip shows
whether the requested summary used the LLM, deterministic rules, or a visible fallback;
the prompt section shows the summary version and fallback error when present.

#### Judge Node

*Category: `node_vejudge`*

Description: the generic judge — `judge_spec` + `engine_config` + `samples` → `judge_result`.
Replaces the old modality-split Text/Video Judge nodes: the wired `judge_spec` now carries the
metric identity and modality, so one node type covers both (a builtin spec runs
`core/judge/Judge`; a custom spec runs its free-text prompt via `judge_spec.run_custom_judge`).
Modality decides video attachment and the per-item "no rendered video" skip gate. Each node
runs one spec across items through the shared concurrent-execution helper
(`node_vejudge/_concurrent_judging.py` — thread pool, checkpointing, streaming batch-eval);
cross-metric parallelism now lives across sibling Judge nodes (the executor runs nodes
sequentially today, so per-metric paths run one after another until a future concurrent-node
executor lands).

Input: `samples` (post-Preprocessing, or directly from a Dataset node), a required
`engine_config` (an LM Engine Node's output), a required `judge_spec` (a Judge Prompt
Node's output), and an optional `calibration` (an Adversarial Calibration Node's
`calibration_results` output — when wired, each item's own `optimized_prompt` is looked
up by item id and injected as that item's extra guidance before the call; builtin specs
only, for now).

Output: `judge_result` — `{item_id: {metric_key: {judge, metric_id, prompt_version,
prompt_system, prompt_user, parsed, raw_content, validation_flags, valid, promptTokens,
completionTokens, totalTokens, model}}}` where `metric_key` is the builtin metric id or the
custom `spec_id`. A custom entry also carries `align: {dimension, score_path}` so the Eval
node can align it generically. `prompt_system`/`prompt_user` are the exact text sent to the LM
for that item — shown in the secondary tab.

Node parameters: **batch size** (streaming batch-eval — see the Eval Node entry). Engine
kind/model/temperature/concurrency come from the `engine_config` input; the metric comes from
the `judge_spec` input.

Secondary tab: a live-updating score-distribution histogram (recharts, sourced from the node's
own in-flight partial results while `running`, falling back to the terminal result once done)
above a summary strip (item count, valid-call count, invalid/errored count, average
`score_1_to_5`) and a per-item rationale viewer — score, `reasoning_lines`, `evidence`/
`issues`, validation flags, and a collapsible **Prompt** section (the exact
`prompt_system`/`prompt_user` sent for that item). A frame scrubber for video metrics is a
tracked follow-up.

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
(`use_case`), since a judge can look strong overall while failing on one category. One generic
node type: it **auto-scopes** its dimensions to whatever the incoming `judge_result` actually
covers, instead of a fixed modality frozenset — a builtin metric resolves its dimensions via
`vejudge/postprocessing/align.py`'s `ALIGNMENT` (e.g. an M3 result → `video_addresses_prompt`;
an M6 result → its three sub-score dimensions), and a custom judge carries its own
`align.dimension`. So each per-metric Judge path feeds straight into its own Eval node,
reporting exactly that metric's dimension(s), and there's no cross-modality merge to reason
about.

Input: `judge_result` (from a Judge node) + `labels` (from a Dataset node).

Output: a metrics report (per-category table, scoped to the incoming metric's dimensions) and,
for the robustness workflow, bootstrap confidence intervals.

Node parameters: none beyond the shared ones below — **Breakdown key**: `use_case` (default)
or a custom category field. **Comparison baseline**: raw vs. calibrated, or judge A vs. judge B.
**Bootstrap CI**: bool, with repeat count (mirrors `vejudge-robust`'s temperature × repeats grid).

Streaming preview: if the wired Judge node's **batch size** param is set, this node re-runs
(recomputing the whole report from scratch, not incrementally — Spearman/Kendall/QWK have no
simple incremental update, and at this data scale a full recompute is cheap) against each
in-flight batch and streams a live preview while the Judge node is still running, instead of
only ever showing the final report once the whole run finishes.

Secondary tab: a live-updating human-vs-judge scatter plot (recharts, one series per
dimension — sourced from `metrics_report`'s `rows` field, the raw per-item pairs
`build_aligned_rows` already computes) above the per-dimension metrics table, then a
per-item picker with a real `<video controls>` player for the selected aligned item.
This node's own inputs (`judge_result`, `labels`) never carry a file path, so the
video is resolved client-side by tracing the wired graph backward — through the
Judge node that feeds this Eval node, to the Dataset node upstream of *that* — and reading
that Dataset node's own cached `samples` output by item id, rather than adding a `samples`
input socket to Eval purely for this display lookup. If every dimension ends up with zero
aligned rows despite real item-id overlap (a metric that was never selected, an
invalid/skipped judge result, a non-numeric score, etc.), `meta.diagnostics` explains
exactly why per dimension instead of leaving the panel silently empty. A per-category bar
chart and a worst-disagreement item list (drilling through to the originating Judge
node's rationale) are not implemented yet.

The metrics table now labels the correlations with the VQA-standard **SRCC / PLCC / KRCC**
(Spearman / Pearson / Kendall), so they read directly against papers like VE-Bench.

#### Alignment Report Node

*Category: `node_eval`*

Description: a **presentation/benchmark** node (like Rule Comparison) — it consumes an Eval
node's `metrics_report` and frames the judge's human-alignment the way VQA papers do:
per-dimension **SRCC / PLCC / KRCC + MAE** beside the **inter-rater human ceiling** (from the
report's `human_ceiling`), plus the **published VE-Bench baselines** (CLIP-F/PickScore →
DOVER/FastVQA/StableVQA → the trained VE-Bench QA) as a reference band, and a one-line verdict
placing the judge's best-dimension SRCC among them. Recomputes nothing (the Eval node did the
correlations); makes no gateway calls.

Input: `metrics_report` (from an Eval node). Output: `comparison` (the framed report).

Secondary tab: the "our judge" SRCC/PLCC/KRCC + human-ceiling table, the VE-Bench reference
table, and the verdict. The VE-Bench baselines are a fixed published reference (only directly
comparable when evaluating VE-Bench itself); it's a separate calibration/benchmark track from
the peanut assembly metrics.

## Workflows

A workflow is a saved node graph (JSON, stored under the left panel's *Workflows* tab). Every
workflow must round-trip to an equivalent CLI invocation — the interface is a visual layer over
`run/*.sh`, not a second implementation of the pipeline.

### Workflows list

* **Base Benchmark** — `Peanut Source` → `Dataset`, fanned out to a per-metric path for each
  aligned metric: a `Judge Prompt` (preset) → `Judge` → `Eval` chain for M3 (text), M5, and M6
  (video), plus `Dataset`'s own `labels` output → each Eval node directly, and two `LM Engine`
  nodes — gpt feeding the text Judge, gemini feeding the video Judges. Equivalent to
  `run/run_base_benchmark.sh`. (`workflows/base_benchmark.json`.)
* **Robustness Sweep** — Base Benchmark with both LM Engine nodes' temperature and an outer
  repeat count swept as a grid, feeding the Eval nodes' bootstrap-CI mode. Equivalent to
  `run/run_base_benchmark_robust.sh` (`vejudge-robust`).
* **Quick Subset** — `Peanut Source` → `Dataset` (small sampling ratio or item-id filter) →
  a single `Judge Prompt`(M3) → `Judge` → `Eval` path (fed by one `LM Engine` node). A
  text-only graph is just the metric paths you wire — no video Judge Prompt/Judge, no "skip
  video" toggle needed. Equivalent to `run/run_quick_subset.sh --limit N` /
  `run/run_text_only.sh`. (`workflows/examples/quick_eval.json`.)
* **Calibration Fit + Apply** — two linked subgraphs sharing one Calibration node's registry
  version: `Peanut Source(seed-calibration split)` → `Dataset` → `Judge Prompt`/`Judge` paths →
  `Calibration(fit)` → registry; then `Peanut Source(held-out split)` → `Dataset` →
  `Judge Prompt`/`Judge` paths → `Calibration(apply, same version)` → `Eval`.
* **Cost Estimate / Dry Run** — any of the above with the dry-run toggle on; runs item matching
  and reports estimated call counts per Judge node without contacting the gateway. Equivalent to
  `run/estimate_cost.sh`.

## Loading a past run

The left panel's *Runs* tab lists every past run found under `logs/exps/*-exps` whose
`run_config.json` marks it as an interface run (`benchmark == "interface_graph"`), newest first,
with its status, workflow name, node count, and number of checkpointed judge calls. Two actions:

* **Open (inspect)** — reconstructs the run into a fresh tab: the graph is loaded from the run
  dir's `workflow_graph.json` (same node ids; positionless nodes auto-grid unless the run's
  `workflow_name` still resolves to a saved workflow, in which case that layout is reused), and
  per-node statuses + outputs hydrate through the normal run-socket path — `GET /api/runs/{id}`
  now **falls back to disk** when the id isn't in the in-memory registry, so the entire existing
  hydration works for a run from a previous server session with no new frontend code. Node
  secondary tabs (Inputs/Outputs/Timing, Eval/Alignment reports) then read the reconstructed
  results exactly as for a live run.
* **Resume** — offered only for a run that stopped short (`error`/`stopped`/`interrupted`);
  continues the existing disk-fresh `resume_from` path, re-executing the graph while skipping
  per-item judge calls already in `judge_results.jsonl`. This is whole-graph resume, not
  mid-node continuation.

**How reconstruction works.** Each terminal run now persists a faithful `run_results.json`
(`{order, node_results}`) alongside `run_status.json`; large collection outputs (e.g. a
multi-thousand-item `raw_dataset`) are stored **summarized** (count + sample keys, matching the
UI's own large-value summarization) to bound run-dir growth, while report/score outputs are
stored in full. When `run_results.json` is present it is used verbatim. For older runs recorded
before this landed, `reconstruct_node_results` does a best-effort rebuild: Eval-family
`eval_*.json` / `alignment_report_*.json` / `rule_eval_*.json` files *are* the node's output;
Judge nodes are reassembled from `judge_results.jsonl` keys (`<node_id>::<item>::<metric>`); other
nodes get an inferred status (`done` if the overall run finished, else neutral) and empty
outputs. These fidelity limits (absent source/dataset outputs, inferred statuses) are surfaced
by the node tabs' existing empty states, not hidden.
