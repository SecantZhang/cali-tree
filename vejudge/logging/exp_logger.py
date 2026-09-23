"""Experiment run directories: ``logs/exps/<YYMMDD-HH:MM:SS>-exps/``.

Each run gets its own timestamped directory containing ``run.log`` (pipeline
execution), ``llm-histories.log`` (LLM call history), and ``run_config.json``
(the exact config, for reproducibility). This matches the Experiments logging
convention in CLAUDE.md.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from .. import config
from .llm_history import LLMHistoryWriter


def _run_id() -> str:
    return time.strftime("%y%m%d-%H:%M:%S")


@dataclass
class ExperimentRun:
    """Owns a single run directory and its loggers."""

    run_id: str
    run_dir: Path
    logger: logging.Logger
    history: LLMHistoryWriter
    _handler: logging.Handler = field(repr=False, default=None)  # type: ignore[assignment]

    def save_config(self, cfg: dict[str, Any]) -> Path:
        path = self.run_dir / "run_config.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False, default=str)
        return path

    def write_json(self, name: str, obj: Any) -> Path:
        path = self.run_dir / name
        with open(path, "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=2, ensure_ascii=False, default=str)
        return path

    def close(self) -> None:
        if self._handler is not None:
            self.logger.removeHandler(self._handler)
            self._handler.close()


def make_exp_run(
    *,
    logs_root: Optional[Path] = None,
    run_id: Optional[str] = None,
    run_dir: Optional[Path] = None,
) -> ExperimentRun:
    """Create a run directory and wire run.log + llm-histories.log.

    By default the dir is ``logs/exps/<run_id>-exps/``. Pass ``run_dir`` to place it
    somewhere explicit (e.g. nested inside a robustness-grid folder).
    """
    rid = run_id or _run_id()
    if run_dir is not None:
        run_dir = Path(run_dir)
    else:
        root = Path(logs_root) if logs_root else config.LOGS_ROOT
        run_dir = root / "exps" / f"{rid}-exps"
    run_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(f"vejudge.exp.{rid}")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    handler = logging.FileHandler(run_dir / "run.log", encoding="utf-8")
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    logger.addHandler(handler)
    # Also surface to console for interactive runs.
    if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
        stream = logging.StreamHandler()
        stream.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
        logger.addHandler(stream)

    history = LLMHistoryWriter(run_dir / "llm-histories.log")
    return ExperimentRun(
        run_id=rid, run_dir=run_dir, logger=logger, history=history, _handler=handler
    )
