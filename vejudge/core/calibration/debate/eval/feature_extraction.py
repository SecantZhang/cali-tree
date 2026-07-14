"""Cold feature extraction: the judge scores an item AND answers the shared
decision-questions, with no debate and no human label in view.

This is the hybrid execution path and the only step that makes a real (video) judge
call. The K bank questions are injected via ``extra_context`` (appended to the judge's
system prompt by ``Judge.run``); the judge is asked to add a ``decision_answers`` object
to its normal JSON. That extra key rides through the judge's own ``parsed`` output (the
validator ignores unknown keys), so no metric SCHEMA change is needed.

Per item the result is a feature vector ``[base_score, b1..bK]`` where each boolean is
*oriented*: 1 means "the condition that should RAISE the score is present" (answer ==
the question's ``raises_score_when``). Orientation is cosmetic for the tree but makes a
linear calibrator's coefficients read intuitively (positive => raises score).
"""

from __future__ import annotations

from typing import Any, Optional

from .....lm_engine.lm_template import LMEngine
from ....judge.parse import parse_json_object
from ....judge.registry import make_judge


def build_decision_extra_context(questions: list[dict[str, Any]]) -> str:
    lines = [f'  "q{i + 1}": true/false  // {q["question"]}' for i, q in enumerate(questions)]
    body = "\n".join(lines)
    return (
        "AFTER producing your normal scored JSON above, answer these calibration "
        "questions about THIS item as booleans, and include them in the SAME JSON object "
        "under a top-level key \"decision_answers\":\n"
        "\"decision_answers\": {\n"
        f"{body}\n"
        "}\n"
        "Answer each strictly true/false based on the actual input; do not change how you "
        "score — just answer the questions alongside your score."
    )


def _as_bool(v: Any) -> Optional[bool]:
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return bool(v)
    if isinstance(v, str):
        s = v.strip().lower()
        if s in ("true", "yes", "y", "1"):
            return True
        if s in ("false", "no", "n", "0"):
            return False
    return None


def extract_features(
    *,
    sample: dict[str, Any],
    metric_id: str,
    questions: list[dict[str, Any]],
    engine: LMEngine,
) -> dict[str, Any]:
    """Run the cold judge call and return
    ``{base_score, features: [base_score, b1..bK], booleans: [0/1..], raw_answers, missing}``.

    ``features`` is what the calibrators fit/predict on. ``missing`` lists question ids
    the judge failed to answer (defaulted to 0 / not-present)."""
    extra = build_decision_extra_context(questions) if questions else None
    result = make_judge(metric_id, engine).run(sample, extra_context=extra)

    parsed = result.get("parsed") or {}
    score_key = "overall_av_sync_score" if metric_id == "M6" else "score_1_to_5"
    base = parsed.get(score_key)
    base_score = float(base) if isinstance(base, (int, float)) and not isinstance(base, bool) else None

    answers = parsed.get("decision_answers")
    if not isinstance(answers, dict):
        # Some models nest it or drop it from `parsed`; re-parse the raw content.
        reparsed = parse_json_object(result.get("raw_content") or "")
        answers = (reparsed or {}).get("decision_answers") if isinstance(reparsed, dict) else {}
    answers = answers or {}

    booleans: list[int] = []
    raw_answers: dict[str, Any] = {}
    missing: list[str] = []
    for i, q in enumerate(questions):
        qid = f"q{i + 1}"
        b = _as_bool(answers.get(qid))
        raw_answers[qid] = answers.get(qid)
        if b is None:
            missing.append(qid)
            oriented = 0  # unanswered => treat the raising-condition as absent
        else:
            # Oriented: 1 when the answer matches the score-raising direction.
            raises_when_yes = q.get("raises_score_when", "yes") == "yes"
            oriented = 1 if (b == raises_when_yes) else 0
        booleans.append(oriented)

    features = ([base_score] if base_score is not None else [None]) + [float(x) for x in booleans]
    return {
        "item_id": sample.get("item_id"),
        "base_score": base_score,
        "booleans": booleans,
        "features": features,
        "raw_answers": raw_answers,
        "missing": missing,
    }
