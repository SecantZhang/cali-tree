# Running CaliTree in PyCharm

Open this repository as the project. Shared launch configurations are saved in
`.run/` and appear under **Run → Edit Configurations** after the project reloads.

## One-time interpreter setup

1. In **Settings → Python Interpreter**, select the existing interpreter at
   `<project>/.venv/bin/python`.
2. In **Settings → Languages & Frameworks → JavaScript Runtime** (called
   **Node.js** in some versions), select Node.js and npm. On this Mac their paths
   are `/opt/homebrew/bin/node` and `/opt/homebrew/bin/npm`. The frontend
   configuration uses the project Node runtime.
3. If the npm configuration type is unavailable, enable/install PyCharm's
   Node.js support. See [JetBrains' npm configuration documentation](https://www.jetbrains.com/help/pycharm/run-debug-configuration-npm.html).

The existing `.venv` and `web/node_modules` are already present in this checkout.
For a new checkout, install dependencies once from the project terminal:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[interface,calitree,dev]'
npm --prefix web ci
```

## Launch configurations

| Name | Type | Command / settings |
| --- | --- | --- |
| CaliTree Backend | Python module | `critical.interface.server --host 127.0.0.1 --port 8000 --reload`; project root working directory |
| CaliTree Backend Debug | Python module | Same backend, without `--reload` |
| CaliTree Frontend | npm | `web/package.json`, command `run`, script `dev`, arguments `-- --host 127.0.0.1 --port 5173 --strictPort` |
| CaliTree Full Stack | Compound | Starts CaliTree Backend and CaliTree Frontend together |

Select **CaliTree Full Stack** in the toolbar and click **Run**. Wait for both
servers to report ready, then open:

- UI: [http://127.0.0.1:5173](http://127.0.0.1:5173)
- API documentation: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

The frontend explicitly sets `VITE_API_BASE_URL=http://127.0.0.1:8000`; Vite
also uses `--strictPort` so a port conflict produces an error instead of moving
the UI to a different port. Stop existing processes on these ports before
starting another copy.

The backend configurations set:

```text
CRITICAL_AURORA_BENCH_ROOT=<project>/data/aurora/bench
CRITICAL_LOGS_ROOT=<project>/logs
CRITICAL_WORKFLOWS_ROOT=<project>/workflows
PYTHONUNBUFFERED=1
```

This checkout already has AURORA metadata at the configured local path. If your
data is elsewhere, edit `CRITICAL_AURORA_BENCH_ROOT` in both backend
configurations. Server startup does not download data or run optimizers.
Configure model credentials through the UI's Settings before live model runs;
launch configurations contain no credentials. GEPA, when selected in a node,
uses its separate configured interpreter or `<project>/.venv-gepa/bin/python`.

For the manual canvas, load `workflows/examples/calitree_aurora_canvas.json`, run
the shared partition first, then select each leaf's fit cases in its Data tab.

## Debugging

Run **CaliTree Frontend**, then launch **CaliTree Backend Debug** with **Debug**
for backend breakpoints. The regular backend uses an auto-reload subprocess,
which makes debugger attachment less predictable. Canvas training/judging also
runs in worker subprocesses: enable PyCharm's **Attach to subprocess automatically
while debugging** option to inspect those workers.

For browser-side React breakpoints, create a JavaScript Debug configuration with
URL `http://127.0.0.1:5173` after launching the frontend. If your IDE lacks npm
support, run this command in PyCharm's terminal while running the Python backend
configuration:

```bash
npm --prefix web run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

Compound configurations launch their members in parallel. See
[JetBrains' compound configuration guide](https://www.jetbrains.com/help/pycharm/run-debug-multiple.html).
