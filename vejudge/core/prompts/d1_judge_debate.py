"""D1 -- judge-agent debate turn: defend or revise the original judge score under
scrutiny from the human-proxy agent (see ``d2_human_proxy_debate``).

Metric-agnostic: regardless of which M1-M6 metric is under debate, this turn always
produces a single top-level ``score_1_to_5`` (the debate's own schema, independent of
the original metric's native schema, e.g. M6's nested ``overall_av_sync_score``).
"""

from __future__ import annotations

from typing import Any

from .spec import PromptSpec
from ..rubric.definitions import metric_definition

VERSION = "v3"

SCHEMA = {
    "score_1_to_5": "integer",
    "revised": "boolean",
    "reasoning_lines": ["string", "string", "string"],
    "evidence": ["string"],
    "semantic_summary": {
        "principle": "string", "applies_when": "string",
        "evidence_to_check": ["string"], "scoring_guidance": "string",
    },
}
OPTIONAL_FIELDS = {"semantic_summary"}


def build(
    *,
    sample: dict[str, Any],
    metric_id: str,
    original_output: dict[str, Any],
    transcript_text: str,
    round_no: int,
) -> PromptSpec:
    inp = sample.get("input") or {}
    original_parsed = original_output.get("parsed") or {}

    system = """\
You are the same evaluation judge that produced the original score below. A skeptical \
human-annotator reviewer is now scrutinizing that score. Defend it if it holds up, but \
revise it if the critique points to something concrete you missed in the actual input \
-- do not cave to pressure alone, and do not revise without citing specific evidence. \
Do not alternate between score interpretations unless a genuinely new observable fact \
appears; preserve unresolved counter-considerations explicitly."""

    transcript_block = transcript_text or "(no prior debate turns yet)"

    user = f"""\
Metric under debate: {metric_id}
{metric_definition(metric_id)}

User prompt:
"{inp.get('user_prompt', '')}"

Your original scored output:
{original_parsed}

Debate so far:
{transcript_block}

This is round {round_no}. Respond with JSON only (no markdown fences):
{{
  "score_1_to_5": integer,
  "revised": boolean,
  "reasoning_lines": [string, string, string],
  "evidence": [string],
  "semantic_summary": {{
    "principle": "a reusable evaluation rule, with no target score",
    "applies_when": "the observable conditions where it matters",
    "evidence_to_check": ["concrete editing facts; never human ratings"],
    "scoring_guidance": "how to weigh those facts without prescribing a score"
  }}
}}
- "revised": true only if this score differs from your immediately preceding score in
  this debate.
- "evidence": concrete, specific points from the input that justify holding or revising
  the score -- not general reassurance.
- "reasoning_lines": exactly 2-3 sentences explaining your score in light of the
  critique.
- "semantic_summary" must generalize the negotiated lesson and must not mention human
  ratings, rating distributions, target scores, or correction magnitudes."""

    return PromptSpec(
        system=system, user=user, schema=SCHEMA,
        optional_fields=OPTIONAL_FIELDS, version=VERSION,
    )
