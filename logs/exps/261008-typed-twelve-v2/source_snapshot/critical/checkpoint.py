"""Run-scoped checkpoint store for resumable pipelines.

A ``CheckpointStore`` memoizes completed *units of work* (keyed by an arbitrary string)
inside a run directory, backed by an append-only JSONL file. Any long pipeline
(benchmarking, testing, training) can use it to skip work it already finished when resumed:
construct the store pointing at a prior run's file and `has(key)`/`get(key)` will return the
cached unit.

Design notes:
- **Run-scoped, not a global cache.** Point each run at its own file. Robustness *repeats*
  deliberately re-sample identical inputs, so sharing a store across runs would wrongly
  collapse them — keep one store per run/cell.
- **Only persist what should be reused.** The caller decides what to `put` (e.g. only
  successful results), so transient failures are retried on the next resume.
- **Append-only + thread-safe**, so concurrent workers can checkpoint as they finish.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Iterator


class CheckpointStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._done: dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.is_file():
            return
        with open(self.path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue  # skip a torn last line from an interrupted write
                key = entry.get("key")
                if key is not None:
                    self._done[key] = entry.get("value")  # last write wins

    # --- read --------------------------------------------------------------
    def has(self, key: str) -> bool:
        return key in self._done

    def get(self, key: str) -> Any:
        return self._done.get(key)

    def keys(self) -> list[str]:
        return list(self._done.keys())

    def __len__(self) -> int:
        return len(self._done)

    def __contains__(self, key: str) -> bool:
        return key in self._done

    def items(self) -> Iterator[tuple[str, Any]]:
        return iter(self._done.items())

    # --- write -------------------------------------------------------------
    def put(self, key: str, value: Any) -> None:
        line = json.dumps({"key": key, "value": value}, ensure_ascii=False, default=str)
        with self._lock:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
            self._done[key] = value
