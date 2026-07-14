"""Aggregate per-item candidate questions into one small shared decision-node bank.

The individual A/B debates each mine their own candidate boolean questions, often
phrasing the same underlying rule differently. This canonicalizes them (one LLM call)
into a small (K≈3-5) deduped set of reusable questions — the shared feature vocabulary
the fitted tree/calibrator will use.

Methodological caveat (surfaced, not hidden): the bank is mined from ALL items,
including any held out in a later LOO fold, so the *feature space* is shared across
folds; only the tree *fit* is held-out-honest. ``build_question_bank`` accepts an
explicit candidate list so a caller can re-mine per fold (``--remine-per-fold``) for a
strictly leak-free variant.
"""

from __future__ import annotations

import json
from typing import Any

from .....lm_engine.lm_template import LMEngine
from ....judge.parse import parse_json_object

_BANK_VERSION = "ab-bank-v1"

_SYSTEM = """\
You consolidate a list of candidate evaluation questions (mined from separate debates) \
into a SMALL canonical set. Merge questions that express the same underlying rule, drop \
near-duplicates and one-offs, and keep only general, reusable yes/no questions a fresh \
judge could answer about any item. Prefer 3-5 questions total. Preserve, for each kept \
question, which answer should raise the score."""


def _user(candidates: list[dict[str, Any]], max_questions: int) -> str:
    listed = "\n".join(
        f'- "{c["question"]}" (raises score when: {c.get("raises_score_when", "yes")})'
        for c in candidates
    )
    return f"""\
Candidate questions from the debates:
{listed}

Respond with JSON only (no markdown fences):
{{
  "questions": [
    {{"question": "canonical general yes/no question", "raises_score_when": "yes" | "no"}}
  ]
}}
- Keep at most {max_questions} questions; merge duplicates; drop item-specific one-offs.
- Order from most to least broadly applicable."""


def build_question_bank(
    *,
    candidates: list[dict[str, Any]],
    engine: LMEngine,
    max_questions: int = 5,
) -> list[dict[str, Any]]:
    """Canonicalize ``candidates`` (each ``{"question", "raises_score_when"}``) into a
    small deduped bank. Returns [] if there were no candidates or the call fails."""
    if not candidates:
        return []
    try:
        out = engine.generate(_user(candidates, max_questions), system=_SYSTEM)
    except Exception:  # noqa: BLE001
        # Fall back to a deterministic dedup on exact question text rather than lose all.
        return _dedup_fallback(candidates, max_questions)
    parsed = parse_json_object(out.get("content") or "")
    if not isinstance(parsed, dict) or not parsed.get("questions"):
        return _dedup_fallback(candidates, max_questions)
    bank: list[dict[str, Any]] = []
    for q in parsed["questions"]:
        if not isinstance(q, dict):
            continue
        text = str(q.get("question") or "").strip()
        raises = str(q.get("raises_score_when") or "yes").strip().lower()
        if text and raises in ("yes", "no"):
            bank.append({"question": text, "raises_score_when": raises})
    return bank[:max_questions] or _dedup_fallback(candidates, max_questions)


def _dedup_fallback(candidates: list[dict[str, Any]], max_questions: int) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for c in candidates:
        key = c["question"].strip().lower()
        if key and key not in seen:
            seen.add(key)
            out.append({"question": c["question"].strip(),
                        "raises_score_when": c.get("raises_score_when", "yes")})
        if len(out) >= max_questions:
            break
    return out
