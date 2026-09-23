"""Append-only writer for ``llm-histories.log`` (one JSON object per line).

Per CLAUDE.md, every LM call records model name, version, prompt hash, and token
counts. The raw token never appears here. Prompts are hashed (and optionally stored)
so a run is auditable without bloating the log with full media payloads.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from pathlib import Path
from typing import Any, Optional


def prompt_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


class LLMHistoryWriter:
    """Thread-safe JSONL appender for LLM request/response history."""

    def __init__(self, path: str | Path, *, store_prompts: bool = True) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._store_prompts = store_prompts
        self._lock = threading.Lock()

    def record(
        self,
        *,
        engine: str,
        model: str,
        prompt: str,
        response: Optional[str],
        media_inputs: Optional[list[Any]] = None,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0,
        latency_s: Optional[float] = None,
        endpoint: Optional[str] = None,
        error: Optional[str] = None,
        extra: Optional[dict[str, Any]] = None,
    ) -> None:
        entry: dict[str, Any] = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "engine": engine,
            "model": model,
            "prompt_hash": prompt_hash(prompt),
            "prompt_chars": len(prompt),
            "n_media": len(media_inputs or []),
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
        }
        if latency_s is not None:
            entry["latency_s"] = round(latency_s, 3)
        if endpoint:
            entry["endpoint_host"] = endpoint
        if error:
            entry["error"] = error
        if self._store_prompts:
            entry["prompt"] = prompt
            entry["response"] = response
        if extra:
            entry.update(extra)

        line = json.dumps(entry, ensure_ascii=False, default=str)
        with self._lock:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
