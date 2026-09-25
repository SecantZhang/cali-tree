"""``LMEngine`` — the abstract base every engine subclasses.

Contract (per CLAUDE.md): ``generate(prompt, media_inputs, schema) -> dict``.
Media inputs are *preprocessed references* (video/frame paths or transcript strings),
never raw bytes passed around by callers. Every call is logged to ``llm-histories.log``
when a history writer is attached.

The base class implements ``generate`` against the shared OpenAI-compatible transport;
subclasses only declare their default model and modality.
"""

from __future__ import annotations

import json
from abc import ABC
from typing import Any, Optional, TypedDict

from .. import openai_compat
from ..creds import PlutoCreds, load_creds


class MediaInput(TypedDict, total=False):
    type: str  # "video" | "image" | "text"
    path: str  # for video/image
    text: str  # for text


class LMEngine(ABC):
    """Base engine. Subclasses set ``name`` and ``default_model``."""

    name: str = "base"
    default_model: str = ""
    supports_video: bool = False

    def __init__(
        self,
        *,
        model: Optional[str] = None,
        creds: Optional[PlutoCreds] = None,
        history: Optional[Any] = None,  # logging.LLMHistoryWriter
        max_tokens: int = 4096,
        temperature: float = 0.3,
        timeout: int = 300,
    ) -> None:
        self.model = model or self.default_model
        self._creds = creds
        self.history = history
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.timeout = timeout

    # --- lazy creds so constructing an engine never hits the filesystem -------
    @property
    def creds(self) -> PlutoCreds:
        if self._creds is None:
            self._creds = load_creds(engine=self.name)
        return self._creds

    # --- message assembly -----------------------------------------------------
    def _build_messages(
        self,
        prompt: str,
        media_inputs: Optional[list[MediaInput]],
        system: Optional[str],
    ) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []
        if system:
            messages.append({"role": "system", "content": system})

        parts: list[dict[str, Any]] = [openai_compat.text_part(prompt)]
        for m in media_inputs or []:
            mtype = m.get("type")
            if mtype == "video":
                if not self.supports_video:
                    raise ValueError(
                        f"Engine '{self.name}' does not support video input"
                    )
                parts.append(openai_compat.video_part(m["path"]))
            elif mtype == "image":
                parts.append(openai_compat.image_part(m["path"]))
            elif mtype == "text":
                parts.append(openai_compat.text_part(m.get("text", "")))
            else:
                raise ValueError(f"Unknown media input type: {mtype!r}")

        # If there is no media, a plain string content keeps payloads small.
        if len(parts) == 1:
            messages.append({"role": "user", "content": prompt})
        else:
            messages.append({"role": "user", "content": parts})
        return messages

    # --- public API -----------------------------------------------------------
    def generate(
        self,
        prompt: str,
        media_inputs: Optional[list[MediaInput]] = None,
        schema: Optional[dict[str, Any]] = None,
        *,
        system: Optional[str] = None,
        model: Optional[str] = None,
    ) -> dict[str, Any]:
        """Run one completion. Returns content + token usage (+ parsed JSON if ``schema``).

        ``schema`` is advisory: when provided, the engine attempts to ``json.loads`` the
        response and returns it under ``parsed`` (None on failure). Strict validation is
        the judge layer's job.
        """
        chosen_model = model or self.model
        messages = self._build_messages(prompt, media_inputs, system)

        error: Optional[str] = None
        result: Optional[openai_compat.ChatResult] = None
        try:
            result = openai_compat.chat_completion(
                endpoints=self.creds.endpoints,
                token=self.creds.token,
                model=chosen_model,
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                timeout=self.timeout,
                provider=self.creds.provider,
            )
        except Exception as e:  # noqa: BLE001 - logged & surfaced to caller
            error = f"{type(e).__name__}: {e}"

        content = result.content if result else None
        if self.history is not None:
            self.history.record(
                engine=self.name,
                model=result.model if result else chosen_model,
                prompt=(system + "\n\n" + prompt) if system else prompt,
                response=content,
                media_inputs=media_inputs,
                prompt_tokens=result.prompt_tokens if result else 0,
                completion_tokens=result.completion_tokens if result else 0,
                total_tokens=result.total_tokens if result else 0,
                latency_s=result.latency_s if result else None,
                endpoint=result.endpoint_host if result else None,
                error=error,
            )

        if error is not None:
            raise RuntimeError(error)

        out: dict[str, Any] = {
            "content": content,
            "model": result.model,  # type: ignore[union-attr]
            "engine": self.name,
            "promptTokens": result.prompt_tokens,  # type: ignore[union-attr]
            "completionTokens": result.completion_tokens,  # type: ignore[union-attr]
            "totalTokens": result.total_tokens,  # type: ignore[union-attr]
            "latencySeconds": result.latency_s,  # type: ignore[union-attr]
            "endpointHost": result.endpoint_host,  # type: ignore[union-attr]
        }
        if schema is not None:
            try:
                out["parsed"] = json.loads(content) if content else None
            except (json.JSONDecodeError, TypeError):
                out["parsed"] = None
        return out
