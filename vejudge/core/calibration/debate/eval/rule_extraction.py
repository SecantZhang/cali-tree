"""Post-debate rule extraction: turn one A/B debate transcript into candidate
reusable boolean decision-questions.

Kept separate from the debate itself (the debate argues; this distills) so the mined
questions have a consistent, machine-parseable shape regardless of how the debate
phrased things. One low-temperature text call per item. Deterministic parsing with a
graceful empty fallback — a debate where the judge held up yields no questions.
"""

from __future__ import annotations

import json
from typing import Any

from .....lm_engine.lm_template import LMEngine
from ....judge.parse import parse_json_object

_EXTRACT_VERSION = "ab-extract-v1"

_SYSTEM = """\
You extract reusable evaluation rules from a debate transcript. Read the debate between \
a judge and a human-proxy reviewer about where the judge's score diverged from human \
raters. Output ONLY the general, reusable decision rules the debate surfaced -- each as \
a yes/no QUESTION a fresh judge could answer about ANY item, plus which answer should \
push the score. Do NOT reference this specific clip. If the debate concluded the judge \
was right (no correction needed), return an empty list."""


def _user(transcript_text: str, metric_id: str) -> str:
    return f"""\
Metric under review: {metric_id}

Debate transcript:
{transcript_text}

Respond with JSON only (no markdown fences):
{{
  "questions": [
    {{
      "question": "a general yes/no question, e.g. 'Does the judge penalize repetition the user's own script explicitly requested?'",
      "raises_score_when": "yes" | "no"
    }}
  ]
}}
- Each question must be answerable for ANY item, never mentioning this specific clip.
- "raises_score_when": the answer indicating the judge under-scored (score should go up).
- Return {{"questions": []}} if the debate found no correction is warranted."""


def extract_candidate_questions(
    *,
    transcript_text: str,
    metric_id: str,
    engine: LMEngine,
) -> list[dict[str, Any]]:
    """Return a list of ``{"question": str, "raises_score_when": "yes"|"no"}``.

    Empty list when the debate warranted no correction, when the call errors, or when the
    response is unparseable — an item that yields no rule simply contributes no feature.
    """
    try:
        out = engine.generate(_user(transcript_text, metric_id), system=_SYSTEM)
    except Exception:  # noqa: BLE001 - a failed extraction just yields no candidates
        return []
    parsed = parse_json_object(out.get("content") or "")
    if not isinstance(parsed, dict):
        return []
    questions: list[dict[str, Any]] = []
    for q in parsed.get("questions") or []:
        if not isinstance(q, dict):
            continue
        text = str(q.get("question") or "").strip()
        raises = str(q.get("raises_score_when") or "yes").strip().lower()
        if text and raises in ("yes", "no"):
            questions.append({"question": text, "raises_score_when": raises})
    return questions
