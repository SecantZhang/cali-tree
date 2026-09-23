"""M3 — Prompt Completeness (text). 1-5: does the plan cover every requirement?"""

from __future__ import annotations

import json
from typing import Any

from ..rubric.definitions import metric_definition
from .spec import PromptSpec

VERSION = "v1"

SCHEMA = {
    "score_1_to_5": "integer",
    "fully_complete": "boolean",
    "missing_aspects": ["string"],
    "reasoning_lines": ["string", "string", "string"],
}


def build(sample: dict[str, Any]) -> PromptSpec:
    inp = sample.get("input") or {}
    out = sample.get("output") or {}
    definition = metric_definition("M3")

    system = f"""\
You are an MLLM-as-judge evaluator for video assembly quality.

Metric: Prompt completeness (text-only evaluation of the assembly plan)
Definition from the project metric catalog:
{definition}

You are given the user prompt, the pool of source A-roll transcript data (what could
be selected from), and the structured output assembly (selected clips, final word-level
view, output transcript). You are judging the PLAN, not watching a video.

Task: Decide whether the assembly satisfies *every part* of the user request that pertains
to content selection and inclusion. If the prompt demands edits you cannot verify from text
(e.g. exact duration), estimate from transcript length and timeline hints.

Respond with JSON only (no markdown fences):
{{
  "score_1_to_5": integer,
  "fully_complete": boolean,
  "missing_aspects": [string],
  "reasoning_lines": [string, string, string]
}}
Scoring rubric:
- 5: Every explicit content requirement in the prompt is reflected in the assembly.
- 4: Minor gap or ambiguity -- one small aspect weakly covered.
- 3: Important aspect missing or only partially covered.
- 2: Mostly off-brief -- assembly addresses a different goal.
- 1: Unrelated or empty.
- fully_complete: true only if score is 5.
- reasoning_lines: exactly 2-3 sentences. List prompt requirements, trace to assembly
  evidence, state why the score follows."""

    user = json.dumps(
        {
            "user_prompt": inp.get("user_prompt", ""),
            "source_a_roll_pool_excerpt": str(inp.get("a_roll_transcript_text", ""))[:24000],
            "assembly_json": out.get("assembly_json") or {},
            "initial_timeline_text_head": str(inp.get("initial_timeline_text", ""))[:4000],
        },
        ensure_ascii=False,
        indent=2,
    )
    return PromptSpec(system=system, user=user, schema=SCHEMA, version=VERSION)
