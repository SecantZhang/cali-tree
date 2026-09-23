"""Tag mined free-text rules to failure-mode concepts — the bridge between the two
vocabularies.

The mined ``qN`` questions (``rule_extraction`` / ``question_bank``) are free text with no
ontology grounding, while the fixed ``FAILURE_MODE_TAXONOMY`` concepts are what the semantic
decision tree splits on. One low-temperature LLM call maps each canonical question to its
nearest taxonomy key (or None when it fits none), so a critic-answered rule can become a
concept-labeled feature (``rule:<key>``). Deterministic empty fallback: on error / an
unparseable response, every question is left untagged (contributes no concept feature).
"""

from __future__ import annotations

from typing import Any, Optional

from .....lm_engine.lm_template import LMEngine
from ....judge.parse import parse_json_object
from ....prompts.d2_human_proxy_debate import FAILURE_MODE_TAXONOMY
from .....postprocessing.align import ALIGNMENT

_TAG_VERSION = "concept-tag-v2-rubric"

_CONCEPT_LINES = "\n".join(f"- {k}: {v}" for k, v in FAILURE_MODE_TAXONOMY.items())
_RUBRIC_LINES = "\n".join(f"- rubric:{key}" for key in ALIGNMENT)

_SYSTEM = f"""\
You map each evaluation question to the ONE judge failure-mode concept it most directly
tests, from this fixed taxonomy:
{_CONCEPT_LINES}

Questions that directly measure an evaluation dimension may instead use one of these
rubric keys:
{_RUBRIC_LINES}

If a question fits none of them, return null for that question. Do not invent new concept
keys — use only the keys listed above."""


def _user(bank: list[dict[str, Any]]) -> str:
    listed = "\n".join(f'  {i + 1}. "{q["question"]}"' for i, q in enumerate(bank))
    return f"""\
Questions:
{listed}

Respond with JSON only (no markdown fences): a top-level "concepts" array with one entry
per question (in order), each either a taxonomy key string or null:
{{"concepts": [{{"index": 1, "key": "audio_neglect" | null}}, ...]}}"""


def tag_questions_to_concepts(
    *, bank: list[dict[str, Any]], engine: LMEngine
) -> list[Optional[str]]:
    """Return one entry per bank question (same order): a valid taxonomy key or None.

    Falls back to all-None on empty bank, a failed call, an unparseable response, or any
    key not in the taxonomy — an untagged question simply contributes no concept feature.
    """
    if not bank:
        return []
    fallback: list[Optional[str]] = [
        entry.get("semantic_key") if _valid_key(entry.get("semantic_key")) else None
        for entry in bank
    ]
    try:
        out = engine.generate(_user(bank), system=_SYSTEM)
        parsed = parse_json_object(out.get("content") or "")
    except Exception:  # noqa: BLE001 - a failed/unparseable tagging leaves everything untagged
        return fallback
    if not isinstance(parsed, dict):
        return fallback
    entries = parsed.get("concepts")
    if not isinstance(entries, list):
        return fallback

    tags = list(fallback)
    for e in entries:
        if not isinstance(e, dict):
            continue
        idx = e.get("index")
        key = e.get("key")
        if isinstance(idx, int) and 1 <= idx <= len(bank):
            if fallback[idx - 1] is None:
                tags[idx - 1] = key if _valid_key(key) else None
    return tags


def _valid_key(key: Any) -> bool:
    return key in FAILURE_MODE_TAXONOMY or (
        isinstance(key, str)
        and key.startswith("rubric:")
        and key.removeprefix("rubric:") in ALIGNMENT
    )
