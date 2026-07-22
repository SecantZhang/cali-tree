"""Independent-critic answering of the rule-bank booleans — the fix for the null result.

The cold-self-answer approach (`feature_extraction`) asked the *same judge* whether it
committed each flagged error; it denied them all (all-zero features). Here a **separate
critic** — a different LM given the item and the judge's own rationale, explicitly told it
is auditing, not re-scoring — answers each rule boolean. The critic being distinct from the
judge is the whole point; a judge won't self-incriminate, an auditor will.

In v2, a video-capable critic also receives the rendered edit. This is essential for
questions about whether an asserted audio/visual flaw is real, localized, or severe;
assembly metadata and the judge's prose alone cannot establish those facts. Text-only
engines retain the previous target-blind fallback.
"""

from __future__ import annotations

from typing import Any

from .....lm_engine.lm_template import LMEngine
from ....judge.parse import parse_json_object
from .feature_extraction import _as_bool

_CRITIC_VERSION = "rule-critic-v3-graded-semantic"

_SYSTEM = """\
You are an independent semantic reviewer of a video edit and its AI-judge evaluation.
Questions marked item_quality ask about observable properties of the edit itself; questions
marked judge_reasoning audit the judge's reasoning. When the rendered video is attached,
inspect it directly and treat it as authoritative for audio/visual claims. For every answer,
give true/false plus evidence strength from 0 (uncertain/unobservable) to 3 (unambiguous),
and one short observable justification. Do not infer a human rating or target score."""


def build_critic_prompt(
    sample: dict[str, Any], judge_rationale: str, questions: list[dict[str, Any]]
) -> str:
    inp = sample.get("input") or {}
    out = sample.get("output") or {}
    numbered = "\n".join(f'  "q{i + 1}": {{"answer": true/false, "strength": 0|1|2|3, '
                         f'"evidence": "short observable justification"}}  // '
                         f'[{q.get("scope", "judge_reasoning")}] {q["question"]}'
                         for i, q in enumerate(questions))
    return f"""\
User's request:
"{inp.get('user_prompt', '')}"

The assembled edit under review:
{out.get('assembly_json') or out.get('output_transcript') or out}

The judge's stated rationale (what you are auditing — NOT re-scoring):
{judge_rationale}

Answer each scoped question in a JSON object only (no markdown fences), under a top-level
key "decision_answers":
{{
"decision_answers": {{
{numbered}
}}
}}"""


def extract_critic_features(
    *,
    sample: dict[str, Any],
    judge_rationale: str,
    questions: list[dict[str, Any]],
    critic_engine: LMEngine,
) -> dict[str, Any]:
    """Return backward-compatible booleans plus graded signed semantic values.

    ``semantic_values`` is in [-1, 1]: positive means evidence for the score-raising
    condition, negative means evidence against it, and magnitude is evidence strength.
    """
    if not questions:
        return {"booleans": [], "raw_answers": {}, "missing": []}
    prompt = build_critic_prompt(sample, judge_rationale, questions)
    answers: dict[str, Any] = {}
    video_path = (sample.get("output") or {}).get("output_video_path")
    media_inputs = None
    if video_path and bool(getattr(critic_engine, "supports_video", False)):
        media_inputs = [{"type": "video", "path": str(video_path)}]
    try:
        out = critic_engine.generate(prompt, media_inputs=media_inputs, system=_SYSTEM)
        parsed = parse_json_object(out.get("content") or "")
        if isinstance(parsed, dict) and isinstance(parsed.get("decision_answers"), dict):
            answers = parsed["decision_answers"]
    except Exception:  # noqa: BLE001 - a failed/unparseable critic call yields all-missing (zeros)
        answers = {}

    booleans: list[int] = []
    semantic_values: list[float] = []
    raw_answers: dict[str, Any] = {}
    missing: list[str] = []
    for i, q in enumerate(questions):
        qid = f"q{i + 1}"
        raw_answers[qid] = answers.get(qid)
        answer = answers.get(qid)
        payload = answer if isinstance(answer, dict) else {}
        b = _as_bool(payload.get("answer") if payload else answer)
        if b is None:
            missing.append(qid)
            booleans.append(0)
            semantic_values.append(0.0)
        else:
            raises_when_yes = q.get("raises_score_when", "yes") == "yes"
            oriented = 1 if (b == raises_when_yes) else 0
            booleans.append(oriented)
            strength = payload.get("strength", 3)
            if not isinstance(strength, (int, float)) or isinstance(strength, bool):
                strength = 3
            magnitude = min(3.0, max(0.0, float(strength))) / 3.0
            semantic_values.append(round(magnitude if oriented else -magnitude, 4))
    return {
        "booleans": booleans,
        "semantic_values": semantic_values,
        "raw_answers": raw_answers,
        "missing": missing,
        "media_grounded": bool(media_inputs),
        "critic_version": _CRITIC_VERSION,
    }
