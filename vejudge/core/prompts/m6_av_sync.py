"""M6 — Audio-Visual Sync (video). Three sub-dimensions (6a/6b/6c) + overall."""

from __future__ import annotations

from typing import Any

from .spec import PromptSpec

VERSION = "v1"

SCHEMA = {
    "voiceover_visual_match": {"score_1_to_5": "integer", "issues": ["string"], "reasoning": "string"},
    "voiceover_continuity": {"score_1_to_5": "integer", "issues": ["string"], "reasoning": "string"},
    "visual_continuity": {"score_1_to_5": "integer", "issues": ["string"], "reasoning": "string"},
    "overall_av_sync_score": "integer",
    "reasoning_lines": ["string", "string", "string"],
}


def build(sample: dict[str, Any]) -> PromptSpec:
    inp = sample.get("input") or {}
    user = f"""\
You are a specialist audio-visual quality judge for an automated video editing system.

Watch the attached video carefully with attention to both the AUDIO (voiceover/dialogue)
and the VISUALS (A-roll talking-head footage and B-roll cutaway footage). The video was
assembled by an algorithm in response to this user prompt:

"{inp.get('user_prompt', '')}"

Evaluate these three specific dimensions:

## 6a. Voiceover-Visual Match
Does the voiceover/dialogue content match what is shown on screen at the same time?
- When the speaker talks about a specific topic (e.g. "cutting onions"), is relevant
  footage (A-roll of them speaking or B-roll of onion cutting) shown?
- Are B-roll cutaway clips topically aligned with the voiceover playing over them?
- Major mismatches: voiceover about topic X while showing completely unrelated footage.

## 6b. Voiceover Continuity
Are there sudden pauses, awkward silences, abrupt mid-sentence cuts, or audio glitches
in the voiceover/dialogue track?
- Smooth: sentences flow naturally, no jarring gaps.
- Problematic: mid-word cuts, unnatural silence gaps (>1s) between sentences that were
  clearly stitched, audio pops or repeated words from bad splicing.

## 6c. Visual Continuity
Are there sudden pauses, freeze frames, black frames, repeated shots, or jarring visual
jump cuts in the video track?
- Smooth: cuts feel intentional, no frozen or black frames, clips transition cleanly.
- Problematic: freeze frames, black flashes between clips, identical shot repeated
  back-to-back, extreme jump cuts within the same clip.

Respond with JSON only (no markdown fences):
{{
  "voiceover_visual_match": {{
    "score_1_to_5": integer,
    "issues": [string],
    "reasoning": string
  }},
  "voiceover_continuity": {{
    "score_1_to_5": integer,
    "issues": [string],
    "reasoning": string
  }},
  "visual_continuity": {{
    "score_1_to_5": integer,
    "issues": [string],
    "reasoning": string
  }},
  "overall_av_sync_score": integer,
  "reasoning_lines": [string, string, string]
}}

Scoring rubric (each sub-dimension):
- 5: No issues detected -- smooth and well-matched throughout.
- 4: One minor issue that a casual viewer might not notice.
- 3: Noticeable issue that detracts from the viewing experience.
- 2: Multiple issues -- feels poorly assembled.
- 1: Severely broken -- unwatchable audio or visual track.

overall_av_sync_score: average of the three, rounded to nearest integer.
reasoning_lines: 2-3 sentences summarizing the biggest AV concerns (or lack thereof)."""
    return PromptSpec(system=None, user=user, schema=SCHEMA, version=VERSION)
