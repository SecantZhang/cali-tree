"""M4 — Visual Prompt Alignment (video). 1-5: does the video visually fulfill the prompt?"""

from __future__ import annotations

from typing import Any

from .spec import PromptSpec

VERSION = "v1"

SCHEMA = {
    "score_1_to_5": "integer",
    "fully_aligned": "boolean",
    "missing_visual_aspects": ["string"],
    "reasoning_lines": ["string", "string", "string"],
}


def build(sample: dict[str, Any]) -> PromptSpec:
    inp = sample.get("input") or {}
    user = f"""\
You are an evaluation judge for an automated video editing system.

Watch the attached video and score how well it visually fulfills the user's prompt.

User prompt:
"{inp.get('user_prompt', '')}"

Evaluate whether what appears on screen matches the prompt:
- Does the video show the content the user asked for?
- Are visual elements (B-roll, A-roll, cuts) aligned with the request?
- Does timing/duration match if the prompt specifies it?

Respond with JSON only (no markdown fences):
{{
  "score_1_to_5": integer,
  "fully_aligned": boolean,
  "missing_visual_aspects": [string],
  "reasoning_lines": [string, string, string]
}}
Scoring rubric:
- 5: Every visual requirement met. What's on screen is exactly what the prompt asked for.
- 4: Minor gap -- mostly aligned but one small visual aspect missing or weak.
- 3: Important visual aspect missing or only partially shown.
- 2: Mostly off-brief -- video shows different content than requested.
- 1: Completely unrelated or empty.
- fully_aligned: true only if score is 5.
- reasoning_lines: exactly 2-3 sentences. What you see vs what was asked vs your score."""
    return PromptSpec(system=None, user=user, schema=SCHEMA, version=VERSION)
