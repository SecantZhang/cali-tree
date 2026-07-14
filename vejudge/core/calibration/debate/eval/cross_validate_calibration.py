"""Leave-one-out generalization test for the corpus calibration prompt.

The per-item grounded debate re-scores its *own* item against that item's human anchor,
so its in-sample MAE→0 is near-tautological (it targets the label it's judged on). The
real question is whether a calibration signal learned on some items *transfers* to unseen
ones. That's what the item-independent ``general_optimized_prompt`` is for, and this is
its cross-validation:

For each labeled item ``i`` (leave-one-out):
  - **train (zero cost):** build the corpus prompt from the *other* items' already-cached
    debate results (``render_corpus_calibration_prompt``) — item ``i``'s own debate never
    contributes, so ``i`` is genuinely held out.
  - **baseline (zero cost):** item ``i``'s uncalibrated score is the cached ``judge-<base>``
    result — the judge already scored every item without any calibration.
  - **calibrated (1 live judge call, only with --live):** re-judge item ``i`` with the
    fold's corpus prompt as dataset-wide ``extra_context``.
  - compare ``|baseline_i - human_i|`` vs ``|calibrated_i - human_i|``.

Aggregate held-out MAE, baseline vs calibrated. Because training reuses cached debates,
the *only* new billable calls are the N held-out re-judges (one per item). Without
``--live`` it runs everything except those: per-fold corpus-prompt stability + baseline
held-out MAE, which is already informative.

Usage:
    python -m vejudge.core.calibration.debate.eval.cross_validate_calibration \
        <run_dir> [--metric M5] [--base-node judge-3] [--live]
"""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from statistics import mean
from typing import Any, Optional

from ..calibrated_result import render_corpus_calibration_prompt


def _ensure_failure_mode_summary(cr: dict[str, Any]) -> dict[str, Any]:
    """Backfill ``failure_mode_summary`` from the transcript turns for checkpoints
    written before that field was carried onto ``CalibratedResult`` — so the corpus
    aggregation sees the recurring modes on older runs too."""
    if cr.get("failure_mode_summary"):
        return cr
    fms = Counter(
        m
        for t in cr.get("transcript", {}).get("turns", [])
        for m in (t.get("failure_modes") or [])
    )
    return {**cr, "failure_mode_summary": dict(fms)}


def _load_checkpoint(run_dir: str) -> dict[str, Any]:
    path = os.path.join(run_dir, "judge_results.jsonl")
    out: dict[str, Any] = {}
    with open(path, encoding="utf-8") as f:
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


def cross_validate(
    run_dir: str, *, metric: str, base_node: str, live: bool, model: str = "peanut",
    env_raw: Optional[str] = None,
) -> dict[str, Any]:
    ckpt = _load_checkpoint(run_dir)
    calib = {
        k.split("::calibration::")[0]: _ensure_failure_mode_summary(v)
        for k, v in ckpt.items()
        if f"::calibration::{metric}" in k
    }
    # Only items with a usable human anchor can be a held-out target.
    items = [
        it for it, cr in calib.items() if _weighted_human(cr.get("human_scores")) is not None
    ]
    folds: list[dict[str, Any]] = []
    engine = loader = None
    if live:
        engine, loader = _build_live(metric, model, env_raw)

    for held_out in items:
        train_results = [calib[it] for it in items if it != held_out]
        corpus_prompt = render_corpus_calibration_prompt(train_results)
        human = _weighted_human(calib[held_out].get("human_scores"))
        baseline = _judge_score(ckpt.get(f"{base_node}::{held_out}::{metric}"), metric)
        calibrated = None
        if live and engine is not None:
            calibrated = _rejudge_live(loader, engine, held_out, metric, corpus_prompt)
        folds.append(
            {
                "held_out": held_out,
                "human": human,
                "baseline": baseline,
                "calibrated": calibrated,
                "corpus_prompt": corpus_prompt,
                "baseline_gap": None if baseline is None else abs(baseline - human),
                "calibrated_gap": None if calibrated is None else abs(calibrated - human),
            }
        )

    base_gaps = [f["baseline_gap"] for f in folds if f["baseline_gap"] is not None]
    cal_gaps = [f["calibrated_gap"] for f in folds if f["calibrated_gap"] is not None]
    return {
        "metric": metric,
        "n_items": len(items),
        "folds": folds,
        "baseline_mae": mean(base_gaps) if base_gaps else None,
        "calibrated_mae": mean(cal_gaps) if cal_gaps else None,
    }


def _build_live(metric: str, model: str, env_raw: Optional[str] = None):
    # Imported lazily so the zero-cost path needs no engine/creds/loader machinery.
    from pathlib import Path

    from ....rubric.definitions import JUDGE_METRICS
    from .....database.dl_peanut_eval.loader import PeanutEvalLoader
    from .....lm_engine import get_engine, load_creds

    kind = "gemini" if JUDGE_METRICS[metric].modality == "video" else "gpt"
    creds = load_creds(env_raw_path=Path(env_raw)) if env_raw else load_creds()
    engine = get_engine(kind, creds=creds)
    return engine, PeanutEvalLoader(model=model)


def _rejudge_live(loader, engine, item_id, metric, corpus_prompt) -> Optional[float]:
    from ....judge.registry import make_judge

    sample = loader.load_sample(item_id)
    result = make_judge(metric, engine).run(sample, extra_context=corpus_prompt)
    return _judge_score(result, metric)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--metric", default="M5")
    ap.add_argument("--base-node", default="judge-3")
    ap.add_argument("--model", default="peanut")
    ap.add_argument("--env-raw", default=None, help="path to a .env-raw for --live creds")
    ap.add_argument("--live", action="store_true")
    args = ap.parse_args()

    report = cross_validate(
        args.run_dir, metric=args.metric, base_node=args.base_node,
        live=args.live, model=args.model, env_raw=args.env_raw,
    )
    print(f"Leave-one-out CV over {report['n_items']} labeled items (metric {report['metric']})\n")
    print(f"{'held-out':34s} {'human':>6s} {'base':>5s} {'cal':>5s} {'|b-h|':>6s} {'|c-h|':>6s}")
    for f in report["folds"]:
        base = "—" if f["baseline"] is None else f"{f['baseline']:.1f}"
        cal = "—" if f["calibrated"] is None else f"{f['calibrated']:.1f}"
        bg = "—" if f["baseline_gap"] is None else f"{f['baseline_gap']:.2f}"
        cg = "—" if f["calibrated_gap"] is None else f"{f['calibrated_gap']:.2f}"
        print(f"{f['held_out']:34s} {f['human']:6.2f} {base:>5s} {cal:>5s} {bg:>6s} {cg:>6s}")
    print()
    print(f"  held-out baseline MAE:   {report['baseline_mae']}")
    print(f"  held-out calibrated MAE: {report['calibrated_mae']}  "
          f"{'(run with --live to fill in)' if report['calibrated_mae'] is None else ''}")
    print("\n  per-fold corpus prompts (each excludes its held-out item):")
    for f in report["folds"]:
        print(f"   [{f['held_out']}] {f['corpus_prompt']}")


if __name__ == "__main__":
    main()
