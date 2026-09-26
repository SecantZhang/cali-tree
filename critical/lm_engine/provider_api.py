"""Wire formats for official OpenAI and Gemini APIs (no network side effects)."""
from __future__ import annotations

import re
from typing import Any, Optional
from urllib.parse import quote, urlparse


def api_provider(base: str, provider: Optional[str] = None) -> str:
    if provider in ("openai", "gemini"):
        return provider
    host = urlparse(base).hostname
    if host == "api.openai.com":
        return "openai"
    if host == "generativelanguage.googleapis.com" and not base.rstrip("/").endswith("/openai"):
        return "gemini"
    return "compatible"


def chat_request(base: str, token: str, model: str, messages: list[dict[str, Any]],
                 max_tokens: int, temperature: float, provider: Optional[str] = None):
    """Return URL, payload, headers, and response dialect for one completion."""
    dialect = api_provider(base, provider)
    headers = {"Content-Type": "application/json; charset=UTF-8"}
    if dialect != "gemini":
        payload = {"model": model, "messages": messages, "temperature": temperature}
        payload["max_completion_tokens" if dialect == "openai" else "max_tokens"] = max_tokens
        # These GPT versions allow sampling temperature with reasoning disabled.
        if dialect == "openai" and re.match(r"^gpt-5\.(?:1|2|4)(?:-(?:mini|nano))?(?:-\d{4}-\d{2}-\d{2})?$", model):
            payload["reasoning_effort"] = "none"
        elif dialect == "openai" and (model.startswith(("o1", "o3", "o4")) or model.startswith("gpt-5")):
            # Do not silently discard a requested experimental temperature.
            if temperature != 1:
                raise ValueError(f"{model} does not support this sampling configuration; use temperature=1 or a model supporting temperature (e.g. gpt-4.1 or gpt-5.4-mini)")
            payload.pop("temperature")
        headers["Authorization"] = f"Bearer {token}"
        return base.rstrip("/") + "/chat/completions", payload, headers, dialect

    contents, system_parts = [], []
    inline_size = 0
    for message in messages:
        content = message.get("content") or ""
        blocks = [{"type": "text", "text": content}] if isinstance(content, str) else content
        parts = []
        for block in blocks:
            if block.get("type") == "text":
                parts.append({"text": block["text"]})
            elif block.get("type") == "image_url":
                uri = block["image_url"]["url"]
                if not uri.startswith("data:") or ";base64," not in uri:
                    raise ValueError("Gemini media must be local image/video data, not an image_url HTTP URL")
                mime, encoded = uri[5:].split(";base64,", 1)
                parts.append({"inlineData": {"mimeType": mime, "data": encoded}})
                inline_size += len(encoded)
            else:
                raise ValueError(f"Unsupported Gemini content part: {block.get('type')!r}")
        role = message.get("role")
        if role in ("system", "developer"):
            system_parts.extend(parts)
        elif role in ("user", "assistant"):
            contents.append({"role": "model" if role == "assistant" else "user", "parts": parts})
        else:
            raise ValueError(f"Unsupported Gemini message role: {role!r}")
    # Conservative GenerateContent inline limit; avoid an opaque provider rejection.
    if inline_size > 19_000_000:
        raise ValueError("Gemini inline media exceeds the 20 MB request limit; use shorter clips or sampled image frames")
    payload = {"contents": contents, "generationConfig": {"maxOutputTokens": max_tokens, "temperature": temperature}}
    if system_parts:
        payload["systemInstruction"] = {"parts": system_parts}
    headers["x-goog-api-key"] = token
    model_id = quote(model.removeprefix("models/"), safe="-._")
    return base.rstrip("/") + f"/models/{model_id}:generateContent", payload, headers, dialect


def chat_response(data: dict, dialect: str, requested_model: str) -> tuple:
    """Normalize text, token accounting, and the returned model identifier."""
    if dialect == "gemini":
        candidates = data.get("candidates") or []
        parts = ((candidates[0].get("content") or {}).get("parts") or []) if candidates else []
        content = "".join(p.get("text", "") for p in parts if not p.get("thought"))
        if not content:
            reason = data.get("promptFeedback") or (candidates[0].get("finishReason") if candidates else "no candidates")
            raise RuntimeError(f"Gemini returned no text: {reason}")
        usage = data.get("usageMetadata") or {}
        prompt = int(usage.get("promptTokenCount") or 0)
        completion = int(usage.get("candidatesTokenCount") or 0) + int(usage.get("thoughtsTokenCount") or 0)
        return content, prompt, completion, int(usage.get("totalTokenCount") or prompt + completion), str(data.get("modelVersion") or requested_model)
    choices = data.get("choices") or []
    content = (choices[0].get("message") or {}).get("content") if choices else None
    usage = data.get("usage") or {}
    return content, int(usage.get("prompt_tokens") or 0), int(usage.get("completion_tokens") or 0), int(usage.get("total_tokens") or 0), str(data.get("model") or requested_model)
