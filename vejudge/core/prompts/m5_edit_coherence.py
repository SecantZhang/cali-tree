"""M5 — Edit Coherence (video). 1-5: flow, pacing, watchability."""

from __future__ import annotations

from typing import Any

from .spec import PromptSpec

VERSION = "v1"

SCHEMA = {
    "score_1_to_5": "integer",
    "issues": ["string"],
    "reasoning_lines": ["string", "string", "string"],
}


def build(sample: dict[str, Any]) -> PromptSpec:
    inp = sample.get("input") or {}
    user = f"""\
You are an evaluation judge for an automated video editing system.

Watch the attached video and score the EDIT COHERENCE -- how well it flows as a
watchable piece of content.

User prompt (for audience/context):
"{inp.get('user_prompt', '')}"

Evaluate:
- Flow: do clips transition smoothly without jarring jumps?
- Pacing: is the rhythm appropriate for the stated audience (e.g. "social media" = snappy)?
- Audio continuity: does the voiceover/dialogue flow naturally without awkward cuts?
- Watchability: would a viewer find this engaging and easy to follow?

Respond with JSON only (no markdown fences):
{{
  "score_1_to_5": integer,
  "issues": [string],
  "reasoning_lines": [string, string, string]
}}
Scoring rubric:
- 5: Professional quality -- smooth flow, good pacing, clean audio, highly watchable.
- 4: Good overall but one minor issue (e.g. slightly awkward transition).
- 3: Noticeable issues that hurt watchability (e.g. choppy pacing, abrupt cuts).
- 2: Multiple issues -- hard to watch, disjointed, poor audio continuity.
- 1: Unwatchable -- no coherent flow.
- reasoning_lines: exactly 2-3 sentences. What you observed, what works/doesn't, your score."""
    return PromptSpec(system=None, user=user, schema=SCHEMA, version=VERSION)
