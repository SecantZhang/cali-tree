"""``BenchmarkRunner`` — abstract benchmark lifecycle.

A benchmark is a fixed (dataset split + judge config + calibration version) that
produces a comparison against human labels. Concrete runners implement the steps.

Resume contract (the standard pattern for any long/expensive runner):
- Accept a ``resume_from`` run directory; when set, re-open it (``make_exp_run(run_dir=...)``)
  instead of creating a new one, and keep its existing ``run_config.json``.
- Memoize each expensive unit of work with a ``vejudge.checkpoint.CheckpointStore`` inside the
  run dir; on resume, skip units already in the store and only redo the missing ones.
- Persist only *successful* units, so transient failures (e.g. an unstable endpoint) retry.
- Keep checkpoints **run-scoped** (one store per run): never share across runs, or intended
  re-samples (e.g. robustness repeats) would be wrongly collapsed.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BenchmarkRunner(ABC):
    @abstractmethod
    def load_items(self) -> list[str]:
        """Item ids to evaluate (already matched to human labels)."""

    @abstractmethod
    def run(self) -> dict[str, Any]:
        """Run judges, align to human labels, compute the gap, write outputs."""
