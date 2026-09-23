"""M2 — Render Failure (video). Is the rendered MP4 broken/unwatchable?"""

from __future__ import annotations

from typing import Any

from .spec import PromptSpec

VERSION = "v1"

SCHEMA = {
    "failure": "boolean",
    "severity": "none | minor | major",
    "reasoning_lines": ["string", "string", "string"],
    "evidence": ["string"],
}


def build(sample: dict[str, Any]) -> PromptSpec:
    inp = sample.get("input") or {}
    user = f"""\
You are an evaluation judge for an automated video editing system.

Watch the attached video and decide whether it is a FAILURE.

User prompt that the video should address:
"{inp.get('user_prompt', '')}"

A failure means:
- The video is broken, black, corrupt, or unwatchable
- The video content is completely unrelated to the prompt
- Severe audio/visual glitches that make it unusable

A NON-failure means the video is watchable and makes a reasonable attempt at the prompt,
even if imperfect. Minor quality issues are NOT failures.

Respond with JSON only (no markdown fences):
{{
  "failure": boolean,
  "severity": "none" | "minor" | "major",
  "reasoning_lines": [string, string, string],
  "evidence": [string]
}}
- reasoning_lines: exactly 2-3 sentences describing what you see, how it relates to the
  prompt, and why it passes or fails."""
    return PromptSpec(system=None, user=user, schema=SCHEMA, version=VERSION)
