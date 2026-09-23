"""Deployment-safe semantic questions anchored in the human evaluation rubric.

Debate mining is intentionally retained, but debates tend to surface only one side of the
calibration problem (usually reasons a judge under-scored).  These fixed questions ensure
the independent critic also measures the observable rubric facets needed to distinguish
items at deployment time.  They contain no item labels, score targets, or fitted values.
"""

from __future__ import annotations

from typing import Any


_QUESTIONS: dict[str, list[tuple[str, str]]] = {
    "M3": [
        ("video_addresses_prompt", "Does the edit satisfy every explicit part of the user's request?"),
    ],
    "M5": [
        ("story_flow_voiceover", "Does the spoken narrative progress coherently without confusing jumps or omissions?"),
        ("story_flow_visuals", "Does the visual sequence form a coherent, easy-to-follow progression?"),
        ("section_placement_opening", "Does the opening establish the topic and context at an appropriate time?"),
        ("section_placement_middle", "Does the middle develop and order the main content effectively?"),
        ("section_placement_closing", "Does the ending provide an appropriately complete resolution or conclusion?"),
        ("story_flow_visuals", "Is the pacing appropriate, without sections feeling persistently rushed or stalled?"),
        ("story_flow_visuals", "Do cuts and transitions preserve temporal and narrative continuity?"),
        ("story_flow_voiceover", "Is the narrative understandable without persistent audio or visual defects disrupting it?"),
    ],
    "M6": [
        ("voiceover_matches_visuals", "Do the visible shots consistently support the concurrent spoken content?"),
        ("abrupt_cutoffs_voiceover", "Does the voiceover remain continuous without abrupt cutoffs or unexplained gaps?"),
        ("abrupt_cutoffs_video", "Do the visuals remain continuous without freezes, black frames, or abrupt interruptions?"),
    ],
}


def rubric_questions(metric_id: str) -> list[dict[str, Any]]:
    """Return target-blind observable questions for ``metric_id`` in stable order."""
    return [
        {
            "question": question,
            "raises_score_when": "yes",
            "scope": "item_quality",
            "semantic_key": f"rubric:{dimension}",
            "metric_ids": [metric_id],
        }
        for dimension, question in _QUESTIONS.get(metric_id, [])
    ]


def combine_with_debate_bank(
    *, metric_id: str, debate_bank: list[dict[str, Any]], max_questions: int,
) -> list[dict[str, Any]]:
    """Keep rubric coverage first, then fill remaining capacity with debate rules."""
    anchors = rubric_questions(metric_id)[:max_questions]
    out = list(anchors)
    seen = {entry["question"].strip().lower() for entry in out}
    for entry in debate_bank:
        text = str(entry.get("question") or "").strip()
        if not text or text.lower() in seen:
            continue
        out.append({**entry, "scope": entry.get("scope") or "judge_reasoning"})
        seen.add(text.lower())
        if len(out) >= max_questions:
            break
    return out


def combine_joint_banks(
    *, metric_ids: list[str], debate_banks: dict[str, list[dict[str, Any]]],
    max_questions_per_metric: int,
) -> list[dict[str, Any]]:
    """Build one stable prompt-aware bank while preserving metric applicability.

    A critic only answers questions belonging to the task's judge prompt. The explicit
    ``metric_ids`` field lets the joint feature builder represent non-applicable questions
    as structural zeros rather than asking an M3 completeness critic about M6 AV sync.
    """
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for metric_id in sorted(set(metric_ids)):
        combined = combine_with_debate_bank(
            metric_id=metric_id,
            debate_bank=debate_banks.get(metric_id, []),
            max_questions=max_questions_per_metric,
        )
        for entry in combined:
            text = str(entry.get("question") or "").strip()
            key = (metric_id, text.lower())
            if not text or key in seen:
                continue
            out.append({**entry, "metric_ids": [metric_id]})
            seen.add(key)
    return out
