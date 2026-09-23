"""Measure the agreement gap between human annotators and LLM judges.

Pipeline:
  1. Load + aggregate human annotations (one row per project::prompt::model).
  2. Match to judge samples via the peanut loader.
  3. Run the selected judges (text -> GPT, video -> Gemini) on each matched item.
  4. Align judge signals to human dimensions (postprocessing.align).
  5. Compute per-dimension / per-category gap metrics + pairwise accuracy.
  6. Write everything through the experiments-logging convention.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from ... import config
from ...checkpoint import CheckpointStore
from ...core.eval.report import per_dimension_agreement
from ...core.judge import make_judge
from ...core.judge.registry import ALL_JUDGES, JUDGE_MODALITY
from ...database.dl_human_annotations import (
    aggregate_annotations,
    load_human_annotations,
)
from ...database.dl_peanut_eval import PeanutEvalLoader
from ...database.dl_peanut_eval.loader import use_case_for
from ...lm_engine import get_engine, load_creds, require_live
from ...logging.exp_logger import ExperimentRun, make_exp_run
from ...postprocessing.align import build_aligned_rows, derive_overall
from ...workflow import JudgeEngines
from ..bench_template import BenchmarkRunner


class AllJudgeCallsFailed(RuntimeError):
    """Every attempted judge call errored — the run produced no usable judgments."""


def all_calls_failed(per_item_judges: dict[str, dict[str, Any]]) -> Optional[str]:
    """Return a sample error string if EVERY non-skipped judge call errored, else None.

    Used to abort instead of silently writing an empty cell when auth/credit/gateway dies.
    """
    attempted = [
        r for judges in per_item_judges.values()
        for r in judges.values() if not r.get("skipped")
    ]
    if not attempted:
        return None
    errored = [r for r in attempted if r.get("error")]
    if len(errored) == len(attempted):
        return str(errored[0].get("error"))
    return None


@dataclass
class HumanGapBenchmark(BenchmarkRunner):
    model: str = "peanut"
    projects: Optional[list[str]] = None
    judges: Optional[list[str]] = None
    limit: Optional[int] = None
    skip_video: bool = False
    dry_run: bool = False
    allow_live: bool = False
    concurrency: int = 1
    video_concurrency: Optional[int] = None  # defaults to `concurrency` when unset
    health_check: bool = True  # probe endpoints + prefer a working one before running
    text_engine_kind: str = "gpt"
    video_engine_kind: str = "gemini"
    text_model: Optional[str] = None
    video_model: Optional[str] = None
    temperature: Optional[float] = None  # None -> engine default (0.3)
    resume_from: Optional[Any] = None  # prior run dir to resume (reuse its checkpoint)
    run: Optional[ExperimentRun] = field(default=None, repr=False)

    # -- matching --------------------------------------------------------------
    def _human_records(self) -> dict[str, Any]:
        recs = load_human_annotations(models=[self.model], projects=self.projects)
        use_cases = {r.project: use_case_for(r.project) for r in recs}
        return aggregate_annotations(recs, use_case_lookup=use_cases)

    def load_items(self) -> list[str]:
        human = self._human_records()
        loader = PeanutEvalLoader(model=self.model, projects=self.projects)
        available = set(loader.list_items())
        matched = sorted(set(human) & available)
        if self.limit is not None:
            matched = matched[: self.limit]
        return matched

    # -- main ------------------------------------------------------------------
    def execute(self) -> dict[str, Any]:  # noqa: C901 - linear orchestration
        if self.run is not None:
            run = self.run
        elif self.resume_from is not None:
            run = make_exp_run(run_dir=Path(self.resume_from))
        else:
            run = make_exp_run()
        self.run = run
        log = run.logger
        if self.resume_from is not None:
            log.info("Resuming run from %s", run.run_dir)

        human = self._human_records()
        loader = PeanutEvalLoader(model=self.model, projects=self.projects)
        items = self.load_items()
        log.info("Matched %d human-labeled items for model=%s", len(items), self.model)

        cfg = {
            "benchmark": "human_gap",
            "model": self.model,
            "projects": self.projects or "ALL",
            "judges": self.judges or "M1..M6",
            "limit": self.limit,
            "skip_video": self.skip_video,
            "dry_run": self.dry_run,
            "judge_video_model": self.video_model or config.DEFAULT_VIDEO_MODEL,
            "judge_text_model": self.text_model or config.DEFAULT_TEXT_MODEL,
            "calibration_version": "none",
            "n_matched_items": len(items),
            "concurrency": self.concurrency,
            "video_concurrency": self.video_concurrency or self.concurrency,
            "temperature": self.temperature,
            "skip_video": self.skip_video,
        }
        if not (self.resume_from and (run.run_dir / "run_config.json").is_file()):
            run.save_config(cfg)  # keep the original config when resuming

        if self.dry_run:
            return self._dry_run_report(items, loader, run, cfg)

        # Real (billable) gateway calls require explicit authorization.
        require_live(self.allow_live, context=f"Benchmark over {len(items)} item(s)")

        # Load creds once (avoids a lazy race when engines are shared across threads).
        creds = load_creds()
        # Probe endpoints and prefer a working one (skip the primary if it's down).
        if self.health_check and len(creds.default_endpoints) > 1:
            from ...lm_engine.health import reorder_creds_by_health

            reorder_creds_by_health(creds, model=self.text_model, logger=log)
        # Only pass temperature when set, so None keeps the engine default (0.3).
        temp_kw = {} if self.temperature is None else {"temperature": self.temperature}
        engines = JudgeEngines(
            text=get_engine(
                self.text_engine_kind, history=run.history, model=self.text_model,
                creds=creds, **temp_kw,
            ),
            video=get_engine(
                self.video_engine_kind, history=run.history, model=self.video_model,
                creds=creds, **temp_kw,
            ),
        )

        # Pre-load samples sequentially (cheap local file I/O) so the worker threads
        # only do network calls.
        samples = {iid: loader.load_sample(iid) for iid in items}
        # Checkpoint store in the run dir — resuming reuses already-completed judge calls.
        store = CheckpointStore(run.run_dir / "judge_results.jsonl")
        if len(store):
            log.info("Found %d checkpointed judge result(s) to reuse", len(store))
        per_item_judges, session_results = self._run_judges_concurrent(
            samples, engines, run, log, store=store
        )

        # Fail loudly if EVERY judge call ATTEMPTED THIS SESSION errored (auth/gateway down).
        # If everything was already cached (no new calls), just rebuild the outputs.
        session_errored = [r for r in session_results if r.get("error")]
        if session_results and len(session_errored) == len(session_results):
            sample_err = str(session_errored[0].get("error"))[:200]
            raise AllJudgeCallsFailed(
                f"All {len(session_results)} judge calls made this session failed "
                f"(e.g. {sample_err}). See {run.run_dir}/llm-histories.log."
            )

        aligned_rows = build_aligned_rows(items, human, per_item_judges)

        gap = self._compute_gap(aligned_rows, human, per_item_judges, cfg)
        run.write_json("gap_result.json", gap)
        _write_aligned_pairs_csv(run, aligned_rows)

        # Persist slimmed per-item judge outputs (incl. M1/M2/M4 that aren't aligned to
        # a human dimension) so any view can be rebuilt later without re-calling.
        run.write_json("judge_outputs.json", _slim_judge_outputs(per_item_judges))

        # Per-item (per-video) gap views.
        from ..per_item import (
            build_per_item_gap,
            build_per_judge_summary,
            build_per_judge_item,
            write_per_item_gap,
            write_rows_csv,
        )

        per_item_rows = build_per_item_gap(aligned_rows)
        write_per_item_gap(per_item_rows, run.run_dir / "per_item_gap.csv")
        write_rows_csv(build_per_judge_item(aligned_rows), run.run_dir / "per_judge_gap.csv")
        write_rows_csv(
            build_per_judge_summary(aligned_rows), run.run_dir / "per_judge_summary.csv"
        )
        gap["per_item"] = per_item_rows
        run.write_json("gap_result.json", gap)  # rewrite with per_item embedded
        log.info(
            "Wrote gap_result.json, aligned_pairs.csv, per_item_gap.csv, "
            "per_judge_gap.csv, per_judge_summary.csv, judge_outputs.json to %s",
            run.run_dir,
        )

        try:
            from ..report import generate_gap_report

            generate_gap_report(gap, aligned_rows, str(run.run_dir))
        except Exception as e:  # noqa: BLE001 - reporting is best-effort
            log.warning("Report generation skipped: %s", e)

        return gap

    # -- concurrent judging ----------------------------------------------------
    def _run_judges_concurrent(
        self,
        samples: dict[str, dict[str, Any]],
        engines: JudgeEngines,
        run: ExperimentRun,
        log,
        store: Optional[CheckpointStore] = None,
    ) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
        """Run (item, judge) tasks across separate text + video thread pools.

        Text and video judges have different ideal concurrency (text is cheap; video is
        bandwidth/memory-bound), so they get independent pools that run simultaneously.
        Checkpointed (item, judge) results in ``store`` are reused (not re-called); only
        successful new results are persisted, so failed calls retry on the next resume.

        Returns (per_item_judges, session_results) where session_results are the results
        of calls actually made this session (excludes cached + skipped).
        """
        selected = self.judges or ALL_JUDGES
        per_item: dict[str, dict[str, Any]] = {iid: {} for iid in samples}

        # Split tasks by modality; pre-fill skipped video judges + reuse checkpointed ones.
        text_tasks: list[tuple[str, str]] = []
        video_tasks: list[tuple[str, str]] = []
        n_cached = 0
        for iid, sample in samples.items():
            has_video = bool((sample.get("output") or {}).get("output_video_path"))
            for mid in selected:
                key = f"{iid}::{mid}"
                if store is not None and store.has(key):
                    per_item[iid][mid] = store.get(key)
                    n_cached += 1
                    continue
                if JUDGE_MODALITY[mid] == "video":
                    if self.skip_video or not has_video:
                        per_item[iid][mid] = {
                            "judge": mid, "metric_id": mid, "parsed": None, "skipped": True
                        }
                    else:
                        video_tasks.append((iid, mid))
                else:
                    text_tasks.append((iid, mid))

        total = len(text_tasks) + len(video_tasks)
        text_workers = max(1, self.concurrency)
        # video_concurrency defaults to the general concurrency when unset.
        video_workers = max(1, self.video_concurrency or self.concurrency)

        _quiet_console(log)
        log.info(
            "Running %d text + %d video tasks (conc text=%d/video=%d); reused %d cached",
            len(text_tasks), len(video_tasks), text_workers, video_workers, n_cached,
        )
        bar = _progress_bar(
            total=total, desc=f"judges (text={text_workers},video={video_workers})"
        )

        def _run_task(item_id: str, metric_id: str) -> tuple[str, str, dict[str, Any]]:
            judge = make_judge(metric_id, engines.for_metric(metric_id))
            return item_id, metric_id, judge.run(samples[item_id])

        session_results: list[dict[str, Any]] = []
        done = 0
        # Two pools open at once -> text and video run concurrently, each capped
        # at its own worker count.
        with ThreadPoolExecutor(max_workers=text_workers) as tex, \
                ThreadPoolExecutor(max_workers=video_workers) as vex:
            futs = [tex.submit(_run_task, i, m) for i, m in text_tasks]
            futs += [vex.submit(_run_task, i, m) for i, m in video_tasks]
            for fut in as_completed(futs):
                item_id, metric_id, result = fut.result()
                per_item[item_id][metric_id] = result
                session_results.append(result)
                # Checkpoint only successful calls so failures retry on resume.
                if store is not None and not result.get("error"):
                    store.put(f"{item_id}::{metric_id}", result)
                done += 1
                if bar is not None:
                    bar.set_postfix_str(f"{item_id} {metric_id}")
                    bar.update(1)
                else:
                    log.info("  [%d/%d] %s %s", done, total, item_id, metric_id)

        if bar is not None:
            bar.close()
        return per_item, session_results

    # -- gap computation -------------------------------------------------------
    def _compute_gap(
        self,
        rows: list[dict[str, Any]],
        human: dict[str, Any],
        per_item_judges: dict[str, dict[str, Any]],
        cfg: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "benchmark_id": self.run.run_id if self.run else None,
            "config": cfg,
            "n_items": len({r["item_id"] for r in rows}),
            "per_dimension": per_dimension_agreement(rows),
            "pairwise_preference_accuracy": _pairwise(human, per_item_judges),
            "calibration_error": None,
            "aligned_pairs_path": "aligned_pairs.csv",
        }

    def _dry_run_report(
        self, items: list[str], loader: PeanutEvalLoader, run: ExperimentRun, cfg: dict
    ) -> dict[str, Any]:
        selected = self.judges or ["M1", "M2", "M3", "M4", "M5", "M6"]
        from ...core.judge.registry import JUDGE_MODALITY

        video_calls = sum(1 for m in selected if JUDGE_MODALITY[m] == "video")
        text_calls = len(selected) - video_calls
        report = {
            "dry_run": True,
            "n_items": len(items),
            "items": items,
            "judges": selected,
            "estimated_calls": {
                "video_judge_calls": video_calls * len(items),
                "text_judge_calls": text_calls * len(items),
            },
            "note": "No gateway calls made. Video judge calls are the cost driver.",
        }
        run.write_json("dry_run.json", report)
        run.logger.info(
            "DRY RUN: %d items, ~%d video + %d text judge calls",
            len(items),
            video_calls * len(items),
            text_calls * len(items),
        )
        return report


def _slim_judge_outputs(
    per_item_judges: dict[str, dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    """Drop bulky raw_content/tokens; keep parsed scores + validation per (item, judge)."""
    out: dict[str, dict[str, Any]] = {}
    for iid, judges in per_item_judges.items():
        out[iid] = {}
        for mid, res in judges.items():
            out[iid][mid] = {
                "parsed": res.get("parsed"),
                "valid": res.get("valid"),
                "validation_flags": res.get("validation_flags"),
                "skipped": res.get("skipped", False),
                "error": res.get("error"),
            }
    return out


def _progress_bar(*, total: int, desc: str):
    """Return a tqdm bar, or None if tqdm is unavailable (e.g. in tests)."""
    try:
        from tqdm.auto import tqdm
    except ImportError:
        return None
    return tqdm(total=total, desc=desc, unit="item", dynamic_ncols=True)


def _quiet_console(logger) -> None:
    """Raise console StreamHandlers to WARNING so they don't clobber the bar.

    File handlers (run.log) keep full INFO detail.
    """
    import logging

    for h in logger.handlers:
        if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler):
            h.setLevel(logging.WARNING)


def _pairwise(
    human: dict[str, Any], per_item_judges: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """Pairwise preference accuracy.

    Requires two competing outputs per cell with judge-derived overall scores. In the
    peanut-only v1 there is one output per item, so this reports n_pairs=0; the field
    is kept so multi-model follow-ups light up automatically.
    """
    # derive judge overalls (available for follow-ups that evaluate multiple outputs)
    _ = {iid: derive_overall(jr) for iid, jr in per_item_judges.items()}
    return {
        "overall": None,
        "by_category": {},
        "n_pairs": 0,
        "note": "Pairwise needs >=2 outputs per cell; not available in peanut-only v1.",
    }


def _write_aligned_pairs_csv(run: ExperimentRun, rows: list[dict[str, Any]]) -> None:
    import csv

    path = run.run_dir / "aligned_pairs.csv"
    fields = ["item_id", "project", "model", "use_case", "dimension", "human", "judge_raw"]
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k) for k in fields})
