"""Per-item (per-video) gap view.

The dimension-level metrics in ``gap_result.json`` hide *which videos* the judge agrees
or disagrees on. This module collapses the tidy aligned pairs into one row per item, with
mean human / mean judge / signed + absolute gap, and the signed gap per dimension.

Used both inside a benchmark run (writes ``per_item_gap.csv``) and standalone to (re)build
the view for a past run from its ``aligned_pairs.csv`` — no gateway calls needed:

    python -m vejudge.benchmark.per_item logs/exps/<run>-exps
"""

from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any, Optional

from ..core.eval import metrics as M
from ..postprocessing.align import ALIGNMENT, JUDGE_SIGNAL_LABEL

# Stable column order for the per-dimension gap columns.
_DIMS = list(ALIGNMENT.keys())

# Inverse map: distinct judge signal -> the human dimensions that align to it.
# (M5 backs 5 human dims; M3/M6a/M6b/M6c back one each.)
_SIGNAL_TO_DIMS: dict[str, list[str]] = defaultdict(list)
for _dim, _label in JUDGE_SIGNAL_LABEL.items():
    _SIGNAL_TO_DIMS[_label].append(_dim)


def build_per_item_gap(aligned_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One row per item: means + signed/abs gap + per-dimension signed gap (judge−human)."""
    by_item: dict[str, dict[str, Any]] = {}
    for r in aligned_rows:
        iid = r["item_id"]
        slot = by_item.setdefault(
            iid,
            {
                "item_id": iid,
                "project": r.get("project"),
                "model": r.get("model"),
                "use_case": r.get("use_case"),
                "_h": [],
                "_j": [],
                "_gaps": {},
            },
        )
        h = float(r["human"])
        j = float(r["judge_raw"])
        slot["_h"].append(h)
        slot["_j"].append(j)
        slot["_gaps"][r["dimension"]] = j - h

    rows: list[dict[str, Any]] = []
    for iid, s in by_item.items():
        h, j = s["_h"], s["_j"]
        abs_gaps = [abs(x) for x in (jj - hh for hh, jj in zip(h, j))]
        row: dict[str, Any] = {
            "item_id": iid,
            "project": s["project"],
            "model": s["model"],
            "use_case": s["use_case"],
            "n_dims": len(h),
            "mean_human": round(mean(h), 3),
            "mean_judge": round(mean(j), 3),
            "mean_gap_signed": round(mean(j) - mean(h), 3),
            "mean_abs_gap": round(mean(abs_gaps), 3),
        }
        for d in _DIMS:
            g = s["_gaps"].get(d)
            row[f"gap_{d}"] = round(g, 2) if g is not None else None
        rows.append(row)

    # Worst disagreement first — that's what you want to eyeball.
    rows.sort(key=lambda r: r["mean_abs_gap"], reverse=True)
    return rows


def build_per_judge_item(aligned_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One row per (item, distinct judge signal) — each judge counts once.

    For a signal backed by multiple human dims (M5), the human side is the mean of those
    dims; the judge value is identical across them. This avoids the per-dimension table's
    over-weighting of M5.
    """
    # group rows: item -> signal -> {humans:[], judges:[]}
    grouped: dict[str, dict[str, dict[str, list[float]]]] = defaultdict(
        lambda: defaultdict(lambda: {"h": [], "j": []})
    )
    meta: dict[str, dict[str, Any]] = {}
    for r in aligned_rows:
        iid = r["item_id"]
        label = JUDGE_SIGNAL_LABEL.get(r["dimension"])
        if label is None:
            continue
        grouped[iid][label]["h"].append(float(r["human"]))
        grouped[iid][label]["j"].append(float(r["judge_raw"]))
        meta.setdefault(iid, {"project": r.get("project"),
                              "model": r.get("model"), "use_case": r.get("use_case")})

    out: list[dict[str, Any]] = []
    for iid, signals in grouped.items():
        for label, hv in signals.items():
            h = mean(hv["h"])
            j = mean(hv["j"])
            out.append({
                "item_id": iid,
                "project": meta[iid]["project"],
                "use_case": meta[iid]["use_case"],
                "judge_signal": label,
                "n_human_dims": len(hv["h"]),
                "human": round(h, 3),
                "judge": round(j, 3),
                "gap_signed": round(j - h, 3),
                "abs_gap": round(abs(j - h), 3),
            })
    out.sort(key=lambda r: (r["item_id"], r["judge_signal"]))
    return out


def build_per_judge_summary(aligned_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One row per distinct judge signal, aggregated across items (each judge once)."""
    per_item = build_per_judge_item(aligned_rows)
    by_signal: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in per_item:
        by_signal[r["judge_signal"]].append(r)

    rows: list[dict[str, Any]] = []
    for label, recs in by_signal.items():
        H = [r["human"] for r in recs]
        J = [r["judge"] for r in recs]
        rows.append({
            "judge_signal": label,
            "n_items": len(recs),
            "mean_human": round(mean(H), 3),
            "mean_judge": round(mean(J), 3),
            "mean_gap_signed": round(mean(J) - mean(H), 3),
            "mae": round(M.mae(H, J), 3) if M.mae(H, J) is not None else None,
            "spearman": (round(s, 3) if (s := M.spearman(H, J)) is not None else None),
        })
    rows.sort(key=lambda r: (r["mean_gap_signed"]))  # most negative (harshest) first
    return rows


def write_rows_csv(rows: list[dict[str, Any]], path: str | Path) -> None:
    path = Path(path)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def write_per_item_gap(rows: list[dict[str, Any]], path: str | Path) -> None:
    path = Path(path)
    base = ["item_id", "project", "model", "use_case", "n_dims",
            "mean_human", "mean_judge", "mean_gap_signed", "mean_abs_gap"]
    fields = base + [f"gap_{d}" for d in _DIMS]
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k) for k in fields})


def from_aligned_csv(path: str | Path) -> list[dict[str, Any]]:
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main(argv: Optional[list[str]] = None) -> int:
    import argparse

    p = argparse.ArgumentParser(description="Build the per-item (per-video) gap view")
    p.add_argument("run_dir", help="an experiment run dir containing aligned_pairs.csv")
    args = p.parse_args(argv)

    run_dir = Path(args.run_dir)
    aligned = run_dir / "aligned_pairs.csv"
    if not aligned.is_file():
        print(f"No aligned_pairs.csv in {run_dir}", file=sys.stderr)
        return 1

    aligned_rows = from_aligned_csv(aligned)

    # 1) per-item (averaged over human dimensions — note M5 is over-weighted here)
    item_rows = build_per_item_gap(aligned_rows)
    write_per_item_gap(item_rows, run_dir / "per_item_gap.csv")

    # 2) per distinct judge signal, each counted once
    pj_item = build_per_judge_item(aligned_rows)
    pj_summary = build_per_judge_summary(aligned_rows)
    write_rows_csv(pj_item, run_dir / "per_judge_gap.csv")
    write_rows_csv(pj_summary, run_dir / "per_judge_summary.csv")

    print("=== Per-item gap (mean over human dimensions; M5-weighted) ===")
    print(f"{'item_id':<34} {'use_case':<15} {'n':>2} {'human':>6} "
          f"{'judge':>6} {'gap':>6} {'|gap|':>6}")
    for r in item_rows:
        print(f"{r['item_id']:<34} {str(r['use_case']):<15} {r['n_dims']:>2} "
              f"{r['mean_human']:>6} {r['mean_judge']:>6} "
              f"{r['mean_gap_signed']:>+6} {r['mean_abs_gap']:>6}")

    print("\n=== Per-judge-signal summary (each judge counted once) ===")
    print(f"{'judge_signal':<28} {'n':>3} {'human':>6} {'judge':>6} "
          f"{'gap':>6} {'mae':>6} {'spear':>6}")
    for r in pj_summary:
        print(f"{r['judge_signal']:<28} {r['n_items']:>3} {r['mean_human']:>6} "
              f"{r['mean_judge']:>6} {r['mean_gap_signed']:>+6} "
              f"{str(r['mae']):>6} {str(r['spearman']):>6}")

    _print_gate_and_m4(run_dir)

    print(f"\nWrote per_item_gap.csv, per_judge_gap.csv, per_judge_summary.csv to {run_dir}")
    return 0


def _print_gate_and_m4(run_dir: Path) -> None:
    """If judge_outputs.json exists, report M1/M2 gates and M4 (not in the crosswalk)."""
    jo_path = run_dir / "judge_outputs.json"
    if not jo_path.is_file():
        print("\n(M1/M2 gates and M4 need judge_outputs.json — not present for this run; "
              "re-run the benchmark to capture them.)")
        return
    jo = json.loads(jo_path.read_text(encoding="utf-8"))

    def _gate_counts(metric: str) -> tuple[int, int, int]:
        fail = ok = skip = 0
        for judges in jo.values():
            res = judges.get(metric) or {}
            if res.get("skipped"):
                skip += 1
                continue
            parsed = res.get("parsed") or {}
            f = parsed.get("failure")
            if f is True:
                fail += 1
            elif f is False:
                ok += 1
        return ok, fail, skip

    m4_scores = [
        ((judges.get("M4") or {}).get("parsed") or {}).get("score_1_to_5")
        for judges in jo.values()
    ]
    m4_scores = [float(s) for s in m4_scores if isinstance(s, (int, float))]

    print("\n=== Binary gates (judge-only; no human equivalent) ===")
    for m, name in (("M1", "assembly_failure"), ("M2", "render_failure")):
        ok, fail, skip = _gate_counts(m)
        print(f"  {m} {name:<18} pass={ok} fail={fail} skipped={skip}")
    if m4_scores:
        print(f"\n=== M4 visual_alignment (computed but NOT in the crosswalk) ===")
        print(f"  mean M4 score = {mean(m4_scores):.2f} over {len(m4_scores)} items "
              f"(alternate signal for prompt alignment vs M3)")


if __name__ == "__main__":
    sys.exit(main())
