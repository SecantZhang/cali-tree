#!/usr/bin/env python3
"""Isolated GEPA 0.1.4 worker; stdin and stdout each carry one JSON line."""

from __future__ import annotations

import base64
import contextlib
import json
import os
import sys
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

LABELS = ("no", "partial", "yes")
RETRYABLE = {408, 409, 429, 500, 502, 503, 504}


@lru_cache(maxsize=32)
def image_data_uri(path: str) -> str:
    source = Path(path)
    encoded = base64.b64encode(source.read_bytes()).decode("ascii")
    suffix = source.suffix.lstrip(".").lower() or "png"
    mime = "jpeg" if suffix in {"jpg", "jpeg"} else suffix
    return f"data:image/{mime};base64,{encoded}"


def parse_judgment(content: str) -> dict[str, Any]:
    text = (content or "").strip()
    if text.startswith("```"):
        lines = text.splitlines()[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        value = json.loads(text)
        label = str(value.get("label") or "").strip().lower()
        if label not in LABELS:
            raise ValueError(f"invalid label {label!r}")
        return {
            "label": label,
            "rationale": str(value.get("rationale") or ""),
            "valid": True,
            "error": None,
        }
    except Exception as exc:  # GEPA adapters return a score rather than raising per item
        return {
            "label": "",
            "rationale": "",
            "valid": False,
            "error": f"{type(exc).__name__}: {exc}",
        }


class Client:
    def __init__(self, endpoints: list[str], token: str, usage: dict[str, Any]) -> None:
        self.endpoints = endpoints
        self.token = token
        self.usage = usage
        self.lock = threading.Lock()

    def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str,
        temperature: float,
        max_tokens: int,
        timeout: int,
        call_type: str,
    ) -> tuple[str, dict[str, Any]]:
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        headers = {
            "Content-Type": "application/json; charset=UTF-8",
            "Authorization": f"Bearer {self.token}",
        }
        errors: list[str] = []
        for endpoint_index, base in enumerate(self.endpoints):
            url = base.rstrip("/") + "/chat/completions"
            host = urlparse(url).netloc
            for attempt in range(5):
                started = time.time()
                try:
                    response = requests.post(
                        url, json=payload, headers=headers, timeout=timeout
                    )
                    latency = time.time() - started
                except requests.RequestException as exc:
                    errors.append(f"{host}: {type(exc).__name__}: {exc}")
                    if attempt < 4:
                        time.sleep(min(2 ** attempt, 30))
                        continue
                    break
                if response.status_code in RETRYABLE:
                    if response.status_code == 429 and endpoint_index < len(self.endpoints) - 1:
                        errors.append(f"{host}: HTTP 429")
                        break
                    if attempt < 4:
                        retry_after = response.headers.get("Retry-After")
                        try:
                            delay = float(retry_after) if retry_after else min(2 ** attempt, 30)
                        except ValueError:
                            delay = min(2 ** attempt, 30)
                        time.sleep(delay)
                        continue
                    errors.append(f"{host}: HTTP {response.status_code} {response.text[:300]}")
                    break
                if response.status_code >= 400:
                    errors.append(f"{host}: HTTP {response.status_code} {response.text[:500]}")
                    break
                data = response.json()
                choices = data.get("choices") or []
                content = ""
                if choices and isinstance(choices[0], dict):
                    content = str((choices[0].get("message") or {}).get("content") or "")
                raw_usage = data.get("usage") or {}
                call = {
                    "call_type": call_type,
                    "model": str(data.get("model") or model),
                    "prompt_tokens": int(raw_usage.get("prompt_tokens") or 0),
                    "completion_tokens": int(raw_usage.get("completion_tokens") or 0),
                    "total_tokens": int(raw_usage.get("total_tokens") or 0),
                    "latency_seconds": latency,
                    "endpoint_host": host,
                }
                with self.lock:
                    self.usage["calls"].append(call)
                    self.usage["prompt_tokens"] += call["prompt_tokens"]
                    self.usage["completion_tokens"] += call["completion_tokens"]
                    self.usage["total_tokens"] += call["total_tokens"]
                return content, call
        raise RuntimeError("all endpoints failed: " + " | ".join(errors))


class ReflectionLM:
    def __init__(self, client: Client, model: str, timeout: int) -> None:
        self.client = client
        self.model = model
        self.timeout = timeout

    def __call__(self, prompt: Any) -> str:
        messages = prompt if isinstance(prompt, list) else [{"role": "user", "content": str(prompt)}]
        content, _ = self.client.chat(
            messages,
            model=self.model,
            temperature=0.0,
            max_tokens=4096,
            timeout=self.timeout,
            call_type="reflection",
        )
        return content


class Adapter:
    propose_new_texts = None

    def __init__(
        self, client: Client, model: str, timeout: int, failure_context: str
    ) -> None:
        self.client = client
        self.model = model
        self.timeout = timeout
        self.failure_context = failure_context

    def _judge(self, item: dict[str, Any], system_prompt: str) -> dict[str, Any]:
        user_content = [
            {
                "type": "text",
                "text": (
                    f"Instruction: {item['instruction']}\n"
                    "The first image is SOURCE; the second is EDITED."
                ),
            },
            {"type": "image_url", "image_url": {"url": image_data_uri(item["source_image_path"])}},
            {"type": "image_url", "image_url": {"url": image_data_uri(item["edited_image_path"])}},
        ]
        try:
            content, call = self.client.chat(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                model=self.model,
                temperature=0.0,
                max_tokens=1024,
                timeout=self.timeout,
                call_type=f"gepa_metric:{item['role']}",
            )
            parsed = parse_judgment(content)
            return {**parsed, "raw_content": content, "model": call["model"]}
        except Exception as exc:
            return {
                "label": "", "rationale": "", "valid": False,
                "raw_content": "", "error": f"{type(exc).__name__}: {exc}",
            }

    def evaluate(self, batch, candidate, capture_traces: bool = False):
        from gepa.core.adapter import EvaluationBatch

        prompt = candidate["system_prompt"]
        with ThreadPoolExecutor(max_workers=min(7, len(batch))) as pool:
            outputs = list(pool.map(lambda item: self._judge(item, prompt), batch))
        # A focal correction is worth 0.70; preserving all six anchors is worth 0.30.
        # GEPA averages these per-instance values, but the common divisor does not alter
        # candidate ranking.
        scores = [
            (0.70 if item["role"] == "focal" else 0.05)
            if output.get("label") == item["target_label"]
            else 0.0
            for item, output in zip(batch, outputs)
        ]
        trajectories = (
            [{"item": item, "output": output} for item, output in zip(batch, outputs)]
            if capture_traces
            else None
        )
        return EvaluationBatch(outputs=outputs, scores=scores, trajectories=trajectories)

    def make_reflective_dataset(self, candidate, eval_batch, components_to_update):
        records = []
        for trajectory in eval_batch.trajectories or []:
            item = trajectory["item"]
            output = trajectory["output"]
            records.append({
                "Inputs": {
                    "instruction": item["instruction"],
                    "role": item["role"],
                },
                "Generated Outputs": {
                    "label": output.get("label") or "invalid",
                    "rationale": output.get("rationale") or "",
                },
                "Feedback": (
                    f"Target label: {item['target_label']}. "
                    f"This is the {item['role']} example. {self.failure_context} "
                    "Revise a reusable semantic-consistency decision boundary; never copy "
                    "the instruction, identify the item/model, or prescribe this answer."
                ),
            })
        return {name: records for name in components_to_update}


def run(request: dict[str, Any]) -> dict[str, Any]:
    import gepa
    from gepa.utils.stop_condition import MaxCandidateProposalsStopper

    token = os.environ.get("AURORA_GEPA_TOKEN", "")
    endpoints = json.loads(os.environ.get("AURORA_GEPA_ENDPOINTS", "[]"))
    if not token or not endpoints:
        raise RuntimeError("worker credentials were not provided")
    usage: dict[str, Any] = {
        "calls": [], "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0,
    }
    client = Client(endpoints, token, usage)
    model = str(request["model"])
    timeout = int(request.get("timeout") or 120)
    adapter = Adapter(client, model, timeout, str(request.get("feedback") or ""))
    reflection = ReflectionLM(client, model, timeout)
    focal = {**request["focal"], "role": "focal"}
    anchors = [{**row, "role": "anchor"} for row in request["anchors"]]
    run_dir = Path(request["run_dir"])
    run_dir.mkdir(parents=True, exist_ok=True)
    with contextlib.redirect_stdout(sys.stderr):
        result = gepa.optimize(
            seed_candidate={"system_prompt": str(request["prompt"])},
            trainset=[focal],
            valset=[focal, *anchors],
            adapter=adapter,
            reflection_lm=reflection,
            candidate_selection_strategy="current_best",
            skip_perfect_score=False,
            reflection_minibatch_size=1,
            use_merge=False,
            stop_callbacks=MaxCandidateProposalsStopper(1),
            seed=int(request.get("seed") or 44),
            run_dir=str(run_dir),
            track_best_outputs=True,
            display_progress_bar=False,
            cache_evaluation=False,
        )
    candidate = (
        result.candidates[-1]["system_prompt"]
        if len(result.candidates) > 1
        else str(request["prompt"])
    )
    return {
        "request_id": request.get("request_id"),
        "prompt": candidate,
        "usage": usage,
        "lineage": {
            "num_candidates": result.num_candidates,
            "candidates": result.candidates,
            "parents": result.parents,
            "val_aggregate_scores": result.val_aggregate_scores,
            "val_subscores": result.val_subscores,
            "discovery_eval_counts": result.discovery_eval_counts,
            "best_index": result.best_idx,
            "returned_candidate_index": len(result.candidates) - 1,
            "total_metric_calls": result.total_metric_calls,
            "num_full_val_evals": result.num_full_val_evals,
        },
    }


def main() -> int:
    line = sys.stdin.readline()
    try:
        request = json.loads(line)
        response = run(request)
    except Exception as exc:
        response = {
            "error": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc(),
        }
    sys.stdout.write(json.dumps(response, ensure_ascii=False, default=str) + "\n")
    sys.stdout.flush()
    return 0 if not response.get("error") else 1


if __name__ == "__main__":
    raise SystemExit(main())
