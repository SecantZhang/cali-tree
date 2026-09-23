"""Mechanism-A/B debate variant for the prompt-calibration experiment.

Differs from the shipped grounded debate (``core.calibration.debate.runner``) on two
axes, hence a *separate* prompt+driver here rather than edits to the shipped path:

- **B (no point label):** the human-proxy sees only the *direction* of the human
  disagreement (humans rated this higher / lower / about the same as the judge) plus the
  item's own qualitative human *notes* — never the numeric human score. Contrast the
  grounded runner, which feeds the exact human anchor as a convergence target.
- **A (extract a general rule, not a score fix):** the debate's stated goal is to name
  the *general, reusable rule* the judge misapplied — phrased to apply to any item — not
  to revise this item's number. There is no numeric convergence; the debate runs a small
  fixed number of rounds (or stops early if the judge concedes the rule).

Turns are text-only (``DebateTurnRunner`` re-serializes the transcript into each prompt;
no video is attached even for a video metric), so an A/B debate is cheap regardless of
metric modality. The item's base score comes from the caller's already-computed judge
result — this module makes no judge/video calls itself.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Optional

from .....lm_engine.lm_template import LMEngine
from ....prompts.spec import PromptSpec
from ....rubric.definitions import metric_definition
from ..runner import DebateTurnRunner
from ..schema import DebateTurn

PROXY_VERSION = "ab-proxy-v1"
JUDGE_VERSION = "ab-judge-v1"

_PROXY_SCHEMA = {
    "proposed_rule": "string",
    "reasoning_lines": ["string", "string", "string"],
    "agrees_with_judge": "boolean",
}
_JUDGE_SCHEMA = {
    "reasoning_lines": ["string", "string", "string"],
    "concede_rule": "boolean",
    "refined_rule": "string",
}


@lru_cache(maxsize=64)
def _own_human_notes(project: str, prompt_idx: int, model: str) -> tuple[str, ...]:
    """This item's *own* free-text human notes (mechanism B evidence).

    Unlike ``retrieval.find_similar_human_note`` (which deliberately pulls a note from a
    *different* item), here we want the annotators' own comments on this exact item —
    but only the prose, never their numeric scores.
    """
    from .....database.dl_human_annotations.loader import load_human_annotations
    from ..retrieval import _candidate_texts  # same-package prose extractor

    item_id = f"{project}::{prompt_idx}::{model}"
    notes: list[str] = []
    for rec in load_human_annotations(projects=[project]):
        if rec.item_id == item_id:
            notes.extend(_candidate_texts(rec.annotation))
    # De-dup while preserving order; cap so the prompt stays bounded.
    seen: set[str] = set()
    uniq = [n for n in notes if not (n in seen or seen.add(n))]
    return tuple(uniq[:6])


def item_own_notes(sample: dict[str, Any]) -> list[str]:
    return list(
        _own_human_notes(
            sample.get("project", ""), int(sample.get("prompt_idx", 0) or 0),
            sample.get("model", ""),
        )
    )


def direction_word(base_score: Optional[float], human_anchor: Optional[float]) -> str:
    if base_score is None or human_anchor is None:
        return "unknown (no usable human aggregate)"
    diff = human_anchor - base_score
    if diff > 0.25:
        return "HIGHER than the judge's score"
    if diff < -0.25:
        return "LOWER than the judge's score"
    return "about the same as the judge's score"


def build_proxy_ab(
    *,
    sample: dict[str, Any],
    metric_id: str,
    original_output: dict[str, Any],
    transcript_text: str,
    round_no: int,
    direction: str,
    notes: list[str],
) -> PromptSpec:
    inp = sample.get("input") or {}
    original_parsed = original_output.get("parsed") or {}
    notes_block = (
        "\n".join(f'- "{n}"' for n in notes)
        if notes
        else "(no free-text human notes available for this item)"
    )
    transcript_block = transcript_text or "(no prior debate turns yet)"

    system = """\
You are a skeptical human-annotator reviewer. Your goal is NOT to pick a number for this \
one clip. Your goal is to name the single most important GENERAL rule the AI judge got \
wrong -- phrased so it applies to ANY similar item, not just this one. State it as a \
crisp conditional the judge could check on any future item (e.g. "If the repetition was \
explicitly requested by the user's own script, it must NOT be penalized as an \
incoherence defect"). Ground it in the concrete evidence, not vague skepticism. If the \
judge's reasoning actually holds up, say so plainly."""

    user = f"""\
Metric under review: {metric_id}
{metric_definition(metric_id)}

User prompt:
"{inp.get('user_prompt', '')}"

The judge's scored output (rationale to scrutinize):
{original_parsed}

How real human annotators scored this item, relative to the judge:
{direction}
(You are deliberately NOT told the humans' exact number -- reason about WHY they'd \
diverge, do not chase a target.)

Real human annotator notes on this item:
{notes_block}

Debate so far:
{transcript_block}

This is round {round_no}. Respond with JSON only (no markdown fences):
{{
  "proposed_rule": "one general, reusable conditional rule the judge misapplied (or \\"none\\" if the judge held up)",
  "reasoning_lines": [string, string, string],
  "agrees_with_judge": boolean
}}
- "proposed_rule": general and item-agnostic; a rule you could hand a fresh judge."""

    return PromptSpec(system=system, user=user, schema=_PROXY_SCHEMA, version=PROXY_VERSION)


def build_judge_ab(
    *,
    sample: dict[str, Any],
    metric_id: str,
    original_output: dict[str, Any],
    transcript_text: str,
    round_no: int,
) -> PromptSpec:
    inp = sample.get("input") or {}
    original_parsed = original_output.get("parsed") or {}
    transcript_block = transcript_text or "(no prior debate turns yet)"

    system = """\
You are the evaluation judge whose score is under review. A human-annotator reviewer has \
proposed a GENERAL rule you may have misapplied. Decide whether the rule is a legitimate, \
generally-true scoring principle -- if so, concede it and, if useful, refine its wording \
to be more precise and general. If the proposed rule is wrong or overreaching, reject it \
and say why, citing the actual input. Judge the RULE's general validity, not this one \
clip's number."""

    user = f"""\
Metric under review: {metric_id}
{metric_definition(metric_id)}

User prompt:
"{inp.get('user_prompt', '')}"

Your original scored output:
{original_parsed}

Debate so far:
{transcript_block}

This is round {round_no}. Respond with JSON only (no markdown fences):
{{
  "reasoning_lines": [string, string, string],
  "concede_rule": boolean,
  "refined_rule": "the rule as you'd state it for a fresh judge (or \\"none\\" if you reject it)"
}}"""

    return PromptSpec(system=system, user=user, schema=_JUDGE_SCHEMA, version=JUDGE_VERSION)


def _ab_transcript_text(turns: list[DebateTurn]) -> str:
    lines: list[str] = []
    for t in turns:
        p = t.parsed or {}
        label = "Human-proxy" if t.role == "human_proxy" else "Judge"
        rule = p.get("proposed_rule") or p.get("refined_rule")
        lines.append(f"Round {t.round} -- {label}:")
        for r in (p.get("reasoning_lines") or []):
            lines.append(f"  - {r}")
        if rule:
            lines.append(f"  [rule: {rule}]")
        if t.error:
            lines.append(f"  [turn failed: {t.error}]")
    return "\n".join(lines)


def run_ab_debate(
    *,
    sample: dict[str, Any],
    metric_id: str,
    original_output: dict[str, Any],
    judge_engine: LMEngine,
    proxy_engine: LMEngine,
    direction: str,
    notes: list[str],
    max_rounds: int = 2,
) -> dict[str, Any]:
    """Run the bounded A/B debate. Returns a lightweight transcript dict; makes only
    text LM calls (no video)."""
    proxy_runner = DebateTurnRunner(proxy_engine)
    judge_runner = DebateTurnRunner(judge_engine)
    turns: list[DebateTurn] = []
    rounds_run = 0

    for round_no in range(1, max_rounds + 1):
        rounds_run = round_no
        proxy_turn = proxy_runner.run_turn(
            role="human_proxy",
            build=build_proxy_ab,
            build_kwargs=dict(
                sample=sample, metric_id=metric_id, original_output=original_output,
                transcript_text=_ab_transcript_text(turns), round_no=round_no,
                direction=direction, notes=notes,
            ),
            round_no=round_no,
        )
        turns.append(proxy_turn)

        judge_turn = judge_runner.run_turn(
            role="judge",
            build=build_judge_ab,
            build_kwargs=dict(
                sample=sample, metric_id=metric_id, original_output=original_output,
                transcript_text=_ab_transcript_text(turns), round_no=round_no,
            ),
            round_no=round_no,
        )
        turns.append(judge_turn)

        # Early stop once the judge accepts the proposed rule — the principle is settled.
        if judge_turn.valid and (judge_turn.parsed or {}).get("concede_rule") is True:
            break

    return {
        "item_id": sample.get("item_id"),
        "metric_id": metric_id,
        "direction": direction,
        "rounds_run": rounds_run,
        "turns": [
            {"round": t.round, "role": t.role, "parsed": t.parsed, "valid": t.valid,
             "error": t.error}
            for t in turns
        ],
        "transcript_text": _ab_transcript_text(turns),
    }
