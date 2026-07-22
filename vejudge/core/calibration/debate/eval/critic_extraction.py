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

_CRITIC_VERSION = "rule-critic-v2-video-grounded"

_SYSTEM = """\
You are an independent reviewer auditing an AI judge's evaluation of a video edit. You are
NOT re-scoring the edit. For each yes/no question, decide whether the judge exhibited the
described reasoning error, based on the user's request, the assembled edit, and the judge's
own stated rationale. When the rendered video is attached, inspect it directly and treat it
as the authority for observable audio/visual claims. Do not accept or reject a claim merely
because the judge stated it confidently. Answer strictly true/false; be willing to say the
judge erred."""


def build_critic_prompt(
    sample: dict[str, Any], judge_rationale: str, questions: list[dict[str, Any]]
) -> str:
    inp = sample.get("input") or {}
    out = sample.get("output") or {}
    numbered = "\n".join(f'  "q{i + 1}": true/false  // {q["question"]}'
                         for i, q in enumerate(questions))
    return f"""\
User's request:
"{inp.get('user_prompt', '')}"

The assembled edit under review:
{out.get('assembly_json') or out.get('output_transcript') or out}

The judge's stated rationale (what you are auditing — NOT re-scoring):
{judge_rationale}

Answer each question about the JUDGE's reasoning as booleans, in a JSON object only (no
markdown fences), under a top-level key "decision_answers":
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
    """Return ``{booleans, raw_answers, missing}`` — the critic's oriented answers to the
    rule bank for one item. Oriented like ``feature_extraction``: 1 means the score-raising
    condition is present (answer == the question's ``raises_score_when``)."""
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
    raw_answers: dict[str, Any] = {}
    missing: list[str] = []
    for i, q in enumerate(questions):
        qid = f"q{i + 1}"
        raw_answers[qid] = answers.get(qid)
        b = _as_bool(answers.get(qid))
        if b is None:
            missing.append(qid)
            booleans.append(0)
        else:
            raises_when_yes = q.get("raises_score_when", "yes") == "yes"
            booleans.append(1 if (b == raises_when_yes) else 0)
    return {
        "booleans": booleans,
        "raw_answers": raw_answers,
        "missing": missing,
        "media_grounded": bool(media_inputs),
        "critic_version": _CRITIC_VERSION,
    }
