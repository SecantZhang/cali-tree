"""Independent-critic answering of the rule-bank booleans — the fix for the null result.

The cold-self-answer approach (`feature_extraction`) asked the *same judge* whether it
committed each flagged error; it denied them all (all-zero features). Here a **separate
critic** — a different LM given the item and the judge's own rationale, explicitly told it
is auditing, not re-scoring — answers each rule boolean. The critic being distinct from the
judge is the whole point; a judge won't self-incriminate, an auditor will.

Text-only in v1: the critic audits the judge's *reasoning* against the task + assembly
(most rule questions are of the form "does the judge penalize X?"), which needs the
rationale + plan, not the rendered video. A video critic is a follow-up.
"""

from __future__ import annotations

from typing import Any

from .....lm_engine.lm_template import LMEngine
from ....judge.parse import parse_json_object
from .feature_extraction import _as_bool

_CRITIC_VERSION = "rule-critic-v1"

_SYSTEM = """\
You are an independent reviewer auditing an AI judge's evaluation of a video edit. You are
NOT re-scoring the edit. For each yes/no question, decide whether the judge exhibited the
described reasoning error, based on the user's request, the assembled edit, and the judge's
own stated rationale. Answer strictly true/false; be willing to say the judge erred."""


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
    try:
        out = critic_engine.generate(prompt, system=_SYSTEM)
    except Exception:  # noqa: BLE001 - a failed critic call yields all-missing (zeros)
        answers: dict[str, Any] = {}
    else:
        parsed = parse_json_object(out.get("content") or "")
        answers = (parsed or {}).get("decision_answers") if isinstance(parsed, dict) else {}
        answers = answers if isinstance(answers, dict) else {}

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
    return {"booleans": booleans, "raw_answers": raw_answers, "missing": missing}
