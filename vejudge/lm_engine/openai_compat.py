"""Shared retrying transport for OpenAI-compatible and native Gemini APIs."""

from __future__ import annotations

import base64
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

import requests

from .provider_api import chat_request, chat_response


@dataclass
class ChatResult:
    content: Optional[str]
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    endpoint_host: str
    latency_s: float
    model: str


@dataclass
class EmbeddingResult:
    vectors: list[list[float]]
    prompt_tokens: int
    total_tokens: int
    endpoint_host: str
    latency_s: float
    model: str


def text_part(text: str) -> dict[str, Any]:
    return {"type": "text", "text": text}


def video_part(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    b64 = base64.b64encode(p.read_bytes()).decode("ascii")
    return {"type": "image_url", "image_url": {"url": f"data:video/mp4;base64,{b64}"}}


def image_part(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    b64 = base64.b64encode(p.read_bytes()).decode("ascii")
    suffix = p.suffix.lstrip(".").lower() or "png"
    mime = "jpeg" if suffix in ("jpg", "jpeg") else suffix
    return {"type": "image_url", "image_url": {"url": f"data:image/{mime};base64,{b64}"}}


def _retry_after_seconds(resp: Optional["requests.Response"], attempt: int) -> float:
    """Seconds to wait before retrying, honoring Retry-After when present.

    ``resp`` is None for network-level errors (no response), in which case we fall back
    to exponential backoff.
    """
    if resp is not None:
        ra = resp.headers.get("retry-after") or resp.headers.get("Retry-After")
        if ra:
            try:
                return float(ra)
            except ValueError:
                pass
    # Exponential backoff fallback (1s, 2s, 4s, ...), capped.
    return min(2.0 ** attempt, 30.0)


# Transient statuses worth retrying on the SAME endpoint (gateway/upstream blips):
# 408 request timeout and 5xx upstream errors (the Pluto proxy returns 502/503/504 when
# its upstream resets or read-times-out on large media payloads).  A 429 is handled
# separately: when a mirror exists it is a capacity signal, so fail over immediately.
_RETRYABLE_STATUS = frozenset({408, 429, 500, 502, 503, 504})


def chat_completion(
    *,
    endpoints: list[str],
    token: str,
    model: str,
    messages: list[dict[str, Any]],
    max_tokens: int = 4096,
    temperature: float = 0.3,
    timeout: int = 300,
    max_retries: int = 4,
    provider: Optional[str] = None,
) -> ChatResult:
    """POST to the first reachable endpoint, falling over to the rest in order.

    Transient failures — HTTP 408/5xx and network errors (connection reset, read timeout)
    — are retried on the *same* endpoint up to ``max_retries`` times. A 429 falls through
    to a configured mirror immediately, but retains the same-endpoint retry behavior when
    it is the only endpoint. Non-retryable responses (e.g. 400/401/404) fall over
    immediately. Raises only if all endpoints fail.
    """
    errors: list[str] = []
    for endpoint_index, base in enumerate(endpoints):
        url, payload, headers, dialect = chat_request(
            base, token, model, messages, max_tokens, temperature, provider
        )
        host = urlparse(url).netloc
        for attempt in range(max_retries + 1):
            t0 = time.time()
            try:
                resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
                latency = time.time() - t0
            except requests.RequestException as e:  # connection reset / read timeout
                errors.append(f"{host}: {type(e).__name__}: {e}")
                if attempt < max_retries:
                    time.sleep(_retry_after_seconds(None, attempt))
                    continue
                break  # exhausted -> next endpoint

            if resp.status_code in _RETRYABLE_STATUS:
                # A per-user 429 means this endpoint is presently saturated for this
                # workload. Retrying it from every concurrent worker only extends the stall;
                # move immediately to the configured mirror, which may have independent
                # capacity. Other transient statuses retain bounded same-endpoint retries.
                if resp.status_code == 429 and endpoint_index < len(endpoints) - 1:
                    errors.append(f"{host}: HTTP 429 {resp.text[:300]}")
                    break
                if attempt < max_retries:
                    time.sleep(_retry_after_seconds(resp, attempt))
                    continue
                errors.append(f"{host}: HTTP {resp.status_code} {resp.text[:300]}")
                break  # exhausted -> next endpoint
            if resp.status_code >= 400:
                errors.append(f"{host}: HTTP {resp.status_code} {resp.text[:500]}")
                break  # non-retryable -> next endpoint

            data = resp.json()
            content, prompt_tokens, completion_tokens, total_tokens, returned_model = chat_response(data, dialect, model)
            return ChatResult(content, prompt_tokens, completion_tokens, total_tokens,
                              host, latency, returned_model)

    raise RuntimeError(
        "All chat/completions endpoints failed:\n  " + "\n  ".join(errors)
    )


def embeddings(
    *,
    endpoints: list[str],
    token: str,
    model: str,
    inputs: list[str],
    timeout: int = 300,
    max_retries: int = 4,
) -> EmbeddingResult:
    """OpenAI-compatible ``/embeddings`` transport with the same retry/failover policy."""
    payload = {"model": model, "input": inputs}
    headers = {
        "Content-Type": "application/json; charset=UTF-8",
        "Authorization": f"Bearer {token}",
    }
    errors: list[str] = []
    for base in endpoints:
        url = base.rstrip("/") + "/embeddings"
        host = urlparse(url).netloc
        for attempt in range(max_retries + 1):
            t0 = time.time()
            try:
                resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
                latency = time.time() - t0
            except requests.RequestException as exc:
                errors.append(f"{host}: {type(exc).__name__}: {exc}")
                if attempt < max_retries:
                    time.sleep(_retry_after_seconds(None, attempt))
                    continue
                break
            if resp.status_code in _RETRYABLE_STATUS:
                if attempt < max_retries:
                    time.sleep(_retry_after_seconds(resp, attempt))
                    continue
                errors.append(f"{host}: HTTP {resp.status_code} {resp.text[:300]}")
                break
            if resp.status_code >= 400:
                errors.append(f"{host}: HTTP {resp.status_code} {resp.text[:500]}")
                break
            data = resp.json()
            ordered = sorted(data.get("data") or [], key=lambda row: row.get("index", 0))
            vectors = [list(map(float, row["embedding"])) for row in ordered]
            if len(vectors) != len(inputs):
                errors.append(
                    f"{host}: expected {len(inputs)} embeddings, received {len(vectors)}"
                )
                break
            usage = data.get("usage") or {}
            return EmbeddingResult(
                vectors=vectors,
                prompt_tokens=int(usage.get("prompt_tokens") or 0),
                total_tokens=int(usage.get("total_tokens") or usage.get("prompt_tokens") or 0),
                endpoint_host=host,
                latency_s=latency,
                model=model,
            )
    raise RuntimeError("All embeddings endpoints failed:\n  " + "\n  ".join(errors))
