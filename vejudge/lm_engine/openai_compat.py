"""Shared OpenAI-compatible ``/chat/completions`` transport with endpoint failover.

The Pluto gateway is OpenAI-compatible: text and video both go through
``/chat/completions``; video is sent as a base64 ``data:video/mp4`` image_url part.
This module is provider-agnostic — engines build the ``messages`` and pick the model.
"""

from __future__ import annotations

import base64
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

import requests


@dataclass
class ChatResult:
    content: Optional[str]
    prompt_tokens: int
    completion_tokens: int
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
# 429 rate limit, 408 request timeout, and 5xx upstream errors (the Pluto proxy returns
# 502/503/504 when its Gemini upstream resets or read-times-out on large video payloads).
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
) -> ChatResult:
    """POST to the first reachable endpoint, falling over to the rest in order.

    Transient failures — HTTP 429/408/5xx and network errors (connection reset, read
    timeout) — are retried on the *same* endpoint up to ``max_retries`` times (honoring
    ``Retry-After`` on 429, else exponential backoff). Only after a transient error
    exhausts its retries do we fall over to the next endpoint. Non-retryable responses
    (e.g. 400/401/404) fall over immediately. Raises only if all endpoints fail.
    """
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    headers = {
        "Content-Type": "application/json; charset=UTF-8",
        "Authorization": f"Bearer {token}",
    }

    errors: list[str] = []
    for base in endpoints:
        url = base.rstrip("/") + "/chat/completions"
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
                if attempt < max_retries:
                    time.sleep(_retry_after_seconds(resp, attempt))
                    continue
                errors.append(f"{host}: HTTP {resp.status_code} {resp.text[:300]}")
                break  # exhausted -> next endpoint
            if resp.status_code >= 400:
                errors.append(f"{host}: HTTP {resp.status_code} {resp.text[:500]}")
                break  # non-retryable -> next endpoint

            data = resp.json()
            choices = data.get("choices") or []
            content: Optional[str] = None
            if choices and isinstance(choices[0], dict):
                msg = choices[0].get("message") or {}
                if isinstance(msg, dict):
                    content = msg.get("content")
            usage = data.get("usage") or {}
            return ChatResult(
                content=content,
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
                endpoint_host=host,
                latency_s=latency,
                model=model,
            )

    raise RuntimeError(
        "All chat/completions endpoints failed:\n  " + "\n  ".join(errors)
    )
