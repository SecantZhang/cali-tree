#!/usr/bin/env python3
"""Optimize one flat Cali-Tree judge prompt with GEPA, as an independent baseline.

Runs in the isolated `.venv-gepa` (Python 3.11+) -- imports nothing from `vejudge`. Reads
`.creds.json` (Stage 2) and `dataset_export.json` (Stage 1), both produced by the main venv.
Task-side judging is multimodal (SOURCE+EDITED images), which GEPA's built-in text-only
`task_lm` cannot express, so this supplies a custom `GEPAAdapter`. Reflection is text-only and
uses the same Pluto-backed callable for both roles.

Never raises on a per-example failure (network error, malformed JSON) -- GEPA's adapter
contract requires a fallback score (0.0) instead, per `GEPAAdapter.evaluate`'s docstring.
"""

from __future__ import annotations

import base64
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

import requests

# This worker runs in an isolated GEPA environment with requests available.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "vejudge" / "lm_engine"))
from provider_api import chat_request

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
SEED_PROMPT_PATH = (
    REPO_ROOT / "vejudge" / "core" / "prompts" / "templates" / "calitree_v2" / "initial_rubric.txt"
)
CREDS_PATH = HERE / ".creds.json"
DATASET_PATH = HERE / "dataset_export.json"
ARTIFACT_PATH = HERE / "artifact.json"

LABELS = ("no", "partial", "yes")
RETRYABLE_STATUS = {408, 409, 429, 500, 502, 503, 504}


def _image_data_uri(path: str) -> str:
    p = Path(path)
    b64 = base64.b64encode(p.read_bytes()).decode("ascii")
    suffix = p.suffix.lstrip(".").lower() or "png"
    mime = "jpeg" if suffix in ("jpg", "jpeg") else suffix
    return f"data:image/{mime};base64,{b64}"


def _parse_json_object(content: str) -> dict[str, Any]:
    """Mirrors vejudge.core.judge.parse.parse_json_object -- strips markdown fences."""
    text = (content or "").strip()
    if text.startswith("```"):
        lines = text.split("\n")
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return json.loads(text)


class PlutoClient:
    """Minimal OpenAI-compatible chat client with endpoint failover + retry.

    Mirrors the request/response shape of vejudge/lm_engine/openai_compat.py's
    `chat_completion`, reimplemented standalone since this venv can't import vejudge.
    """

    def __init__(self, endpoints: list[str], token: str) -> None:
        self.endpoints = endpoints
        self.token = token

    def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str,
        max_tokens: int = 1024,
        temperature: float = 0.0,
        max_retries: int = 4,
        timeout: int = 300,
    ) -> tuple[str, dict[str, int]]:
        errors: list[str] = []
        for base in self.endpoints:
            url, payload, headers, _ = chat_request(
                base, self.token, model, messages, max_tokens, temperature
            )
            host = urlparse(url).netloc
            for attempt in range(max_retries + 1):
                try:
                    resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
                except requests.RequestException as exc:
                    errors.append(f"{host}: {type(exc).__name__}: {exc}")
                    if attempt < max_retries:
                        time.sleep(2 ** attempt)
                        continue
                    break
                if resp.status_code in RETRYABLE_STATUS:
                    if attempt < max_retries:
                        time.sleep(2 ** attempt)
                        continue
                    errors.append(f"{host}: HTTP {resp.status_code} {resp.text[:300]}")
                    break
                if resp.status_code >= 400:
                    errors.append(f"{host}: HTTP {resp.status_code} {resp.text[:500]}")
                    break
                data = resp.json()
                choices = data.get("choices") or []
                content = ""
                if choices and isinstance(choices[0], dict):
                    msg = choices[0].get("message") or {}
                    content = str(msg.get("content") or "")
                usage = data.get("usage") or {}
                return content, {
                    "prompt_tokens": int(usage.get("prompt_tokens", 0)),
                    "completion_tokens": int(usage.get("completion_tokens", 0)),
                    "total_tokens": int(usage.get("total_tokens", 0)),
                }
        raise RuntimeError("All chat/completions endpoints failed:\n  " + "\n  ".join(errors))


class PlutoLanguageModel:
    """A gepa.proposer.reflective_mutation.base.LanguageModel: __call__(prompt) -> str.

    Used for GEPA's reflection role (text-only), backed by the same Pluto gateway.
    """

    def __init__(self, client: PlutoClient, model: str, usage: dict[str, int]) -> None:
        self.client = client
        self.model = model
        self.usage = usage

    def __call__(self, prompt: str | list[dict[str, Any]]) -> str:
        messages = (
            prompt if isinstance(prompt, list) else [{"role": "user", "content": prompt}]
        )
        content, call_usage = self.client.chat(messages, model=self.model, max_tokens=4096)
        for key, value in call_usage.items():
            self.usage[key] = self.usage.get(key, 0) + value
        self.usage["reflection_calls"] = self.usage.get("reflection_calls", 0) + 1
        return content


class VEJudgeGEPAAdapter:
    """GEPAAdapter for the flat Cali-Tree judge: evaluate() makes the real multimodal call."""

    # GEPAAdapter is a Protocol with a default `propose_new_texts = None` class attribute;
    # a plain (non-inheriting) class does not pick that up automatically, and GEPA's engine
    # checks `adapter.propose_new_texts is not None` without a getattr(..., None) guard, so
    # omitting this raises AttributeError on every reflective-mutation attempt.
    propose_new_texts = None

    def __init__(
        self, client: PlutoClient, model: str, usage: dict[str, int], concurrency: int = 8
    ) -> None:
        self.client = client
        self.model = model
        self.usage = usage
        self.concurrency = concurrency

    def _judge_one(self, item: dict[str, Any], system_prompt: str) -> dict[str, Any]:
        instruction = item["instruction"]
        user_content = [
            {
                "type": "text",
                "text": (
                    f"Instruction: {instruction}\n"
                    "The first image is SOURCE; the second is EDITED."
                ),
            },
            {"type": "image_url", "image_url": {"url": _image_data_uri(item["source_image_path"])}},
            {"type": "image_url", "image_url": {"url": _image_data_uri(item["edited_image_path"])}},
        ]
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]
        try:
            content, call_usage = self.client.chat(messages, model=self.model)
            for key, value in call_usage.items():
                self.usage[key] = self.usage.get(key, 0) + value
            self.usage["task_calls"] = self.usage.get("task_calls", 0) + 1
            parsed = _parse_json_object(content)
            label = str(parsed.get("label") or "")
            rationale = str(parsed.get("rationale") or "")
            if label not in LABELS:
                raise ValueError(f"invalid label {label!r} in response {content[:200]!r}")
            return {"label": label, "rationale": rationale, "error": None}
        except Exception as exc:  # noqa: BLE001 -- adapter contract: never raise per-example
            return {"label": "", "rationale": "", "error": f"{type(exc).__name__}: {exc}"}

    def evaluate(self, batch, candidate, capture_traces: bool = False):
        from gepa.core.adapter import EvaluationBatch

        system_prompt = candidate["system_prompt"]
        with ThreadPoolExecutor(max_workers=self.concurrency) as pool:
            outputs = list(pool.map(lambda item: self._judge_one(item, system_prompt), batch))
        scores = [
            1.0 if out["label"] and out["label"] == item["target_label"] else 0.0
            for out, item in zip(outputs, batch)
        ]
        trajectories = None
        if capture_traces:
            trajectories = [
                {"item": item, "output": out} for item, out in zip(batch, outputs)
            ]
        return EvaluationBatch(outputs=outputs, scores=scores, trajectories=trajectories)

    def make_reflective_dataset(self, candidate, eval_batch, components_to_update):
        records = []
        for traj in eval_batch.trajectories or []:
            item, out = traj["item"], traj["output"]
            target = item["target_label"]
            predicted = out["label"] or "(invalid/unparseable response)"
            if out["error"]:
                feedback = f"The judge call failed: {out['error']}. Target label was {target!r}."
            elif predicted == target:
                feedback = f"Correct: predicted {predicted!r} matches target {target!r}."
            else:
                feedback = (
                    f"Incorrect: predicted {predicted!r} but the target label is {target!r}. "
                    f"Rationale given: {out['rationale'][:300]!r}"
                )
            records.append({
                "Inputs": {"instruction": item["instruction"]},
                "Generated Outputs": {"label": predicted, "rationale": out["rationale"]},
                "Feedback": feedback,
            })
        return {name: records for name in components_to_update}


def main() -> int:
    creds = json.loads(CREDS_PATH.read_text(encoding="utf-8"))
    dataset = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    seed_prompt = SEED_PROMPT_PATH.read_text(encoding="utf-8").strip()

    trainset = [row for row in dataset.values() if row.get("cal_split") == "fit"]
    valset = [row for row in dataset.values() if row.get("cal_split") == "validation"]
    print(f"trainset={len(trainset)} valset={len(valset)}")

    usage: dict[str, int] = {}
    client = PlutoClient(creds["endpoints"], creds["token"])
    adapter = VEJudgeGEPAAdapter(client, model="gpt-4.1-mini", usage=usage, concurrency=8)
    reflection_lm = PlutoLanguageModel(client, model="gpt-4.1-mini", usage=usage)

    import gepa

    start = time.time()
    result = gepa.optimize(
        seed_candidate={"system_prompt": seed_prompt},
        trainset=trainset,
        valset=valset,
        adapter=adapter,
        reflection_lm=reflection_lm,
        max_metric_calls=700,
        seed=44,
        run_dir=str(HERE / "gepa_run"),
        display_progress_bar=True,
    )
    wall_clock = time.time() - start

    artifact = {
        "prompt": result.best_candidate["system_prompt"],
        "seed_prompt_version": "calitree_v2",
        "total_metric_calls": result.total_metric_calls,
        "best_val_score": (
            result.val_aggregate_scores[result.best_idx]
            if result.val_aggregate_scores else None
        ),
        "num_candidates": result.num_candidates,
        "usage": usage,
        "wall_clock_seconds": wall_clock,
        "max_metric_calls_budget": 700,
        "trainset_size": len(trainset),
        "valset_size": len(valset),
    }
    ARTIFACT_PATH.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    print(f"wrote {ARTIFACT_PATH}")
    print(json.dumps({k: v for k, v in artifact.items() if k != "prompt"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
