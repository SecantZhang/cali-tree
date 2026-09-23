"""Measure the calibration prompts' verbosity on a real run's checkpoint file.

Reports, per item, the word count of the current (distilled) ``optimized_prompt`` vs the
old verbatim-transcript-dump form it replaced, and the single corpus-level calibration
prompt distilled across all items. The point of the redesign was concision +
generalization (see the calibration section of ``docs/research.md`` /
``calibrated_result.py``); this script quantifies it against actual debate output rather
than a synthetic fixture.

Usage:
    python -m vejudge.core.calibration.debate.eval.measure_prompt_verbosity \
        logs/exps/<ts>-exps/judge_results.jsonl
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from typing import Any

from ..calibrated_result import (
    render_corpus_calibration_prompt,
    render_optimized_prompt_addendum,
)
from ..schema import DebateVerdict


def _load_calibration_entries(path: str) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            key, value = entry.get("key", ""), entry.get("value")
            if "::calibration::" in key and isinstance(value, dict):
                out[key] = value
    return out


def _verdict_from_stored_result(cr: dict[str, Any]) -> DebateVerdict:
    """Rebuild a ``DebateVerdict`` from a stored ``CalibratedResult`` dict.

    Older checkpoints predate ``failure_mode_summary`` on the result, so it's recomputed
    from the transcript turns (matching how ``DebateRunner`` tallies it).
    """
    fms = Counter(
        m
        for t in cr.get("transcript", {}).get("turns", [])
        for m in (t.get("failure_modes") or [])
    )
    return DebateVerdict.from_dict(
        {
            "item_id": cr["item_id"],
            "metric_id": cr["metric_id"],
            "initial_score": cr.get("original_score"),
            "final_score": cr.get("final_score"),
            "score_delta": cr.get("score_delta"),
            "converged": cr.get("converged", False),
            "rounds_run": cr.get("rounds_run", 0),
            "flags": cr.get("flags", []),
            "reasoning_trace": cr.get("reasoning", ""),
            "failure_mode_summary": dict(fms),
            "transcript": cr["transcript"],
            "grounded": cr.get("grounded", False),
        }
    )


def main(path: str) -> None:
    calib = _load_calibration_entries(path)
    if not calib:
        print(f"No calibration entries in {path}")
        return

    old_total = new_total = 0
    new_max = 0
    result_dicts: list[dict[str, Any]] = []
    print(f"{len(calib)} calibrated items in {path}\n")
    for key, cr in calib.items():
        item = key.split("::calibration::")[0]
        old_words = len((cr.get("optimized_prompt") or "").split())
        verdict = _verdict_from_stored_result(cr)
        new_prompt = render_optimized_prompt_addendum(verdict)
        new_words = len(new_prompt.split())
        old_total += old_words
        new_total += new_words
        new_max = max(new_max, new_words)
        result_dicts.append(
            {
                "failure_mode_summary": dict(verdict.failure_mode_summary),
                "score_delta": cr.get("score_delta"),
            }
        )
        print(f"  {item:38s} old={old_words:5d}w  new={new_words:3d}w")

    n = len(calib)
    reduction = 100 * (1 - new_total / old_total) if old_total else 0.0
    print(
        f"\n  mean/item: old={old_total / n:.0f}w  new={new_total / n:.0f}w "
        f"({reduction:.0f}% reduction); new max={new_max}w"
    )
    print("\n  CORPUS calibration prompt (one, item-independent):")
    print("   ", render_corpus_calibration_prompt(result_dicts))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    main(sys.argv[1])
