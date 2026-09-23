"""Measure the in-sample effect of the judge -> calibration -> judge sandwich.

Compares, per item, the baseline (uncalibrated) judge score against the calibrated
judge's score and the human anchor, all from a completed sandwich run's checkpoint
(no new calls). Answers "did calibration move scores, and toward humans?".

IMPORTANT — this is *in-sample*: in grounded mode the debate targets each item's own
human score, so a calibrated score landing near the human value is close to tautological
(it memorized the label it's being scored against). For a generalization estimate that
holds out the label, use ``cross_validate_calibration``.

Usage:
    python -m vejudge.core.calibration.debate.eval.measure_sandwich_effect \
        <run_dir> [--metric M5] [--base-node judge-3] [--calibrated-node judge-7]
"""

from __future__ import annotations

import argparse
import json
import os
from statistics import mean
from typing import Any, Optional


def _load(run_dir: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    with open(os.path.join(run_dir, "judge_results.jsonl"), encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                e = json.loads(line)
                out[e["key"]] = e["value"]
    return out


def _judge_score(v: Optional[dict[str, Any]], metric: str) -> Optional[float]:
    parsed = (v or {}).get("parsed") or {}
    key = "overall_av_sync_score" if metric == "M6" else "score_1_to_5"
    s = parsed.get(key)
    return float(s) if isinstance(s, (int, float)) and not isinstance(s, bool) else None


def _weighted_human(human_scores: Optional[dict[str, Any]]) -> Optional[float]:
    num = den = 0.0
    for info in (human_scores or {}).values():
        sc, n = info.get("score"), info.get("n", 0)
        if sc is not None and n > 0:
            num += sc * n
            den += n
    return num / den if den > 0 else None


def main(run_dir: str, metric: str, base_node: str, cal_node: str) -> None:
    E = _load(run_dir)
    items = [k.split("::calibration::")[0] for k in E if f"::calibration::{metric}" in k]
    grounded = any(E[k].get("grounded") for k in E if f"::calibration::{metric}" in k)
    print(f"Sandwich run {run_dir}  ({'grounded' if grounded else 'blind'} debate, metric {metric})\n")
    print(f"{'item':34s} {'human':>6s} {'base':>5s} {'cal':>5s} {'|b-h|':>6s} {'|c-h|':>6s}  moved")
    base_gaps, cal_gaps, changed = [], [], 0
    for it in items:
        b = _judge_score(E.get(f"{base_node}::{it}::{metric}"), metric)
        c = _judge_score(E.get(f"{cal_node}::{it}::{metric}"), metric)
        h = _weighted_human((E.get(f"{it}::calibration::{metric}") or {}).get("human_scores"))
        if None in (b, c, h):
            print(f"{it:34s}  (missing b={b} c={c} h={h})")
            continue
        bg, cg = abs(b - h), abs(c - h)
        base_gaps.append(bg)
        cal_gaps.append(cg)
        moved = (
            "same" if abs(c - b) < 1e-9
            else "closer" if cg < bg - 1e-9
            else "farther" if cg > bg + 1e-9
            else "sideways"
        )
        if abs(c - b) >= 1e-9:
            changed += 1
        print(f"{it:34s} {h:6.2f} {b:5.1f} {c:5.1f} {bg:6.2f} {cg:6.2f}  {moved}")
    if base_gaps:
        print(
            f"\n  scores changed by calibration: {changed}/{len(base_gaps)}\n"
            f"  baseline MAE={mean(base_gaps):.2f}  calibrated MAE={mean(cal_gaps):.2f}  "
            f"delta={mean(cal_gaps) - mean(base_gaps):+.2f}  (in-sample; see module docstring)"
        )


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--metric", default="M5")
    ap.add_argument("--base-node", default="judge-3")
    ap.add_argument("--calibrated-node", default="judge-7")
    args = ap.parse_args()
    main(args.run_dir, args.metric, args.base_node, args.calibrated_node)
