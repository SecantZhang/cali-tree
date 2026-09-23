"""M1 — Assembly Failure (text). Judges the plan (notes + assembly_json)."""

from __future__ import annotations

import json
import os
from typing import Any

from .spec import PromptSpec

VERSION = "v1"

SCHEMA = {
    "failure": "boolean",
    "severity": "none | minor | major",
    "reasoning_lines": ["string", "string", "string"],
    "evidence": ["string"],
}

_SYSTEM = """\
You are an evaluation judge for an automated video assembly system.

Your task: decide whether the ASSEMBLY PLAN (notes JSON + structured assembly_json)
addresses the USER PROMPT. You are judging the *plan*, not the rendered video.

Inputs provided:
- user_prompt: what the user asked for
- assembly_json: final clip IDs, trimmed words, output transcript
- notes_excerpt: orchestration history (critic/editor iterations, pipeline status)
- a_roll_transcript_excerpt: source material the editor could pick from
- b_roll_captions_excerpt: available B-roll visual descriptions

Respond with JSON only (no markdown fences):
{
  "failure": boolean,
  "severity": "none" | "minor" | "major",
  "reasoning_lines": [string, string, string],
  "evidence": [string]
}
- failure=true means the plan does not address the prompt.
- severity: "none" if pass; "minor" if mostly addressed but meaningful gap; "major" if
  clearly wrong or core requirements missing.
- reasoning_lines: exactly 2-3 sentences. (1) What in the assembly/notes you observed.
  (2) How that maps to the prompt requirements. (3) Why that implies pass or fail."""


def _truncate_file(path: str, max_chars: int) -> str:
    if not path or not os.path.isfile(path):
        return ""
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read()[:max_chars]


def build(sample: dict[str, Any], *, notes_max_chars: int = 32000) -> PromptSpec:
    inp = sample.get("input") or {}
    out = sample.get("output") or {}
    notes_excerpt = _truncate_file(str(inp.get("notes_path", "")), notes_max_chars)
    user = json.dumps(
        {
            "user_prompt": inp.get("user_prompt", ""),
            "assembly_json": out.get("assembly_json") or {},
            "notes_excerpt": notes_excerpt,
            "a_roll_transcript_excerpt": str(inp.get("a_roll_transcript_text", ""))[:8000],
            "b_roll_captions_excerpt": str(inp.get("b_roll_captions_excerpt", ""))[:8000],
        },
        ensure_ascii=False,
        indent=2,
    )
    return PromptSpec(system=_SYSTEM, user=user, schema=SCHEMA, version=VERSION)
