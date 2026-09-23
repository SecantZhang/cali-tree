"""Robustness grid: sweep temperature x repeats and measure judge stability.

Three identical-config runs gave wildly different human-vs-judge correlations. This
harness runs the full base benchmark across a grid of sampling temperatures (rows) and
repeated runs (columns) and reports two things a single run can't:

  1. **Judge self-consistency** across repeats — does the judge return the same scores?
     (per-item score std + run-to-run rank agreement). Human labels are fixed, so this
     isolates judge sampling variance.
  2. **Bootstrap CIs** on each cell's Spearman — given n is tiny (~13), is a swing real
     or just resampling noise on a handful of items?

Each grid cell is one ``HumanGapBenchmark`` run (its own ``logs/exps/<ts>-exps/`` dir);
the combined report lands in ``logs/exps/<ts>-robust/``.

Real calls -> requires --live. The default 4x5 grid is ~20 full runs; always --dry-run first.
"""

from __future__ import annotations

import argparse
import csv
import itertools
import json
import logging
import random
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from statistics import mean, pstdev
from typing import Any, Optional

from .. import config
from ..core.eval.metrics import spearman
from ..lm_engine import LiveCallNotAllowed
from ..logging.exp_logger import make_exp_run
from .human_gap import AllJudgeCallsFailed, HumanGapBenchmark

# ----------------------------------------------------------------------------- #
# Pure analysis helpers (unit-tested without any network)
# ----------------------------------------------------------------------------- #


def _percentile(sorted_vals: list[float], p: float) -> Optional[float]:
    if not sorted_vals:
        return None
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    k = (len(sorted_vals) - 1) * (p / 100.0)
    lo = int(k)
    hi = min(lo + 1, len(sorted_vals) - 1)
    frac = k - lo
    return sorted_vals[lo] * (1 - frac) + sorted_vals[hi] * frac


def bootstrap_spearman(
    human: list[float],
    judge: list[float],
    *,
    n_boot: int = 1000,
    seed: int = 0,
) -> tuple[Optional[float], Optional[float]]:
    """95% bootstrap CI for Spearman(human, judge). (None, None) if too few/degenerate."""
    pairs = [
        (h, j) for h, j in zip(human, judge) if h is not None and j is not None
    ]
    if len(pairs) < 3:
        return (None, None)
    rng = random.Random(seed)
    n = len(pairs)
    vals: list[float] = []
    for _ in range(n_boot):
        sample = [pairs[rng.randrange(n)] for _ in range(n)]
        s = spearman([p[0] for p in sample], [p[1] for p in sample])
        if s is not None:
            vals.append(s)
    if not vals:
        return (None, None)
    vals.sort()
    return (_percentile(vals, 2.5), _percentile(vals, 97.5))


def self_consistency(
    judge_by_repeat: list[dict[str, float]],
) -> tuple[Optional[float], Optional[float]]:
    """Judge stability across repeats for one signal.

    ``judge_by_repeat`` is a list (over repeats) of {item_id: judge_score}. Returns
    (within_item_std_mean, run_to_run_spearman_mean):
      - within_item_std_mean: mean over items (present in all repeats) of the std of the
        judge's score across repeats. 0 = perfectly repeatable.
      - run_to_run_spearman_mean: mean pairwise Spearman of judge scores between repeats.
        1 = identical ranking each time; None if undeterminable.
    """
    repeats = [d for d in judge_by_repeat if d]
    if len(repeats) < 2:
        return (None, None)
    common = set(repeats[0])
    for d in repeats[1:]:
        common &= set(d)
    common = sorted(common)

    within = None
    if common:
        stds = [pstdev([d[item] for d in repeats]) for item in common]
        within = mean(stds)

    corrs: list[float] = []
    for a, b in itertools.combinations(range(len(repeats)), 2):
        xs = [repeats[a][i] for i in common]
        ys = [repeats[b][i] for i in common]
        s = spearman(xs, ys)
        if s is not None:
            corrs.append(s)
    run_to_run = mean(corrs) if corrs else None
    return (within, run_to_run)


# ----------------------------------------------------------------------------- #
# Reading per-cell artifacts
# ----------------------------------------------------------------------------- #


def _f(x: Any) -> Optional[float]:
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def read_cell_summary(run_dir: Path) -> dict[str, dict[str, Any]]:
    """signal -> {spearman, mae, gap, n} from a cell's per_judge_summary.csv."""
    out: dict[str, dict[str, Any]] = {}
    p = run_dir / "per_judge_summary.csv"
    if not p.is_file():
        return out
    for r in csv.DictReader(open(p, encoding="utf-8")):
        out[r["judge_signal"]] = {
            "spearman": _f(r.get("spearman")),
            "mae": _f(r.get("mae")),
            "gap": _f(r.get("mean_gap_signed")),
            "n": int(r["n_items"]) if r.get("n_items") else 0,
        }
    return out


def read_cell_pairs(run_dir: Path) -> dict[str, dict[str, dict[str, float]]]:
    """signal -> {'human': {item: v}, 'judge': {item: v}} from per_judge_gap.csv."""
    out: dict[str, dict[str, dict[str, float]]] = {}
    p = run_dir / "per_judge_gap.csv"
    if not p.is_file():
        return out
    for r in csv.DictReader(open(p, encoding="utf-8")):
        sig = r["judge_signal"]
        h, j = _f(r.get("human")), _f(r.get("judge"))
        if h is None or j is None:
            continue
        slot = out.setdefault(sig, {"human": {}, "judge": {}})
        slot["human"][r["item_id"]] = h
        slot["judge"][r["item_id"]] = j
    return out


# ----------------------------------------------------------------------------- #
# Grid + summary builders
# ----------------------------------------------------------------------------- #


def build_grid_rows(cells: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One row per (temperature, repeat, signal) with metrics + bootstrap CI."""
    rows: list[dict[str, Any]] = []
    for cell in cells:
        run_dir = Path(cell["run_dir"])
        summ = read_cell_summary(run_dir)
        pairs = read_cell_pairs(run_dir)
        for sig, m in summ.items():
            ci_lo = ci_hi = None
            if sig in pairs:
                items = sorted(pairs[sig]["human"])
                h = [pairs[sig]["human"][i] for i in items]
                j = [pairs[sig]["judge"][i] for i in items]
                ci_lo, ci_hi = bootstrap_spearman(h, j)
            rows.append({
                "temperature": cell["temperature"],
                "repeat": cell["repeat"],
                "judge_signal": sig,
                "n": m["n"],
                "spearman": m["spearman"],
                "ci_low": ci_lo,
                "ci_high": ci_hi,
                "gap": m["gap"],
                "mae": m["mae"],
                "run_id": cell["run_id"],
            })
    return rows


def build_summary_rows(cells: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One row per (temperature, signal): agreement spread + judge self-consistency."""
    # group cells by temperature
    by_temp: dict[float, list[dict[str, Any]]] = {}
    for c in cells:
        by_temp.setdefault(c["temperature"], []).append(c)

    rows: list[dict[str, Any]] = []
    for temp, temp_cells in sorted(by_temp.items()):
        summaries = [read_cell_summary(Path(c["run_dir"])) for c in temp_cells]
        pairs = [read_cell_pairs(Path(c["run_dir"])) for c in temp_cells]
        signals = sorted({s for cs in summaries for s in cs})
        for sig in signals:
            spears = [cs[sig]["spearman"] for cs in summaries if sig in cs]
            spears = [s for s in spears if s is not None]
            judge_by_repeat = [
                p[sig]["judge"] for p in pairs if sig in p
            ]
            within, run2run = self_consistency(judge_by_repeat)
            rows.append({
                "temperature": temp,
                "judge_signal": sig,
                "n_repeats": len(temp_cells),
                "human_spearman_mean": round(mean(spears), 3) if spears else None,
                "human_spearman_std": round(pstdev(spears), 3) if len(spears) > 1 else (0.0 if spears else None),
                "within_item_std_mean": round(within, 3) if within is not None else None,
                "run_to_run_spearman_mean": round(run2run, 3) if run2run is not None else None,
            })
    return rows


def _write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def _write_report(
    out_dir: Path, cfg: dict[str, Any], summary: list[dict[str, Any]]
) -> None:
    lines = [
        f"# Robustness grid — {out_dir.name}",
        "",
        f"Grid: temperatures {cfg['temperatures']} x {cfg['repeats']} repeats "
        f"= {len(cfg['temperatures']) * cfg['repeats']} cells. Judges {cfg['judges']}.",
        "",
    ]
    if cfg.get("aborted"):
        lines += [
            f"> ⚠️ **ABORTED after {cfg.get('cells_completed')} completed cell(s)** — a cell's "
            "judge calls all failed (likely auth/credit/gateway). Tables below cover only the "
            f"completed cells. Cause: {cfg['aborted']}",
            "",
        ]
    lines += [
        "## Per-temperature, per-judge summary",
        "",
        "| temp | judge | repeats | human ρ mean | human ρ std | judge within-item std | judge run↔run ρ |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in summary:
        lines.append(
            f"| {r['temperature']} | {r['judge_signal']} | {r['n_repeats']} | "
            f"{r['human_spearman_mean']} | {r['human_spearman_std']} | "
            f"{r['within_item_std_mean']} | {r['run_to_run_spearman_mean']} |"
        )
    lines += [
        "",
        "## How to read this",
        "",
        "- **judge within-item std ~0 at temp 0 but >0 at higher temp** ⇒ the swings are "
        "driven by sampling randomness (calibration on a noisy signal won't help until "
        "temperature is lowered / scores are averaged).",
        "- **low within-item std but high human ρ std / wide bootstrap CI** (see "
        "`robust_grid.csv`) ⇒ the judge is stable; the swing is small-n correlation noise "
        "on ~13 items (need more items, not lower temperature).",
        "- **run↔run ρ near 1** means the judge ranks videos the same way each run; near 0 "
        "means its ranking is essentially re-rolled each time.",
        "",
        "See `robust_grid.csv` (per-cell Spearman + bootstrap CI) and `robust_summary.csv`.",
    ]
    (out_dir / "robust_report.md").write_text("\n".join(lines), encoding="utf-8")


# ----------------------------------------------------------------------------- #
# Resume helpers
# ----------------------------------------------------------------------------- #

import re  # noqa: E402

_CELL_RE = re.compile(r"^temp([0-9.]+)_rep([0-9]+)-exps$")


def cell_is_complete(cell_dir: Path) -> bool:
    """A cell is complete iff per_judge_summary.csv has at least one data row."""
    p = Path(cell_dir) / "per_judge_summary.csv"
    if not p.is_file():
        return False
    with open(p, encoding="utf-8") as f:
        return sum(1 for _ in f) > 1  # header + >=1 data row


def scan_complete_cells(out_dir: Path) -> list[dict[str, Any]]:
    """All complete cells on disk under a robust dir (regardless of session)."""
    out_dir = Path(out_dir)
    cells: list[dict[str, Any]] = []
    for d in sorted(out_dir.glob("temp*_rep*-exps")):
        m = _CELL_RE.match(d.name)
        if not m or not cell_is_complete(d):
            continue
        cells.append({
            "temperature": float(m.group(1)),
            "repeat": int(m.group(2)),
            "run_id": d.name,
            "run_dir": str(d),
        })
    return cells


def find_last_robust_dir(logs_root: Optional[Path] = None) -> Optional[Path]:
    root = Path(logs_root) if logs_root else config.LOGS_ROOT
    dirs = sorted((root / "exps").glob("*-robust"))
    return dirs[-1] if dirs else None


def load_grid_config(robust_dir: Path) -> dict[str, Any]:
    p = Path(robust_dir) / "robust_config.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}


# ----------------------------------------------------------------------------- #
# Orchestrator
# ----------------------------------------------------------------------------- #


@dataclass
class RobustBenchmark:
    temperatures: list[float] = field(default_factory=lambda: [0.0, 0.3, 0.7, 1.0])
    repeats: int = 5
    model: str = "peanut"
    projects: Optional[list[str]] = None
    judges: Optional[list[str]] = None
    limit: Optional[int] = None
    concurrency: int = 8
    video_concurrency: Optional[int] = 4
    skip_video: bool = False
    allow_live: bool = False
    dry_run: bool = False
    health_check: bool = True
    resume_from: Optional[Path] = None  # robust dir to resume

    def _out_dir(self) -> Path:
        rid = time.strftime("%y%m%d-%H:%M:%S")
        d = config.LOGS_ROOT / "exps" / f"{rid}-robust"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _make_cell(self, temperature: float) -> HumanGapBenchmark:
        return HumanGapBenchmark(
            model=self.model,
            projects=self.projects,
            judges=self.judges,
            limit=self.limit,
            concurrency=self.concurrency,
            video_concurrency=self.video_concurrency,
            skip_video=self.skip_video,
            allow_live=self.allow_live,
            temperature=temperature,
            health_check=self.health_check,
        )

    def run(self) -> dict[str, Any]:
        resuming = self.resume_from is not None
        out_dir = Path(self.resume_from) if resuming else self._out_dir()
        logger = _grid_logger(out_dir)
        n_cells = len(self.temperatures) * self.repeats
        cfg = {
            "temperatures": self.temperatures,
            "repeats": self.repeats,
            "model": self.model,
            "projects": self.projects or "ALL",
            "judges": self.judges or "M1..M6",
            "skip_video": self.skip_video,
            "n_cells": n_cells,
            "concurrency": self.concurrency,
            "video_concurrency": self.video_concurrency,
        }
        if not (resuming and (out_dir / "robust_config.json").is_file()):
            (out_dir / "robust_config.json").write_text(
                json.dumps(cfg, indent=2, default=str), encoding="utf-8"
            )

        if self.dry_run:
            return self._dry_run(out_dir, logger, cfg, n_cells, resuming)

        if resuming:
            done_now = len(scan_complete_cells(out_dir))
            logger.info("RESUMING %s — %d/%d cells already complete", out_dir, done_now, n_cells)

        cells: list[dict[str, Any]] = []
        aborted: Optional[str] = None
        i = 0
        for temp in self.temperatures:
            if aborted:
                break
            for rep in range(1, self.repeats + 1):
                i += 1
                cell_dir = out_dir / f"temp{temp}_rep{rep}-exps"
                if resuming and cell_is_complete(cell_dir):
                    logger.info("=== cell %d/%d  temp=%s  repeat=%d — skip (complete) ===",
                                i, n_cells, temp, rep)
                    continue
                logger.info("=== cell %d/%d  temp=%s  repeat=%d ===", i, n_cells, temp, rep)
                cell = self._make_cell(temp)
                # Resume an incomplete cell's own checkpoint (reuses its successful calls).
                cell.resume_from = cell_dir if cell_dir.exists() else None
                cell.run = make_exp_run(
                    run_id=f"{out_dir.name}-t{temp}-r{rep}", run_dir=cell_dir
                )
                try:
                    cell.execute()
                    cells.append({
                        "temperature": temp,
                        "repeat": rep,
                        "run_id": cell.run.run_id if cell.run else None,
                        "run_dir": str(cell.run.run_dir) if cell.run else None,
                    })
                except AllJudgeCallsFailed as e:
                    # Whole cell failed (auth/credit/gateway). Continuing the grid would
                    # just burn hours on the same failure — abort and report.
                    logger.error("  ABORTING GRID: %s", e)
                    cells.append({
                        "temperature": temp, "repeat": rep,
                        "run_id": None, "run_dir": None, "error": str(e),
                    })
                    aborted = str(e)
                    break
                except Exception as e:  # noqa: BLE001 - a one-off cell error isn't fatal
                    logger.error("  cell failed (temp=%s repeat=%d): %s", temp, rep, e)
                    cells.append({
                        "temperature": temp, "repeat": rep,
                        "run_id": None, "run_dir": None, "error": str(e),
                    })

        if aborted:
            logger.error(
                "Grid aborted after %d/%d cells. Analyzing the %d completed cell(s).",
                len(cells), n_cells, sum(1 for c in cells if c.get("run_dir")),
            )
        (out_dir / "cells.json").write_text(
            json.dumps(cells, indent=2, default=str), encoding="utf-8"
        )
        # Analyze ALL complete cells on disk (covers cells from prior resume sessions too).
        ok_cells = scan_complete_cells(out_dir)
        cfg["aborted"] = aborted
        cfg["cells_completed"] = len(ok_cells)
        grid = build_grid_rows(ok_cells)
        summary = build_summary_rows(ok_cells)
        _write_csv(grid, out_dir / "robust_grid.csv")
        _write_csv(summary, out_dir / "robust_summary.csv")
        _write_report(out_dir, cfg, summary)
        logger.info("Wrote robust_grid.csv, robust_summary.csv, robust_report.md to %s", out_dir)

        return {"out_dir": str(out_dir), "n_cells": n_cells, "cells_ok": len(ok_cells),
                "aborted": aborted, "grid": grid, "summary": summary}

    def _dry_run(
        self, out_dir: Path, logger, cfg: dict, n_cells: int, resuming: bool = False
    ) -> dict[str, Any]:
        base = HumanGapBenchmark(
            model=self.model, projects=self.projects, judges=self.judges,
            limit=self.limit, skip_video=self.skip_video, dry_run=True,
        )
        per_cell = base.execute()  # writes its own dry_run dir; no gateway calls
        ec = per_cell.get("estimated_calls", {})
        v = ec.get("video_judge_calls", 0)
        t = ec.get("text_judge_calls", 0)
        n_complete = len(scan_complete_cells(out_dir)) if resuming else 0
        pending = n_cells - n_complete
        report = {
            "dry_run": True,
            "resume": resuming,
            "out_dir": str(out_dir),
            "grid": f"{len(self.temperatures)} temps x {self.repeats} repeats = {n_cells} cells",
            "cells_complete": n_complete,
            "cells_pending": pending,
            "items_per_cell": per_cell.get("n_items"),
            "calls_per_cell": {"video": v, "text": t},
            "total_calls_pending": {"video": v * pending, "text": t * pending},
            "rough_minutes_estimate": round(pending * 10.5),
            "note": "No gateway calls. ~10.5 min/cell observed at conc 8/4.",
        }
        (out_dir / "dry_run.json").write_text(
            json.dumps(report, indent=2, default=str), encoding="utf-8"
        )
        logger.info(
            "DRY RUN%s: %d/%d cells pending, ~%d video + %d text calls, ~%d min",
            " (resume)" if resuming else "", pending, n_cells,
            v * pending, t * pending, report["rough_minutes_estimate"],
        )
        return report


def _grid_logger(out_dir: Path) -> logging.Logger:
    logger = logging.getLogger(f"vejudge.robust.{out_dir.name}")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    fh = logging.FileHandler(out_dir / "run.log", encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s: %(message)s"))
    logger.addHandler(fh)
    if not any(isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
               for h in logger.handlers):
        sh = logging.StreamHandler()
        sh.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
        logger.addHandler(sh)
    return logger


def _csv_list(val: Optional[str]) -> Optional[list[str]]:
    if not val:
        return None
    return [x.strip() for x in val.split(",") if x.strip()]


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description="VEJudge robustness grid (temperature x repeats)")
    p.add_argument("--temperatures", default="0.0,0.3,0.7,1.0", help="comma list of temps")
    p.add_argument("--repeats", type=int, default=5)
    p.add_argument("--models", default="peanut")
    p.add_argument("--projects", default=None)
    p.add_argument("--judges", default=None)
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--concurrency", type=int, default=8)
    p.add_argument("--video-concurrency", type=int, default=4)
    p.add_argument("--skip-video", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--live", action="store_true")
    p.add_argument("--no-health-check", action="store_true")
    p.add_argument(
        "--continue", dest="resume", nargs="?", const="__LAST__", default=None,
        help="resume an unfinished grid: a *-robust dir, or omit for the most recent. "
             "The grid is read from the run's robust_config.json (grid flags ignored).",
    )
    args = p.parse_args(argv)

    resume_dir: Optional[Path] = None
    if args.resume is not None:
        resume_dir = (
            find_last_robust_dir() if args.resume == "__LAST__" else Path(args.resume)
        )
        if resume_dir is None or not resume_dir.is_dir():
            print(f"Refused: no robust run to resume ({args.resume}).", file=sys.stderr)
            return 2
        gcfg = load_grid_config(resume_dir)
        temps = [float(x) for x in gcfg.get("temperatures", [0.0, 0.3, 0.7, 1.0])]
        repeats = int(gcfg.get("repeats", 5))
        model = gcfg.get("model", "peanut")
        projects = None if gcfg.get("projects") in (None, "ALL") else gcfg["projects"]
        judges = None if gcfg.get("judges") in (None, "M1..M6") else gcfg["judges"]
        skip_video = bool(gcfg.get("skip_video", False))
        print(f"Resuming grid from {resume_dir} (stored grid: {len(temps)} temps x "
              f"{repeats} repeats; CLI grid flags ignored).")
    else:
        temps = [float(x) for x in args.temperatures.split(",") if x.strip()]
        repeats = args.repeats
        model = (_csv_list(args.models) or ["peanut"])[0]
        projects = _csv_list(args.projects)
        judges = _csv_list(args.judges)
        skip_video = args.skip_video

    bench = RobustBenchmark(
        temperatures=temps,
        repeats=repeats,
        model=model,
        projects=projects,
        judges=judges,
        limit=args.limit,
        concurrency=args.concurrency,
        video_concurrency=args.video_concurrency,
        skip_video=skip_video,
        allow_live=args.live,
        dry_run=args.dry_run,
        health_check=not args.no_health_check,
        resume_from=resume_dir,
    )
    try:
        result = bench.run()
    except LiveCallNotAllowed as e:
        print(f"Refused: {e}", file=sys.stderr)
        return 2
    if result.get("aborted"):
        print(
            f"ABORTED after {result['cells_ok']} cell(s): {result['aborted']}",
            file=sys.stderr,
        )
        print(f"Partial outputs in {result['out_dir']}")
        return 1
    print(f"Done. Outputs in {result['out_dir']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
