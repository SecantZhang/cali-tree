"""Orchestrator: individual A/B calibration -> post-aggregation into a semantic
decision rule -> fit + evaluate on the small M5 batch.

Pipeline (per the plan): load a completed sandwich run's checkpoint -> for each item run
a fresh mechanism-A/B debate (text) -> extract candidate boolean rules -> canonicalize a
shared question bank -> the judge answers the bank cold per item (one video call) to
build feature vectors [base_score, b1..bK] -> fit four comparators and report in-sample
AND leave-one-out MAE against the human aggregates:

  (a) base            = the judge's own score, uncalibrated
  (b) base+bias       = base + mean(human-base) on the fit set (global recalibration)
  (c) linear[base+b]  = LinearCalibrator over base score + semantic booleans
  (d) tree[base+b]    = DecisionTreeCalibrator over base score + semantic booleans

If (c)/(d) beat (b) held-out, the semantic booleans add signal beyond a plain bias shift.

Engines are injected so the whole thing runs offline with scripted engines (--mock) or
live (--live). Feature vectors are computed once per item and reused across every LOO
fold, so the only billable video calls are N cold feature extractions.
"""

from __future__ import annotations

import argparse
import json
from statistics import mean
from typing import Any, Optional

from ...linear import LinearCalibrator
from ...tree import DecisionTreeCalibrator
from .ab_debate import direction_word, item_own_notes, run_ab_debate
from .cross_validate_calibration import _judge_score, _load_checkpoint, _weighted_human
from .feature_extraction import extract_features
from .question_bank import build_question_bank
from .rule_extraction import extract_candidate_questions


def _mae(preds: list[float], truth: list[float]) -> Optional[float]:
    pairs = [(p, t) for p, t in zip(preds, truth) if p is not None and t is not None]
    return mean(abs(p - t) for p, t in pairs) if pairs else None


def _predict_bias(base_fit: list[float], human_fit: list[float], base_query: float) -> float:
    """(b) base + mean residual on the fit set — pure global bias correction."""
    resid = [h - b for b, h in zip(base_fit, human_fit)]
    return base_query + (mean(resid) if resid else 0.0)


def run_experiment(
    *,
    run_dir: str,
    metric: str,
    base_node: str,
    proxy_engine: Any,
    judge_text_engine: Any,
    feature_judge_engine: Any,
    loader: Any,
    max_rounds: int = 2,
    max_questions: int = 5,
) -> dict[str, Any]:
    ckpt = _load_checkpoint(run_dir)
    calib = {
        k.split("::calibration::")[0]: v
        for k, v in ckpt.items()
        if f"::calibration::{metric}" in k
    }
    items = [it for it, cr in calib.items() if _weighted_human(cr.get("human_scores")) is not None]

    # --- individual A/B calibration + rule mining (text calls) ---
    per_item: dict[str, dict[str, Any]] = {}
    all_candidates: list[dict[str, Any]] = []
    for it in items:
        sample = loader.load_sample(it)
        original = ckpt.get(f"{base_node}::{it}::{metric}") or {}
        base = _judge_score(original, metric)
        human = _weighted_human(calib[it].get("human_scores"))
        direction = direction_word(base, human)
        debate = run_ab_debate(
            sample=sample, metric_id=metric, original_output=original,
            judge_engine=judge_text_engine, proxy_engine=proxy_engine,
            direction=direction, notes=item_own_notes(sample), max_rounds=max_rounds,
        )
        candidates = extract_candidate_questions(
            transcript_text=debate["transcript_text"], metric_id=metric,
            engine=judge_text_engine,
        )
        all_candidates.extend(candidates)
        per_item[it] = {"sample": sample, "base": base, "human": human,
                        "direction": direction, "candidates": candidates}

    # --- aggregation: shared question bank ---
    bank = build_question_bank(candidates=all_candidates, engine=judge_text_engine,
                               max_questions=max_questions)

    # --- cold feature extraction (the only video calls), once per item ---
    for it in items:
        feats = extract_features(
            sample=per_item[it]["sample"], metric_id=metric, questions=bank,
            engine=feature_judge_engine,
        )
        per_item[it]["feature_row"] = feats

    # --- fit + evaluate ---
    usable = [
        it for it in items
        if per_item[it]["base"] is not None and per_item[it]["human"] is not None
        and per_item[it]["feature_row"]["base_score"] is not None
    ]
    bases = {it: per_item[it]["base"] for it in usable}
    humans = {it: per_item[it]["human"] for it in usable}
    # Full feature vector [base, b1..bK]; sub-vector [base] for (a)/(b).
    feats_full = {it: [float(bases[it])] + [float(x) for x in per_item[it]["feature_row"]["booleans"]]
                  for it in usable}
    feat_names = ["base_score"] + [f"q{i+1}" for i in range(len(bank))]

    def eval_split(fit_ids: list[str], query_ids: list[str]) -> dict[str, list[float]]:
        Xb = [[bases[i]] for i in fit_ids]
        yb = [humans[i] for i in fit_ids]
        lin = LinearCalibrator().fit([feats_full[i] for i in fit_ids], yb) if len(fit_ids) >= 2 else None
        tree = DecisionTreeCalibrator().fit([feats_full[i] for i in fit_ids], yb,
                                            feature_names=feat_names) if len(fit_ids) >= 2 else None
        preds = {"base": [], "bias": [], "linear": [], "tree": []}
        for q in query_ids:
            preds["base"].append(bases[q])
            preds["bias"].append(_predict_bias([bases[i] for i in fit_ids], yb, bases[q]))
            preds["linear"].append(lin.predict([feats_full[q]])[0] if lin else bases[q])
            preds["tree"].append(tree.predict([feats_full[q]])[0] if tree else bases[q])
        return preds

    # In-sample: fit and predict on all usable items.
    insample = eval_split(usable, usable)
    truth = [humans[i] for i in usable]
    insample_mae = {k: _mae(v, truth) for k, v in insample.items()}

    # LOO: for each item, fit on the rest, predict it.
    loo_preds = {k: [] for k in ("base", "bias", "linear", "tree")}
    for held in usable:
        rest = [i for i in usable if i != held]
        one = eval_split(rest, [held])
        for k in loo_preds:
            loo_preds[k].append(one[k][0])
    loo_mae = {k: _mae(v, truth) for k, v in loo_preds.items()}

    # Fit the reported tree/linear on the full set for display (metadata / rule text).
    tree_full = DecisionTreeCalibrator().fit([feats_full[i] for i in usable],
                                             [humans[i] for i in usable], feature_names=feat_names)

    return {
        "metric": metric, "n_items": len(usable), "bank": bank,
        "feature_names": feat_names,
        "per_item": {it: {"base": bases[it], "human": round(humans[it], 2),
                          "booleans": per_item[it]["feature_row"]["booleans"],
                          "missing": per_item[it]["feature_row"]["missing"]}
                     for it in usable},
        "insample_mae": insample_mae, "loo_mae": loo_mae,
        "tree_rule": tree_full.metadata().get("rule_text", ""),
    }


def _print_report(r: dict[str, Any]) -> None:
    print(f"\nPrompt-calibration experiment — metric {r['metric']}, n={r['n_items']} items\n")
    print("Shared question bank (semantic decision nodes):")
    if r["bank"]:
        for i, q in enumerate(r["bank"]):
            print(f"  q{i+1} (raises when {q['raises_score_when']}): {q['question']}")
    else:
        print("  (empty — no rules mined)")
    print("\nPer-item (base = uncalibrated judge, human = weighted aggregate, booleans oriented):")
    print(f"  {'item':34s} {'base':>4s} {'human':>5s}  booleans")
    for it, d in r["per_item"].items():
        miss = f"  missing={d['missing']}" if d["missing"] else ""
        print(f"  {it:34s} {d['base']:>4.1f} {d['human']:>5.2f}  {d['booleans']}{miss}")

    def row(name: str, key: str) -> str:
        ins = r["insample_mae"][key]; loo = r["loo_mae"][key]
        f = lambda v: "  —  " if v is None else f"{v:.2f}"
        return f"  {name:22s} in-sample={f(ins)}   LOO={f(loo)}"
    print("\nMAE vs human (lower is better; uncalibrated baseline is row (a)):")
    print(row("(a) base only", "base"))
    print(row("(b) base + global bias", "bias"))
    print(row("(c) linear[base+bools]", "linear"))
    print(row("(d) tree[base+bools]", "tree"))
    print("\nFitted decision rule (full-set, auditable):")
    print(r["tree_rule"] or "  (no tree)")


def _build_live_engines(metric: str, env_raw: Optional[str]):
    from pathlib import Path
    from ....rubric.definitions import JUDGE_METRICS
    from .....database.dl_peanut_eval.loader import PeanutEvalLoader
    from .....lm_engine import get_engine, load_creds

    creds = load_creds(env_raw_path=Path(env_raw)) if env_raw else load_creds()
    # One engine for everything: the debate/extraction/aggregation calls are text (the
    # turn runner never attaches media), the feature-extraction judge call attaches the
    # video — same engine, media decided by the caller. Using the metric's own modality
    # engine (gemini for M5) matches what the cached sandwich runs used and avoids
    # depending on a separate gpt deployment on the gateway. (Judge and proxy share a
    # model here — acceptable for this feasibility pass; note it as a self-bias caveat.)
    kind = "gemini" if JUDGE_METRICS[metric].modality == "video" else "gpt"
    engine = get_engine(kind, creds=creds)
    return engine, engine, PeanutEvalLoader(model="peanut")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--metric", default="M5")
    ap.add_argument("--base-node", default="judge-3")
    ap.add_argument("--max-rounds", type=int, default=2)
    ap.add_argument("--env-raw", default=None)
    ap.add_argument("--live", action="store_true")
    args = ap.parse_args()

    if not args.live:
        raise SystemExit("Refusing to run without --live (real judge calls). See --mock in tests.")
    text_engine, feature_engine, loader = _build_live_engines(args.metric, args.env_raw)
    report = run_experiment(
        run_dir=args.run_dir, metric=args.metric, base_node=args.base_node,
        proxy_engine=text_engine, judge_text_engine=text_engine,
        feature_judge_engine=feature_engine, loader=loader, max_rounds=args.max_rounds,
    )
    _print_report(report)


if __name__ == "__main__":
    main()
