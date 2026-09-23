# VEJudge Interface — web

React frontend for the ComfyUI-style node-graph interface (`../vejudge/interface/interface.md`).
Only 3 of the 8 planned node types are implemented — Dataset, Judge, Eval — matching the
backend's current scope (see `docs/architecture.md`'s Interface API section).

npm-managed and **not part of the Python package** (`pyproject.toml`'s
`include=["vejudge*"]` already excludes it — no packaging changes needed here).

## Dev setup

```bash
npm install
cp .env.example .env.local   # point VITE_API_BASE_URL at the backend if not the default
npm run dev                  # http://127.0.0.1:5173 by default; note: --host defaults to
                              # `localhost`, which can resolve to ::1 in some environments —
                              # pass --host 127.0.0.1 if the dev server seems unreachable
```

Requires the backend running separately: `../run/run_interface.sh` (see the main
`README.md`'s "Running the visual interface" section).

## Scripts

| Command | What |
|---|---|
| `npm run dev` | Vite dev server with HMR |
| `npm run build` | Typecheck (`tsc -b`) + production build to `dist/` |
| `npm run test` | Vitest — component/store/socket-typing tests, jsdom environment |
| `npm run lint` | oxlint (requires Node ≥22.12 for its native binding; a known gap on older Node 22.x patch versions) |

## Structure

```
src/
├── api/          REST client (nodes/workflows/runs/datasets) + ws URL helper
├── canvas/       GraphCanvas.tsx — the React Flow wrapper
├── hooks/        useRunSocket — resync-then-subscribe run status/log streaming
├── nodes/        DatasetNode/JudgeNode/EvalNode + socket-type/param-schema mirrors
├── panels/       TopBar (run controls), LeftPanel (Nodes/Workflows/Datasets tabs),
│                 RightPanel (Inspector + secondary-tab modal), BottomPanel (Console)
├── store/        graphStore (nodes/edges, toJSON/loadGraph) + runStore (run status/logs)
└── theme/        light/dark ThemeProvider, persisted to localStorage
```

Only the 3 in-scope node types have palette entries, custom node components, and secondary
tabs — no stubs for Preprocessing/LM Engine/Ensemble/Calibration/Aggregation.
