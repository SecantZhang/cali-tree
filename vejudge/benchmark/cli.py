"""``vejudge-bench`` — run the human-vs-judge agreement-gap benchmark.

Examples:
    vejudge-bench --dry-run --models peanut --projects prj-paris-2025
    vejudge-bench --limit 2 --models peanut --projects prj-paris-2025 --judges M3,M5,M6
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from .. import config
from ..lm_engine import LiveCallNotAllowed
from .human_gap import AllJudgeCallsFailed, HumanGapBenchmark


def _csv_list(val: Optional[str]) -> Optional[list[str]]:
    if not val:
        return None
    return [x.strip() for x in val.split(",") if x.strip()]


def _find_last_bench_dir() -> Optional[Path]:
    """Most recent human_gap run dir (a *-exps with benchmark==human_gap in its config)."""
    candidates = []
    for d in sorted((config.LOGS_ROOT / "exps").glob("*-exps")):
        cfg_path = d / "run_config.json"
        if not cfg_path.is_file():
            continue
        try:
            if json.loads(cfg_path.read_text(encoding="utf-8")).get("benchmark") == "human_gap":
                candidates.append(d)
        except (json.JSONDecodeError, OSError):
            continue
    return candidates[-1] if candidates else None


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description="VEJudge human-vs-judge gap benchmark")
    p.add_argument("--models", default="peanut", help="comma list; v1 supports peanut")
    p.add_argument("--projects", default=None, help="comma list of prj-* (default: all)")
    p.add_argument("--judges", default=None, help="comma list e.g. M3,M5,M6 (default: all)")
    p.add_argument("--limit", type=int, default=None, help="max items (cost guardrail)")
    p.add_argument(
        "--concurrency",
        type=int,
        default=1,
        help="parallel calls for text judges (1=sequential). Also the default for video "
        "when --video-concurrency is unset. Gateway allows ~16.",
    )
    p.add_argument(
        "--video-concurrency",
        type=int,
        default=None,
        help="parallel calls for video judges (defaults to --concurrency). Video is "
        "bandwidth/memory-bound, so ~4-8 is the sweet spot.",
    )
    p.add_argument("--skip-video", action="store_true", help="text judges only")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="resolve items + estimate calls without hitting the gateway",
    )
    p.add_argument(
        "--live",
        action="store_true",
        help="authorize real (billable) gateway calls; required for a non-dry-run",
    )
    p.add_argument(
        "--no-health-check",
        action="store_true",
        help="skip the endpoint health probe (don't reorder to a working endpoint)",
    )
    p.add_argument("--text-model", default=None)
    p.add_argument("--video-model", default=None)
    p.add_argument(
        "--temperature",
        type=float,
        default=None,
        help="sampling temperature for both judges (default: engine default 0.3)",
    )
    p.add_argument(
        "--continue", dest="resume", nargs="?", const="__LAST__", default=None,
        help="resume an interrupted run: a run dir, or omit for the most recent. "
             "Reuses checkpointed judge calls; run config read from run_config.json.",
    )
    args = p.parse_args(argv)

    resume_dir: Optional[Path] = None
    model = (_csv_list(args.models) or ["peanut"])[0]
    projects = _csv_list(args.projects)
    judges = _csv_list(args.judges)
    limit, skip_video, temperature = args.limit, args.skip_video, args.temperature
    if args.resume is not None:
        resume_dir = _find_last_bench_dir() if args.resume == "__LAST__" else Path(args.resume)
        if resume_dir is None or not resume_dir.is_dir():
            print(f"Refused: no benchmark run to resume ({args.resume}).", file=sys.stderr)
            return 2
        cfg_path = resume_dir / "run_config.json"
        rc = json.loads(cfg_path.read_text(encoding="utf-8")) if cfg_path.is_file() else {}
        model = rc.get("model", model)
        projects = None if rc.get("projects") in (None, "ALL") else rc["projects"]
        judges = None if rc.get("judges") in (None, "M1..M6") else rc["judges"]
        limit = rc.get("limit", limit)
        skip_video = bool(rc.get("skip_video", skip_video))
        temperature = rc.get("temperature", temperature)
        print(f"Resuming run from {resume_dir} (config read from run_config.json).")
    elif len(_csv_list(args.models) or ["peanut"]) > 1:
        print("v1 supports a single model at a time; using the first.", file=sys.stderr)

    bench = HumanGapBenchmark(
        model=model,
        projects=projects,
        judges=judges,
        limit=limit,
        concurrency=args.concurrency,
        video_concurrency=args.video_concurrency,
        skip_video=skip_video,
        dry_run=args.dry_run,
        allow_live=args.live,
        text_model=args.text_model,
        video_model=args.video_model,
        temperature=temperature,
        resume_from=resume_dir,
        health_check=not args.no_health_check,
    )
    try:
        result = bench.execute()
    except LiveCallNotAllowed as e:
        print(f"Refused: {e}", file=sys.stderr)
        return 2
    except AllJudgeCallsFailed as e:
        print(f"Failed: {e}", file=sys.stderr)
        return 1
    run_dir = bench.run.run_dir if bench.run else "(none)"
    print(f"Done. Outputs in {run_dir}")
    if not args.dry_run:
        n = result.get("n_items")
        print(f"Aligned items: {n}. See gap_result.json for per-dimension metrics.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
