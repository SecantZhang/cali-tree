"""D2 -- human-proxy debate turn: a skeptical strict human-annotator persona critiques
the judge's score, armed with the known judge failure-mode taxonomy (docs/research.md)
and, when available, a retrieved real human annotation note for grounding (the
"hybrid persona + optional retrieval" design).
"""

from __future__ import annotations

from typing import Any, Optional

from .spec import PromptSpec

VERSION = "v1"

# Fixed vocabulary of judge failure modes. Owned here (prompt content) and imported by
# vejudge.core.calibration.debate.schema to normalize/count ``cited_failure_modes``.
FAILURE_MODE_TAXONOMY: dict[str, str] = {
    "surface_realism_bias": "Rewards visually clean outputs that ignore the instruction.",
    "frame_only_blindness": "Misses flicker, motion defects, or other temporal issues.",
    "audio_neglect": "Ignores the audio track entirely.",
    "source_drift_blindness": "Misses unintended changes to the source material.",
    "overconfident_rationale": "States a rationale without pointing to concrete evidence.",
    "scale_drift": "Score meaning drifts across prompts or model families.",
    "long_video_compression": "Loses detail when summarizing a long video.",
    "position_bias": "Prefers a candidate due to its ordering, not its content.",
    "self_bias": "Favors outputs from a related model family.",
    "category_imbalance": "Over- or under-scores based on edit category, not quality.",
}

_TAXONOMY_LINES = "\n".join(f"- {k}: {v}" for k, v in FAILURE_MODE_TAXONOMY.items())

SCHEMA = {
    "score_1_to_5": "integer",
    "agrees_with_judge": "boolean",
    "critique_lines": ["string", "string", "string"],
    "cited_failure_modes": ["string"],
}


def build(
    *,
    sample: dict[str, Any],
    metric_id: str,
    original_output: dict[str, Any],
    transcript_text: str,
    round_no: int,
    retrieved_note: Optional[str],
) -> PromptSpec:
    inp = sample.get("input") or {}
    original_parsed = original_output.get("parsed") or {}

    system = f"""\
You are a skeptical, strict human annotator reviewing an AI judge's score for a video \
editing evaluation. You are armed with a known list of judge failure modes:
{_TAXONOMY_LINES}

Your job: find the strongest concrete reason the judge's score is wrong or \
overconfident, citing evidence from the actual sample -- not general skepticism. If the \
score genuinely holds up, say so."""

    if retrieved_note:
        grounding_block = (
            "A real human annotator's note on a similar past item is provided below as "
            "supporting evidence, not a hard override:\n"
            f'"{retrieved_note}"'
        )
    else:
        grounding_block = (
            "No similar historical human annotation was found for this item/category -- "
            "rely on the persona and failure-mode taxonomy above only."
        )

    transcript_block = transcript_text or "(no prior debate turns yet)"

    user = f"""\
Metric under debate: {metric_id}

User prompt:
"{inp.get('user_prompt', '')}"

The judge's current scored output:
{original_parsed}

{grounding_block}

Debate so far:
{transcript_block}

This is round {round_no}. Respond with JSON only (no markdown fences):
{{
  "score_1_to_5": integer,
  "agrees_with_judge": boolean,
  "critique_lines": [string, string, string],
  "cited_failure_modes": [string]
}}
- "cited_failure_modes": zero or more keys from the failure-mode list above (use the
  exact keys, e.g. "surface_realism_bias"), only when genuinely applicable.
- "critique_lines": exactly 2-3 sentences, concrete and evidence-based."""

    return PromptSpec(system=system, user=user, schema=SCHEMA, version=VERSION)
