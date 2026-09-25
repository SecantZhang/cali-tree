#!/usr/bin/env python3
"""Run the resumable AURORA individual prompt-repair experiment.

The default is a no-cost preparation/dry run.  ``--live`` is required for the
``baseline``, ``repair``, or ``all`` phases to make gateway calls.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Optional

from vejudge import config
from vejudge.checkpoint import CheckpointStore
from vejudge.core.calibration.textgrad_adapter import textgrad_update
from vejudge.database.dl_aurora import AuroraBenchLoader
from vejudge.experiments.aurora_prompt_repair import (
    LABELS,
    baseline_summary,
    build_balanced_sample,
    candidate_rank,
    lint_candidate,
    optimizer_feedback,
    parse_judgment,
    prompt_diff,
    prompt_digest,
    repair_reason,
    robustness_stats,
    select_anchors,
)
from vejudge.experiments.prompt_repair_report import write_html_report
from vejudge.lm_engine import get_engine, load_creds
from vejudge.lm_engine import openai_compat
from vejudge.lm_engine.gate import require_live
from vejudge.logging.exp_logger import make_exp_run
from tqdm.auto import tqdm

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROMPT_PATH = (
    REPO_ROOT
    / "vejudge"
    / "core"
    / "prompts"
    / "templates"
    / "calitree_v2"
    / "initial_rubric.txt"
)
DEFAULT_GEPA_PYTHON = REPO_ROOT / ".venv-gepa" / "bin" / "python"
GEPA_WORKER = REPO_ROOT / "run" / "aurora_prompt_repair" / "gepa_worker.py"
PRICING_SOURCE = "https://developers.openai.com/api/docs/models/gpt-5.4-mini"


@lru_cache(maxsize=512)
def _cached_image_part(path: str) -> dict[str, Any]:
    """Avoid re-reading/base64-encoding the same image for every repeat."""
    return openai_compat.image_part(path)


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    temporary.replace(path)


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    temporary.replace(path)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _case_slug(item_id: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9_.-]+", "-", item_id).strip("-")[:72]
    return f"{clean}-{prompt_digest(item_id)[:8]}"


class LiveJudge:
    """Thread-safe, checkpointed multimodal judge with explicit call identities."""

    def __init__(
        self,
        *,
        model: str,
        checkpoint: CheckpointStore,
        history: Any,
        max_tokens: int,
        timeout: int,
    ) -> None:
        self.model = model
        self.checkpoint = checkpoint
        self.history = history
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.creds = load_creds(model=model)

    def judge(
        self,
        case: dict[str, Any],
        prompt: str,
        *,
        temperature: float,
        call_id: str,
    ) -> dict[str, Any]:
        cache_key = (
            f"aurora-repair::judge::{call_id}::{prompt_digest(prompt)}::"
            f"t={temperature:g}"
        )
        if self.checkpoint.has(cache_key):
            cached = dict(self.checkpoint.get(cache_key))
            cached["checkpoint_hit"] = True
            return cached

        user_text = (
            f"Instruction: {case['instruction']}\n"
            "The first image is SOURCE; the second is EDITED."
        )
        media = [
            _cached_image_part(str(case["source_image_path"])),
            _cached_image_part(str(case["edited_image_path"])),
        ]
        messages = [
            {"role": "system", "content": prompt},
            {
                "role": "user",
                "content": [openai_compat.text_part(user_text), *media],
            },
        ]
        try:
            result = openai_compat.chat_completion(
                provider=self.creds.provider, endpoints=self.creds.endpoints,
                token=self.creds.token,
                model=self.model,
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=temperature,
                timeout=self.timeout,
                max_retries=4,
            )
        except Exception as exc:  # unsuccessful calls remain absent so resume retries them
            error = f"{type(exc).__name__}: {exc}"
            self.history.record(
                engine="gpt",
                model=self.model,
                prompt=prompt + "\n\n" + user_text,
                response=None,
                media_inputs=media,
                error=error,
                extra={"call_id": call_id, "temperature": temperature},
            )
            return {
                "call_id": call_id,
                "label": "",
                "rationale": "",
                "valid": False,
                "error": error,
                "checkpoint_hit": False,
            }

        content = str(result.content or "")
        parsed = parse_judgment(content)
        row = {
            "call_id": call_id,
            **parsed,
            "error": None,
            "raw_content": content,
            "requested_model": self.model,
            "model": result.model,
            "temperature": temperature,
            "prompt_tokens": result.prompt_tokens,
            "completion_tokens": result.completion_tokens,
            "total_tokens": result.total_tokens,
            "latency_seconds": result.latency_s,
            "endpoint_host": result.endpoint_host,
            "checkpoint_hit": False,
        }
        self.history.record(
            engine="gpt",
            model=result.model,
            prompt=prompt + "\n\n" + user_text,
            response=content,
            media_inputs=media,
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            total_tokens=result.total_tokens,
            latency_s=result.latency_s,
            endpoint=result.endpoint_host,
            extra={"call_id": call_id, "temperature": temperature},
        )
        # A completed HTTP response is a completed repeat, even when its contract is invalid.
        self.checkpoint.put(cache_key, row)
        return row


class TextGradProposer:
    def __init__(
        self,
        *,
        model: str,
        checkpoint: CheckpointStore,
        history: Any,
        run_dir: Path,
        max_tokens: int,
        timeout: int,
    ) -> None:
        self.checkpoint = checkpoint
        self.run_dir = run_dir
        self.engine = get_engine(
            "gpt",
            model=model,
            creds=load_creds(model=model),
            history=history,
            max_tokens=max_tokens,
            temperature=0.0,
            timeout=timeout,
        )
        # TextGrad mutates module-global logging state in 0.1.8.
        self._lock = threading.Lock()

    def propose(
        self, *, item_id: str, round_index: int, prompt: str, feedback: str
    ) -> tuple[str, dict[str, Any]]:
        key = (
            f"aurora-repair::optimizer::textgrad::{item_id}::{round_index}::"
            f"{prompt_digest(prompt + feedback)}"
        )
        if self.checkpoint.has(key):
            payload = dict(self.checkpoint.get(key))
            payload["checkpoint_hit"] = True
            return str(payload["prompt"]), payload
        usage: list[dict[str, Any]] = []
        with self._lock:
            updated = textgrad_update(
                prompt,
                feedback,
                engine=self.engine,
                usage_cb=lambda result: usage.append(dict(result)),
                log_dir=self.run_dir / "textgrad",
            )
        payload = {
            "prompt": updated,
            "feedback": feedback,
            "usage": usage,
            "unchanged": updated == prompt,
            "checkpoint_hit": False,
        }
        self.checkpoint.put(key, payload)
        return updated, payload


class GepaProposer:
    """Invoke one isolated GEPA proposal through a one-line JSON protocol."""

    def __init__(
        self,
        *,
        model: str,
        checkpoint: CheckpointStore,
        python_path: Path,
        run_dir: Path,
        timeout: int,
    ) -> None:
        self.model = model
        self.checkpoint = checkpoint
        self.python_path = python_path
        self.run_dir = run_dir
        self.timeout = timeout
        self.creds = load_creds(model=model)

    def validate(self) -> None:
        if not self.python_path.is_file():
            raise RuntimeError(
                f"GEPA Python not found at {self.python_path}; run "
                "./run/aurora_prompt_repair/setup_gepa_venv.sh"
            )
        if not GEPA_WORKER.is_file():
            raise RuntimeError(f"GEPA worker not found at {GEPA_WORKER}")

    def propose(
        self,
        *,
        item_id: str,
        round_index: int,
        prompt: str,
        feedback: str,
        focal: dict[str, Any],
        anchors: list[dict[str, Any]],
        seed: int,
    ) -> tuple[str, dict[str, Any]]:
        key = (
            f"aurora-repair::optimizer::gepa::{item_id}::{round_index}::"
            f"{prompt_digest(prompt + feedback)}"
        )
        if self.checkpoint.has(key):
            payload = dict(self.checkpoint.get(key))
            payload["checkpoint_hit"] = True
            return str(payload["prompt"]), payload
        request = {
            "request_id": f"{_case_slug(item_id)}-round-{round_index}",
            "model": self.model,
            "seed": seed + round_index,
            "prompt": prompt,
            "feedback": feedback,
            "focal": focal,
            "anchors": anchors,
            "run_dir": str(
                self.run_dir / "gepa" / _case_slug(item_id) / f"round-{round_index}"
            ),
            "timeout": self.timeout,
        }
        environment = os.environ.copy()
        environment.update(
            {
                "AURORA_GEPA_TOKEN": self.creds.token,
                "AURORA_GEPA_PROVIDER": self.creds.provider,
                "AURORA_GEPA_ENDPOINTS": json.dumps(self.creds.endpoints),
            }
        )
        started = time.time()
        try:
            completed = subprocess.run(
                [str(self.python_path), str(GEPA_WORKER)],
                input=json.dumps(request) + "\n",
                text=True,
                capture_output=True,
                check=False,
                timeout=max(900, self.timeout * 20),
                env=environment,
            )
            lines = [line for line in completed.stdout.splitlines() if line.strip()]
            if not lines:
                raise RuntimeError(
                    f"GEPA worker exit={completed.returncode}: "
                    f"{completed.stderr[-2000:]}"
                )
            response = json.loads(lines[-1])
            if response.get("error"):
                raise RuntimeError(
                    str(response["error"]) + "\n" + str(response.get("traceback") or "")
                )
            if completed.returncode:
                raise RuntimeError(
                    f"GEPA worker exit={completed.returncode}: {completed.stderr[-2000:]}"
                )
            updated = str(response.get("prompt") or prompt)
            payload = {
                "prompt": updated,
                "feedback": feedback,
                "lineage": response.get("lineage") or {},
                "usage": response.get("usage") or {},
                "worker_stderr_tail": completed.stderr[-4000:],
                "wall_clock_seconds": time.time() - started,
                "unchanged": updated == prompt,
                "checkpoint_hit": False,
            }
        except Exception as exc:  # a failed proposal consumes a recorded outer round
            updated = prompt
            payload = {
                "prompt": prompt,
                "feedback": feedback,
                "lineage": {},
                "usage": {},
                "wall_clock_seconds": time.time() - started,
                "unchanged": True,
                "error": f"{type(exc).__name__}: {exc}",
                "checkpoint_hit": False,
            }
        self.checkpoint.put(key, payload)
        return updated, payload


class Experiment:
    def __init__(self, args: argparse.Namespace, run_dir: Path) -> None:
        self.args = args
        self.run_dir = run_dir
        self.run = make_exp_run(run_id=run_dir.name, run_dir=run_dir)
        self.checkpoint = CheckpointStore(run_dir / "checkpoints.jsonl")
        self.prompt = args.prompt_path.read_text(encoding="utf-8")
        self.judge: Optional[LiveJudge] = None
        self.textgrad: Optional[TextGradProposer] = None
        self.gepa: Optional[GepaProposer] = None
        self._active_progress: Optional[Any] = None
        self._progress_lock = threading.Lock()

    def close(self) -> None:
        if self._active_progress is not None:
            self._active_progress.close()
            self._active_progress = None
        self.run.close()

    def _progress(self, *, total: int, description: str, unit: str) -> Any:
        return tqdm(
            total=total,
            desc=description,
            unit=unit,
            dynamic_ncols=True,
            position=0,
            leave=True,
            disable=bool(getattr(self.args, "no_progress", False)),
        )

    def _progress_stage(
        self, method: str, item_id: str, round_index: int, stage: str
    ) -> None:
        bar = self._active_progress
        if bar is None:
            return
        short_id = item_id if len(item_id) <= 34 else item_id[:31] + "..."
        with self._progress_lock:
            bar.set_postfix_str(
                f"{method} | {short_id} | round {round_index}/{self.args.max_rounds} | {stage}",
                refresh=True,
            )

    def configure_live(self) -> None:
        require_live(self.args.live, context="AURORA prompt-repair experiment")
        self.judge = LiveJudge(
            model=self.args.model,
            checkpoint=self.checkpoint,
            history=self.run.history,
            max_tokens=self.args.max_tokens,
            timeout=self.args.timeout,
        )

    def configure_optimizers(self) -> None:
        if self.judge is None:
            self.configure_live()
        if "textgrad" in self.args.methods:
            self.textgrad = TextGradProposer(
                model=self.args.model,
                checkpoint=self.checkpoint,
                history=self.run.history,
                run_dir=self.run_dir,
                max_tokens=self.args.optimizer_max_tokens,
                timeout=self.args.timeout,
            )
        if "gepa" in self.args.methods:
            self.gepa = GepaProposer(
                model=self.args.model,
                checkpoint=self.checkpoint,
                python_path=self.args.gepa_python,
                run_dir=self.run_dir,
                timeout=self.args.timeout,
            )
            self.gepa.validate()

    def sample(self) -> dict[str, Any]:
        loader = AuroraBenchLoader(root=self.args.dataset_root, repeat=3)
        samples, labels = loader.load_all()
        manifest = build_balanced_sample(
            samples, labels, size=self.args.sample_size, seed=self.args.seed
        )
        _atomic_json(self.run_dir / "sample_manifest.json", {
            key: value for key, value in manifest.items() if key != "clean_holdout"
        })
        _atomic_json(
            self.run_dir / "clean_holdout_manifest.json",
            {
                "schema_version": 1,
                "dataset": "AURORA-Bench",
                "excluded_selected_task_uids": manifest["selected_task_uids"],
                "cases": manifest["clean_holdout"],
                "counts": manifest["counts"]["clean_holdout"],
            },
        )
        self.run.logger.info(
            "sampled %d cases; clean holdout has %d cases",
            len(manifest["cases"]),
            len(manifest["clean_holdout"]),
        )
        return manifest

    def _manifest(self) -> dict[str, Any]:
        path = self.run_dir / "sample_manifest.json"
        if not path.is_file():
            return self.sample()
        return _read_json(path)

    def _write_anchors(
        self,
        rows: list[dict[str, Any]],
        *,
        exclude_item_ids: Optional[set[str]] = None,
    ) -> list[dict[str, Any]]:
        anchors = select_anchors(
            rows,
            per_label=2,
            seed=self.args.seed,
            allow_fallback=True,
            exclude_item_ids=exclude_item_ids,
        )
        degraded = any(
            (row.get("anchor_selection") or {}).get("tier") != "robust"
            for row in anchors
        )
        if exclude_item_ids is None:
            _atomic_json(
                self.run_dir / "anchors.json",
                {
                    "consensus_proxy": (
                        "absolute distance of aggregate score from label prototype"
                    ),
                    "raw_rater_votes_available": False,
                    "selection_policy": (
                        "Prefer robust initially-correct cases; when a label has fewer "
                        "than two, fill with the highest-repeat-hit initially-correct "
                        "distinct cases."
                    ),
                    "degraded_guard": degraded,
                    "cases": [
                        {
                            key: row[key]
                            for key in (
                                "item_id", "task_uid", "task", "model", "instruction",
                                "source_image_path", "edited_image_path", "human_score",
                                "target_score", "target_label", "robustness",
                                "anchor_selection",
                            )
                        }
                        for row in anchors
                    ],
                },
            )
        if degraded:
            details = [
                f"{row['target_label']}:{row['item_id']}="
                f"{row['anchor_selection']['baseline_target_hits']}/{self.args.repeats}"
                for row in anchors
                if row["anchor_selection"]["tier"] != "robust"
            ]
            self.run.logger.warning(
                "anchor guard uses best-available nonrobust fallback(s): %s",
                ", ".join(details),
            )
        return anchors

    def baseline(self) -> list[dict[str, Any]]:
        if self.judge is None:
            raise RuntimeError("live judge is not configured")
        cases = self._manifest()["cases"]
        work: list[tuple[dict[str, Any], float, str, str]] = []
        for case in cases:
            work.append((case, 0.0, f"baseline:init:{case['item_id']}", "initial"))
            for repeat_index in range(self.args.repeats):
                work.append((
                    case,
                    self.args.repeat_temperature,
                    f"baseline:repeat:{case['item_id']}:{repeat_index:02d}",
                    f"repeat:{repeat_index}",
                ))
        results: dict[str, dict[str, Any]] = {}
        progress = self._progress(
            total=len(work), description="AURORA baseline", unit="call"
        )
        try:
            with ThreadPoolExecutor(max_workers=self.args.concurrency) as pool:
                futures = {
                    pool.submit(
                        self.judge.judge,
                        case,
                        self.prompt,
                        temperature=temperature,
                        call_id=call_id,
                    ): key
                    for case, temperature, call_id, key in work
                }
                for future in as_completed(futures):
                    result = future.result()
                    results[result["call_id"]] = result
                    progress.set_postfix_str(result["call_id"][-42:], refresh=False)
                    progress.update(1)
        finally:
            progress.close()

        rows: list[dict[str, Any]] = []
        for case in cases:
            initial = results[f"baseline:init:{case['item_id']}"]
            repeats = [
                results[f"baseline:repeat:{case['item_id']}:{index:02d}"]
                for index in range(self.args.repeats)
            ]
            rows.append({
                **case,
                "initial": initial,
                "repeats": repeats,
                "robustness": robustness_stats(
                    repeats,
                    case["target_label"],
                    required=self.args.robust_min_correct,
                ),
            })
        _write_jsonl(self.run_dir / "baseline_predictions.jsonl", rows)
        summary = baseline_summary(
            rows, required_correct=self.args.robust_min_correct
        )
        _atomic_json(self.run_dir / "baseline_metrics.json", summary)
        try:
            self._write_anchors(rows)
        except ValueError as exc:
            _atomic_json(
                self.run_dir / "anchors.json",
                {
                    "consensus_proxy": (
                        "absolute distance of aggregate score from label prototype"
                    ),
                    "raw_rater_votes_available": False,
                    "error": str(exc),
                    "cases": [],
                },
            )
            self.run.logger.warning("%s", exc)
            return rows
        self.run.logger.info(
            "baseline accuracy=%s robust=%d/%d repair_pool=%d",
            summary["accuracy"], summary["robust_count"], len(rows), summary["repair_pool_size"],
        )
        return rows

    def _baseline_rows(self) -> list[dict[str, Any]]:
        path = self.run_dir / "baseline_predictions.jsonl"
        if not path.is_file():
            raise RuntimeError("baseline_predictions.jsonl is missing; run the baseline phase")
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]

    def _anchors(self) -> list[dict[str, Any]]:
        path = self.run_dir / "anchors.json"
        payload = _read_json(path) if path.is_file() else {}
        anchors = payload.get("cases") or []
        if payload.get("error") or len(anchors) != 6:
            anchors = self._write_anchors(self._baseline_rows())
        return anchors

    def _repeat_candidate(
        self, case: dict[str, Any], prompt: str, method: str, round_index: int
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        assert self.judge is not None
        predictions = []
        for index in range(self.args.repeats):
            self._progress_stage(
                method,
                case["item_id"],
                round_index,
                f"robustness repeat {index + 1}/{self.args.repeats}",
            )
            predictions.append(self.judge.judge(
                case,
                prompt,
                temperature=self.args.repeat_temperature,
                call_id=(
                    f"repair:{method}:{case['item_id']}:{round_index}:repeat:{index:02d}"
                ),
            ))
        return predictions, robustness_stats(
            predictions,
            case["target_label"],
            required=self.args.robust_min_correct,
        )

    def _anchor_check(
        self,
        prompt: str,
        anchors: list[dict[str, Any]],
        method: str,
        focal: dict[str, Any],
        round_index: int,
    ) -> list[dict[str, Any]]:
        assert self.judge is not None
        output = []
        for anchor_index, anchor in enumerate(anchors):
            self._progress_stage(
                method,
                focal["item_id"],
                round_index,
                f"anchor guard {anchor_index + 1}/{len(anchors)}",
            )
            prediction = self.judge.judge(
                anchor,
                prompt,
                temperature=self.args.repeat_temperature,
                call_id=(
                    f"repair:{method}:{focal['item_id']}:{round_index}:"
                    f"anchor:{anchor_index}:{anchor['item_id']}"
                ),
            )
            output.append({
                "item_id": anchor["item_id"],
                "target_label": anchor["target_label"],
                "anchor_selection": anchor.get("anchor_selection") or {},
                "prediction": prediction,
                "correct": prediction.get("label") == anchor["target_label"],
            })
        return output

    def _proposal(
        self,
        method: str,
        case: dict[str, Any],
        anchors: list[dict[str, Any]],
        round_index: int,
        parent_prompt: str,
        feedback: str,
    ) -> tuple[str, dict[str, Any]]:
        if method == "textgrad":
            assert self.textgrad is not None
            return self.textgrad.propose(
                item_id=case["item_id"], round_index=round_index,
                prompt=parent_prompt, feedback=feedback,
            )
        if method == "gepa":
            assert self.gepa is not None
            return self.gepa.propose(
                item_id=case["item_id"], round_index=round_index,
                prompt=parent_prompt, feedback=feedback, focal=case,
                anchors=anchors, seed=self.args.seed,
            )
        raise ValueError(f"unknown optimizer method {method!r}")

    def _repair_track(
        self,
        case: dict[str, Any],
        baseline: dict[str, Any],
        anchors: list[dict[str, Any]],
        method: str,
    ) -> dict[str, Any]:
        slug = _case_slug(case["item_id"])
        prompt_dir = self.run_dir / "prompts" / slug / method
        prompt_dir.mkdir(parents=True, exist_ok=True)
        seed_path = prompt_dir / "round-00-seed.txt"
        if not seed_path.exists():
            seed_path.write_text(self.prompt, encoding="utf-8")

        best_prompt = self.prompt
        focal_only = bool(getattr(self.args, "focal_only", False))
        best_rank = candidate_rank(
            target_hits=int(baseline["robustness"]["target_hits"]),
            anchor_correct=0 if focal_only else len(anchors),
            screen_correct=baseline["initial"].get("label") == case["target_label"],
            prompt=self.prompt,
        )
        rounds: list[dict[str, Any]] = []
        accepted = False

        for round_index in range(1, self.args.max_rounds + 1):
            self._progress_stage(method, case["item_id"], round_index, "restore/checkpoint")
            round_key = f"aurora-repair::round::{method}::{case['item_id']}::{round_index}"
            if self.checkpoint.has(round_key):
                row = dict(self.checkpoint.get(round_key))
                rounds.append(row)
                rank = tuple(
                    int(value)
                    for value in (
                        row.get("rank")
                        or (0, 0, 0, -len(row.get("candidate_prompt") or ""))
                    )
                )
                if rank > best_rank:
                    best_rank = rank
                    best_prompt = str(row["candidate_prompt"])
                if row.get("accepted"):
                    best_rank = rank
                    best_prompt = str(row["candidate_prompt"])
                    accepted = True
                    break
                continue

            previous = rounds[-1] if rounds else None
            feedback = optimizer_feedback(
                case,
                baseline,
                previous,
                include_anchor_feedback=not focal_only,
            )
            parent_prompt = best_prompt
            self._progress_stage(method, case["item_id"], round_index, "optimize prompt")
            candidate, optimizer = self._proposal(
                method, case, anchors, round_index, parent_prompt, feedback
            )
            lint = lint_candidate(candidate, case)
            screen: dict[str, Any] = {
                "label": "", "rationale": "", "valid": False,
                "error": "candidate_lint_failed",
            }
            repeats: list[dict[str, Any]] = []
            robust = robustness_stats([], case["target_label"], required=self.args.robust_min_correct)
            anchor_results: list[dict[str, Any]] = []
            if lint["valid"]:
                assert self.judge is not None
                self._progress_stage(method, case["item_id"], round_index, "screen focal case")
                screen = self.judge.judge(
                    case,
                    candidate,
                    temperature=0.0,
                    call_id=f"repair:{method}:{case['item_id']}:{round_index}:screen",
                )
                if screen.get("label") == case["target_label"]:
                    self._progress_stage(
                        method, case["item_id"], round_index,
                        f"robustness repeats 0/{self.args.repeats}",
                    )
                    repeats, robust = self._repeat_candidate(
                        case, candidate, method, round_index
                    )
                    if robust["robust"] and not focal_only:
                        self._progress_stage(
                            method, case["item_id"], round_index, "anchor guard 0/6"
                        )
                        anchor_results = self._anchor_check(
                            candidate, anchors, method, case, round_index
                        )
            anchor_correct = sum(row["correct"] for row in anchor_results)
            accepted = bool(
                robust["robust"]
                and (focal_only or anchor_correct == len(anchors))
            )
            rank = candidate_rank(
                target_hits=int(robust["target_hits"]),
                anchor_correct=anchor_correct,
                screen_correct=screen.get("label") == case["target_label"],
                prompt=candidate,
            )
            candidate_path = prompt_dir / f"round-{round_index:02d}.txt"
            diff_path = prompt_dir / f"round-{round_index:02d}.diff"
            candidate_path.write_text(candidate, encoding="utf-8")
            diff_path.write_text(prompt_diff(parent_prompt, candidate), encoding="utf-8")
            row = {
                "round": round_index,
                "parent_prompt_sha256": prompt_digest(parent_prompt),
                "candidate_prompt_sha256": prompt_digest(candidate),
                "candidate_prompt": candidate,
                "candidate_prompt_path": str(candidate_path),
                "prompt_diff_path": str(diff_path),
                "feedback": feedback,
                "optimizer": optimizer,
                "lint": lint,
                "screen": screen,
                "repeats": repeats,
                "robustness": robust,
                "anchors": anchor_results,
                "accepted": accepted,
                "rank": list(rank),
            }
            self.checkpoint.put(round_key, row)
            rounds.append(row)
            if rank > best_rank:
                best_rank = rank
                best_prompt = candidate
            if accepted:
                best_rank = rank
                best_prompt = candidate
                break

        final_path = prompt_dir / "accepted.txt" if accepted else prompt_dir / "best.txt"
        final_path.write_text(best_prompt, encoding="utf-8")
        return {
            "item_id": case["item_id"],
            "task_uid": case["task_uid"],
            "task": case["task"],
            "model": case["model"],
            "human_score": case["human_score"],
            "target_label": case["target_label"],
            "repair_reason": repair_reason(baseline),
            "method": method,
            "acceptance_mode": "focal_only" if focal_only else "anchor_guard",
            "anchor_guard_degraded": any(
                (row.get("anchor_selection") or {}).get("tier") != "robust"
                for row in anchors
            ),
            "seed_prompt_sha256": prompt_digest(self.prompt),
            "initial": baseline["initial"],
            "baseline_robustness": baseline["robustness"],
            "rounds": rounds,
            "accepted": accepted,
            "stop_reason": (
                "accepted_focal_robust"
                if accepted and focal_only
                else "accepted_robust_with_anchors"
                if accepted
                else "max_rounds_exhausted"
            ),
            "best_prompt_path": str(final_path),
            "best_prompt_sha256": prompt_digest(best_prompt),
            "best_rank": list(best_rank),
        }

    def repair(self) -> list[dict[str, Any]]:
        rows = self._baseline_rows()
        baseline_by_id = {row["item_id"]: row for row in rows}
        case_fields = (
            "item_id", "task_uid", "task", "model", "instruction",
            "source_image_path", "edited_image_path", "human_score",
            "target_score", "target_label", "source_split",
        )
        cases = [
            {key: row[key] for key in case_fields if key in row}
            for row in rows
            if repair_reason(row)
        ]
        focal_only = bool(getattr(self.args, "focal_only", False))
        primary_anchors = [] if focal_only else self._anchors()
        # A best-available fallback is itself unstable and therefore belongs to the
        # repair pool. For its own track, substitute the next ranked distinct case so
        # the focal example never acts as its own generality guard.
        anchors_by_case = {
            case["item_id"]: (
                []
                if focal_only
                else
                self._write_anchors(rows, exclude_item_ids={case["item_id"]})
                if any(
                    anchor["item_id"] == case["item_id"]
                    for anchor in primary_anchors
                )
                else primary_anchors
            )
            for case in cases
        }
        jobs = [
            (case, method, anchors_by_case[case["item_id"]])
            for case in cases
            for method in self.args.methods
        ]
        traces: list[dict[str, Any]] = []
        progress = self._progress(
            total=len(jobs), description="AURORA repair", unit="track"
        )
        self._active_progress = progress
        try:
            with ThreadPoolExecutor(max_workers=self.args.concurrency) as pool:
                futures = {
                    pool.submit(
                        self._repair_track,
                        case,
                        baseline_by_id[case["item_id"]],
                        case_anchors,
                        method,
                    ): (case["item_id"], method)
                    for case, method, case_anchors in jobs
                }
                for future in as_completed(futures):
                    item_id, method = futures[future]
                    try:
                        trace = future.result()
                    except Exception as exc:
                        trace = {
                            "item_id": item_id,
                            "method": method,
                            "accepted": False,
                            "rounds": [],
                            "stop_reason": "track_error",
                            "error": f"{type(exc).__name__}: {exc}",
                        }
                    traces.append(trace)
                    with self._progress_lock:
                        progress.set_postfix_str(
                            f"{method} | {item_id[:34]} | {trace['stop_reason']}",
                            refresh=False,
                        )
                        progress.update(1)
                    self.run.logger.info(
                        "repair %s %s: %s", item_id, method, trace["stop_reason"]
                    )
        finally:
            with self._progress_lock:
                progress.close()
                self._active_progress = None
        traces.sort(key=lambda row: (row["item_id"], row["method"]))
        _write_jsonl(self.run_dir / "repair_traces.jsonl", traces)
        return traces

    def report(self) -> dict[str, Any]:
        baseline_rows = self._baseline_rows()
        trace_path = self.run_dir / "repair_traces.jsonl"
        traces = (
            [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines() if line]
            if trace_path.is_file()
            else []
        )
        baseline = baseline_summary(
            baseline_rows, required_correct=self.args.robust_min_correct
        )
        method_summary: dict[str, Any] = {}
        for method in self.args.methods:
            selected = [row for row in traces if row.get("method") == method]
            accepted = [row for row in selected if row.get("accepted")]
            method_summary[method] = {
                "eligible": len(selected),
                "accepted": len(accepted),
                "repair_rate": len(accepted) / len(selected) if selected else None,
                "by_label": {
                    label: {
                        "eligible": sum(row.get("target_label") == label for row in selected),
                        "accepted": sum(
                            row.get("target_label") == label and row.get("accepted")
                            for row in selected
                        ),
                    }
                    for label in LABELS
                },
                "stop_reasons": _counts(row.get("stop_reason") for row in selected),
                "rounds_attempted": sum(len(row.get("rounds") or []) for row in selected),
            }
        usage = _collect_usage(self.checkpoint)
        estimated_cost = (
            usage["prompt_tokens"] * self.args.input_cost_per_million
            + usage["completion_tokens"] * self.args.output_cost_per_million
        ) / 1_000_000
        summary = {
            "schema_version": 1,
            "experiment": "aurora_individual_prompt_repair",
            "model": self.args.model,
            "acceptance_mode": (
                "focal_only" if getattr(self.args, "focal_only", False) else "anchor_guard"
            ),
            "robust_min_correct": self.args.robust_min_correct,
            "seed_prompt_sha256": prompt_digest(self.prompt),
            "baseline": baseline,
            "repair": method_summary,
            "usage": usage,
            "estimated_cost_usd": estimated_cost,
            "pricing": {
                "input_usd_per_million_tokens": self.args.input_cost_per_million,
                "output_usd_per_million_tokens": self.args.output_cost_per_million,
                "source": PRICING_SOURCE,
                "snapshot_date": "2026-09-09",
                "note": "Estimate excludes unreported cache discounts and provider markups.",
            },
        }
        _atomic_json(self.run_dir / "summary.json", summary)
        self._write_summary_csv(traces)
        self._write_markdown_reports(baseline_rows, traces, summary)
        write_html_report(self.run_dir)
        return summary

    def _write_summary_csv(self, traces: list[dict[str, Any]]) -> None:
        path = self.run_dir / "summary.csv"
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=[
                "item_id", "method", "target_label", "repair_reason", "accepted",
                "stop_reason", "rounds", "best_target_hits", "best_anchor_correct",
                "best_prompt_path",
            ])
            writer.writeheader()
            for row in traces:
                best_rank = row.get("best_rank") or [0, 0, 0, 0]
                writer.writerow({
                    "item_id": row.get("item_id"),
                    "method": row.get("method"),
                    "target_label": row.get("target_label"),
                    "repair_reason": row.get("repair_reason"),
                    "accepted": row.get("accepted"),
                    "stop_reason": row.get("stop_reason"),
                    "rounds": len(row.get("rounds") or []),
                    "best_target_hits": best_rank[0],
                    "best_anchor_correct": best_rank[1],
                    "best_prompt_path": row.get("best_prompt_path"),
                })

    def _write_markdown_reports(
        self,
        baseline_rows: list[dict[str, Any]],
        traces: list[dict[str, Any]],
        summary: dict[str, Any],
    ) -> None:
        repair_dir = self.run_dir / "case_reports"
        repair_dir.mkdir(parents=True, exist_ok=True)
        traces_by_id: dict[str, list[dict[str, Any]]] = {}
        for trace in traces:
            traces_by_id.setdefault(str(trace["item_id"]), []).append(trace)
        for baseline in baseline_rows:
            if baseline["item_id"] not in traces_by_id:
                continue
            lines = [
                f"# {baseline['item_id']}", "",
                f"- Target: `{baseline['target_label']}` (aggregate score {baseline['human_score']})",
                f"- Initial: `{baseline['initial'].get('label') or 'invalid'}`",
                f"- Repair reason: `{repair_reason(baseline)}`",
                f"- Baseline repeats: `{baseline['robustness']['label_distribution']}`; "
                f"target hits {baseline['robustness']['target_hits']}/{baseline['robustness']['n']}",
                "", "## Initial rationale", "", baseline["initial"].get("rationale") or "(none)",
            ]
            for trace in sorted(traces_by_id[baseline["item_id"]], key=lambda row: row["method"]):
                lines.extend([
                    "", f"## {trace['method']}", "", f"Stop: `{trace['stop_reason']}`",
                    f"Final prompt: `{trace.get('best_prompt_path') or '(unavailable)'}`",
                ])
                for round_row in trace.get("rounds") or []:
                    robust = round_row.get("robustness") or {}
                    diff_text = ""
                    diff_path = Path(str(round_row.get("prompt_diff_path") or ""))
                    if diff_path.is_file():
                        diff_text = diff_path.read_text(encoding="utf-8")
                    lines.extend([
                        "", f"### Round {round_row['round']}", "",
                        f"- Lint: `{round_row['lint']}`",
                        f"- Screen: `{(round_row.get('screen') or {}).get('label') or 'invalid'}`",
                        f"- Repeats: `{robust.get('label_distribution') or {}}`; "
                        f"target hits {robust.get('target_hits', 0)}/{robust.get('n', 0)}",
                        *([] if getattr(self.args, "focal_only", False) else [
                            f"- Anchors correct: {sum(a.get('correct', False) for a in round_row.get('anchors') or [])}/6"
                        ]),
                        f"- Accepted: `{round_row.get('accepted', False)}`",
                        f"- Prompt: `{round_row.get('candidate_prompt_path')}`",
                        f"- Diff: `{round_row.get('prompt_diff_path')}`",
                    ])
                    if diff_text:
                        lines.extend([
                            "", "<details><summary>Prompt progression diff</summary>", "",
                            "```diff", diff_text.rstrip(), "```", "", "</details>",
                        ])
            (repair_dir / f"{_case_slug(baseline['item_id'])}.md").write_text(
                "\n".join(lines) + "\n", encoding="utf-8"
            )
        md = [
            "# AURORA individual prompt-repair summary", "",
            f"Model: `{summary['model']}`", "",
            f"Initial accuracy: `{summary['baseline']['accuracy']}`", "",
            f"Initial robust coverage: `{summary['baseline']['robust_coverage']}`", "",
            f"Repair pool: `{summary['baseline']['repair_pool_size']}`", "",
            f"Robust means empirically stable at {self.args.robust_min_correct}/{self.args.repeats} "
            "fresh repeated calls, not a "
            "high-confidence statistical guarantee.", "",
        ]
        for method, values in summary["repair"].items():
            md.append(
                f"- {method}: {values['accepted']}/{values['eligible']} robust repairs "
                f"({values['repair_rate']})"
            )
        md.extend([
            "",
            f"Recorded tokens: {summary['usage']['total_tokens']}",
            f"Estimated API cost: ${summary['estimated_cost_usd']:.4f}",
        ])
        (self.run_dir / "summary.md").write_text("\n".join(md) + "\n", encoding="utf-8")


def _counts(values: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        key = str(value)
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def _collect_usage(checkpoint: CheckpointStore) -> dict[str, Any]:
    usage = {
        "judge_calls": 0,
        "optimizer_rounds": 0,
        "optimizer_model_calls": 0,
        "gepa_metric_calls": 0,
        "gepa_reflection_calls": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "latency_seconds": 0.0,
        "models": {},
    }
    seen_call_ids: set[str] = set()
    for key, value in checkpoint.items():
        if not isinstance(value, dict):
            continue
        if "::judge::" in key and value.get("call_id") not in seen_call_ids:
            seen_call_ids.add(str(value.get("call_id")))
            usage["judge_calls"] += 1
            for name in ("prompt_tokens", "completion_tokens", "total_tokens"):
                usage[name] += int(value.get(name) or 0)
            usage["latency_seconds"] += float(value.get("latency_seconds") or 0)
            model = str(value.get("model") or value.get("requested_model") or "unknown")
            usage["models"][model] = usage["models"].get(model, 0) + 1
        elif "::optimizer::" in key:
            usage["optimizer_rounds"] += 1
            nested = value.get("usage")
            nested_rows = nested if isinstance(nested, list) else [nested]
            for row in nested_rows:
                if not isinstance(row, dict):
                    continue
                calls = row.get("calls") if isinstance(row.get("calls"), list) else []
                if calls:
                    usage["optimizer_model_calls"] += len(calls)
                    usage["gepa_metric_calls"] += sum(
                        str(call.get("call_type") or "").startswith("gepa_metric:")
                        for call in calls
                    )
                    usage["gepa_reflection_calls"] += sum(
                        call.get("call_type") == "reflection" for call in calls
                    )
                    usage["latency_seconds"] += sum(
                        float(call.get("latency_seconds") or 0) for call in calls
                    )
                    for call in calls:
                        model = str(call.get("model") or "unknown")
                        usage["models"][model] = usage["models"].get(model, 0) + 1
                else:
                    # One TextGrad EngineLM generation per successful adapter result.
                    usage["optimizer_model_calls"] += 1
                    usage["latency_seconds"] += float(
                        row.get("latencySeconds") or row.get("latency_seconds") or 0
                    )
                    model = str(row.get("model") or "unknown")
                    usage["models"][model] = usage["models"].get(model, 0) + 1
                for source, target in (
                    ("promptTokens", "prompt_tokens"),
                    ("completionTokens", "completion_tokens"),
                    ("totalTokens", "total_tokens"),
                    ("prompt_tokens", "prompt_tokens"),
                    ("completion_tokens", "completion_tokens"),
                    ("total_tokens", "total_tokens"),
                ):
                    usage[target] += int(row.get(source) or 0)
    usage["latency_seconds"] = round(usage["latency_seconds"], 3)
    usage["completed_model_calls"] = (
        usage["judge_calls"] + usage["optimizer_model_calls"]
    )
    return usage


def _parse_methods(value: str) -> list[str]:
    methods = [part.strip().lower() for part in value.split(",") if part.strip()]
    invalid = set(methods) - {"textgrad", "gepa"}
    if not methods or invalid:
        raise argparse.ArgumentTypeError("methods must be textgrad, gepa, or both")
    return list(dict.fromkeys(methods))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["sample", "baseline", "repair", "report", "all"])
    parser.add_argument("--live", action="store_true", help="Authorize billable model calls.")
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dataset-root", type=Path, default=config.AURORA_BENCH_ROOT)
    parser.add_argument("--prompt-path", type=Path, default=DEFAULT_PROMPT_PATH)
    parser.add_argument("--model", default="gpt-5.4-mini")
    parser.add_argument("--sample-size", type=int, default=100)
    parser.add_argument("--seed", type=int, default=44)
    parser.add_argument("--repeats", type=int, default=10)
    parser.add_argument("--robust-min-correct", type=int, default=7)
    parser.add_argument(
        "--focal-only",
        action="store_true",
        help=(
            "Optimize and accept only on the focal case; do not select, evaluate, or "
            "feed back generality anchors."
        ),
    )
    parser.add_argument("--repeat-temperature", type=float, default=0.3)
    parser.add_argument("--max-rounds", type=int, default=5)
    parser.add_argument("--methods", type=_parse_methods, default=["textgrad", "gepa"])
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument(
        "--no-progress", action="store_true",
        help="Disable terminal progress bars (useful when another process owns stderr).",
    )
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--max-tokens", type=int, default=1024)
    parser.add_argument("--optimizer-max-tokens", type=int, default=4096)
    parser.add_argument("--gepa-python", type=Path, default=DEFAULT_GEPA_PYTHON)
    parser.add_argument("--input-cost-per-million", type=float, default=0.75)
    parser.add_argument("--output-cost-per-million", type=float, default=4.50)
    return parser


def _validate_args(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    if args.sample_size < 6 and not args.focal_only:
        parser.error("--sample-size must be at least 6 to provide two anchors per label")
    if args.repeats < 1 or not 1 <= args.robust_min_correct <= args.repeats:
        parser.error("robust-min-correct must be between 1 and repeats")
    if args.max_rounds < 1 or args.concurrency < 1 or args.timeout < 1:
        parser.error("max-rounds, concurrency, and timeout must be positive")
    if not 0 <= args.repeat_temperature <= 2:
        parser.error("repeat-temperature must be in [0, 2]")
    if args.phase in {"baseline", "repair"} and not args.live:
        parser.error(f"{args.phase} makes model calls and requires --live")
    if args.phase in {"repair", "report"} and args.run_dir is None:
        parser.error(f"{args.phase} requires --run-dir pointing to an existing staged run")
    if args.resume and args.run_dir is None:
        parser.error("--resume requires --run-dir")


def _run_dir(args: argparse.Namespace) -> Path:
    if args.run_dir:
        path = args.run_dir.resolve()
        if path.exists() and any(path.iterdir()) and not args.resume:
            raise ValueError(f"run directory is not empty; pass --resume: {path}")
        return path
    stamp = time.strftime("%y%m%d-%H%M%S")
    return config.LOGS_ROOT / "exps" / f"{stamp}-aurora-individual-repair"


def _save_config(experiment: Experiment) -> None:
    args = experiment.args
    payload = {
        "experiment": "aurora_individual_prompt_repair",
        "model": args.model,
        "seed": args.seed,
        "sample_size": args.sample_size,
        "repeats": args.repeats,
        "robust_min_correct": args.robust_min_correct,
        "focal_only": args.focal_only,
        "repeat_temperature": args.repeat_temperature,
        "max_rounds": args.max_rounds,
        "methods": args.methods,
        "concurrency": args.concurrency,
        "progress": not args.no_progress,
        "timeout": args.timeout,
        "max_tokens": args.max_tokens,
        "optimizer_max_tokens": args.optimizer_max_tokens,
        "dataset_root": str(args.dataset_root.resolve()),
        "prompt_path": str(args.prompt_path.resolve()),
        "prompt_sha256": prompt_digest(experiment.prompt),
        "gepa_python": str(args.gepa_python.resolve()),
        "input_cost_per_million": args.input_cost_per_million,
        "output_cost_per_million": args.output_cost_per_million,
    }
    path = experiment.run_dir / "run_config.json"
    if path.is_file():
        old = _read_json(path)
        critical = [
            "model", "seed", "sample_size", "repeats", "robust_min_correct",
            "repeat_temperature", "max_rounds", "methods", "focal_only", "prompt_sha256",
        ]
        changed = [name for name in critical if old.get(name) != payload.get(name)]
        if changed:
            raise ValueError(f"resume configuration changed critical fields: {changed}")
    else:
        _atomic_json(path, payload)


def _write_preflight(experiment: Experiment) -> None:
    manifest = experiment._manifest()
    sample_size = len(manifest["cases"])
    repeats = experiment.args.repeats
    rounds = experiment.args.max_rounds
    methods = experiment.args.methods
    anchor_calls = 0 if experiment.args.focal_only else 6
    per_round_external = 1 + repeats + anchor_calls
    gepa_internal = (4 if experiment.args.focal_only else 16) if "gepa" in methods else 0
    payload = {
        "dry_run": True,
        "sample_size": sample_size,
        "baseline_judge_calls": sample_size * (1 + repeats),
        "repair_pool_size": "known after baseline",
        "worst_case_if_every_case_requires_repair": {
            "outer_rounds": sample_size * len(methods) * rounds,
            "external_screen_repeat_anchor_calls": (
                sample_size * len(methods) * rounds * per_round_external
            ),
            "gepa_internal_metric_calls": sample_size * rounds * gepa_internal,
            "note": (
                "Repeat and anchor calls only occur after the preceding gates pass, so actual "
                "usage should be lower. Each GEPA proposal also makes one reflection call."
            ),
        },
        "model": experiment.args.model,
        "methods": methods,
        "acceptance_mode": "focal_only" if experiment.args.focal_only else "anchor_guard",
    }
    _atomic_json(experiment.run_dir / "preflight.json", payload)


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _validate_args(parser, args)
    try:
        run_dir = _run_dir(args)
    except ValueError as exc:
        parser.error(str(exc))
    run_dir.mkdir(parents=True, exist_ok=True)
    experiment = Experiment(args, run_dir)
    try:
        _save_config(experiment)
        if args.phase == "sample":
            experiment.sample()
        elif args.phase == "baseline":
            experiment.configure_live()
            experiment.baseline()
            experiment.report()
        elif args.phase == "repair":
            experiment.configure_live()
            experiment.configure_optimizers()
            experiment.repair()
            experiment.report()
        elif args.phase == "report":
            experiment.report()
        elif args.phase == "all":
            sample_path = experiment.run_dir / "sample_manifest.json"
            if not (args.resume and sample_path.is_file()):
                experiment.sample()
            if not args.live:
                _write_preflight(experiment)
            else:
                experiment.configure_live()
                experiment.baseline()
                experiment.configure_optimizers()
                experiment.repair()
                experiment.report()
        else:  # pragma: no cover - argparse owns choices
            raise AssertionError(args.phase)
    finally:
        experiment.close()
    print(f"run_dir={run_dir}")
    if not args.live and args.phase == "all":
        print("dry_run=true; rerun with --live --run-dir <path> --resume")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
