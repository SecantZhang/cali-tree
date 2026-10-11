# Historical optimizers

These implementations are archived, executable compatibility code. Extend the current fulfillment optimizer and
`shared/` components for new work. Do not delete this package while callers, tests or historical reproductions use it.

- Root modules: original casewise structural optimizer and acceptance/evaluation/edit implementations.
- `robust/`: v3 greedy/Pareto search, refinement, deterministic typed evidence, v4 semantic evidence factory,
  v5 Boolean counting and v6 endpoint factories. Their shared execution/search/feedback code has been extracted.
- `backends/`: original whole-program TextGrad and GEPA comparison adapters and isolated GEPA worker.

Former module paths are compatibility aliases, preserving module identity and patching behavior. No historic experiment
programs, manifests, observations, reports, snapshots or templates were moved or rewritten. Runtime loaders for v2–v7
remain at their stable paths; artifact versions are dispatch contracts, not competing algorithm defaults.
