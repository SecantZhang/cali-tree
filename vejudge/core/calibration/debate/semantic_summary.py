"""Semantic prompt distillation for adversarial-calibration debates.

Both the deterministic rule path and the optional LLM path produce the same validated
``SemanticSummary``.  Rendering and leakage checks are shared so choosing an LLM changes
how meaning is extracted, never the safety contract of the downstream judge prompt.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from ....lm_engine.lm_template import LMEngine
from ...judge.parse import parse_json_object
from .schema import DebateTranscript

SUMMARY_VERSION = "semantic-v1"
MAX_WORDS = 250
_REQUIRED_FIELDS = {
    "principle", "applies_when", "evidence_to_check", "scoring_guidance",
}

_LEAKAGE = re.compile(
    r"\b(?:human(?:s)?|annotator(?:s)?|rater(?:s)?|rating(?:s)?|median|mode)\b"
    r"|\b(?:score|rated)\s+(?:of|was|is|to|from|at)\s*\d"
    r"|\bscore\b[^.!?\n]{0,40}\d"
    r"|\b\d+(?:\.\d+)?\s*/\s*(?:5|10)\b"
    r"|\b\d+(?:\.\d+)?\s*%",
    re.IGNORECASE,
)


@dataclass
class SemanticSummary:
    principle: str = ""
    applies_when: str = ""
    evidence_to_check: list[str] = field(default_factory=list)
    scoring_guidance: str = ""
    counter_consideration: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _safe(value: Any) -> str:
    text = _clean(value)
    return "" if not text or _LEAKAGE.search(text) else text


def _dedupe(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _safe(value)
        key = re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
        if text and key and key not in seen:
            seen.add(key)
            out.append(text)
    return out


def validate_summary(data: Any) -> tuple[Optional[SemanticSummary], Optional[str]]:
    """Normalize one summary and reject any label/target leakage as a whole."""
    if not isinstance(data, dict):
        return None, "summary_not_an_object"
    missing = sorted(_REQUIRED_FIELDS - data.keys())
    if missing:
        return None, "summary_missing_required_fields:" + ",".join(missing)
    evidence = data.get("evidence_to_check") or []
    if not isinstance(evidence, list):
        return None, "summary_evidence_not_a_list"
    raw_fields = [
        data.get("principle"), data.get("applies_when"), data.get("scoring_guidance"),
        data.get("counter_consideration"), *evidence,
    ]
    if any(_LEAKAGE.search(_clean(v)) for v in raw_fields if _clean(v)):
        return None, "summary_contains_human_label_or_target_score"
    summary = SemanticSummary(
        principle=_safe(data.get("principle")),
        applies_when=_safe(data.get("applies_when")),
        evidence_to_check=_dedupe(evidence)[:3],
        scoring_guidance=_safe(data.get("scoring_guidance")),
        counter_consideration=_safe(data.get("counter_consideration")),
    )
    if not any((summary.principle, summary.applies_when, summary.evidence_to_check,
                summary.scoring_guidance, summary.counter_consideration)):
        return None, "summary_has_no_safe_semantic_content"
    return summary, None


def _structured(turn: Any) -> Optional[dict[str, Any]]:
    parsed = getattr(turn, "parsed", None) or {}
    value = parsed.get("semantic_summary")
    return value if isinstance(value, dict) else None


def rule_based_summary(
    transcript: DebateTranscript,
    failure_mode_summary: dict[str, int],
    tendencies: dict[str, str],
) -> SemanticSummary:
    """Extract a stable semantic lesson without an extra model call.

    New turns provide structured semantic fields. Older checkpoints fall back to safe
    reasoning/evidence sentences, so changing the renderer does not require re-debating.
    """
    valid = [t for t in transcript.turns if t.valid and t.parsed]
    judges = [t for t in valid if t.role == "judge"]
    proxies = [t for t in valid if t.role == "human_proxy"]
    final_judge = judges[-1] if judges else None
    primary = _structured(final_judge) if final_judge else None

    ranked = sorted(
        ((key, n) for key, n in failure_mode_summary.items() if key in tendencies),
        key=lambda pair: (-pair[1], pair[0]),
    )
    tendency_text = [tendencies[key] for key, _ in ranked[:3]]
    principle = _safe((primary or {}).get("principle"))
    if not principle and tendency_text:
        principle = "Check for a tendency to " + "; to ".join(tendency_text) + "."

    applies_when = _safe((primary or {}).get("applies_when"))
    guidance = _safe((primary or {}).get("scoring_guidance"))

    evidence: list[str] = list((primary or {}).get("evidence_to_check") or [])
    for turn in reversed(judges):
        evidence.extend((turn.parsed or {}).get("evidence") or [])
    if not evidence:
        for turn in reversed(valid):
            evidence.extend((turn.parsed or {}).get("reasoning_lines") or [])

    counter = ""
    if not transcript.converged and proxies:
        proxy_structured = _structured(proxies[-1]) or {}
        counter = _safe(proxy_structured.get("principle"))
        if not counter:
            safe_proxy = _dedupe(list((proxies[-1].parsed or {}).get("reasoning_lines") or []))
            counter = safe_proxy[0] if safe_proxy else ""

    clean_evidence = _dedupe(evidence)[:3]
    has_semantic_content = bool(principle or applies_when or clean_evidence or counter)
    candidate = SemanticSummary(
        principle=principle,
        applies_when=applies_when,
        evidence_to_check=clean_evidence,
        scoring_guidance=guidance or ((
            "Base the evaluation on observable instruction fulfillment and editing quality, "
            "and explicitly weigh both successes and defects."
        ) if has_semantic_content else ""),
        counter_consideration=counter if _clean(counter).lower() != _clean(principle).lower() else "",
    )
    # Deterministic and LLM extraction deliberately converge on this same validation
    # boundary; weak/legacy histories may validate to no content, in which case the
    # empty summary is preferable to inventing filler.
    validated, _ = validate_summary(candidate.to_dict())
    return validated or SemanticSummary()


def render_summary(summary: SemanticSummary) -> str:
    if not any((summary.principle, summary.applies_when, summary.evidence_to_check,
                summary.scoring_guidance, summary.counter_consideration)):
        return ""
    sections: list[str] = ["Semantic calibration guidance from adversarial review:"]
    if summary.principle:
        sections.append(f"Principle: {summary.principle}")
    if summary.applies_when:
        sections.append(f"Apply when: {summary.applies_when}")
    if summary.evidence_to_check:
        sections.append("Evidence to check: " + " ".join(f"- {v}" for v in summary.evidence_to_check))
    if summary.scoring_guidance:
        sections.append(f"Scoring guidance: {summary.scoring_guidance}")
    if summary.counter_consideration:
        sections.append(f"Counter-consideration: {summary.counter_consideration}")

    kept: list[str] = []
    used = 0
    for section in sections:
        words = section.split()
        if used + len(words) > MAX_WORDS:
            continue
        kept.append(section)
        used += len(words)
    return "\n".join(kept)


_LLM_SYSTEM = """\
You distill an adversarial video-editing evaluation debate into reusable semantic
calibration guidance. Preserve the negotiated evaluation principle and concrete,
observable editing evidence. Never include human/annotator/rater ratings, rating
distributions, medians, modes, target scores, correction magnitudes, or instructions to
copy a score. Return JSON only using the requested fields."""


def llm_summary(transcript: DebateTranscript, engine: LMEngine) -> tuple[Optional[SemanticSummary], Optional[str]]:
    history: list[str] = []
    for turn in transcript.turns:
        parsed = turn.parsed or {}
        role = "Human-proxy critique" if turn.role == "human_proxy" else "Judge response"
        history.append(f"Round {turn.round} — {role}:")
        history.extend(f"- {line}" for line in (parsed.get("reasoning_lines") or []))
        history.extend(f"- Observable evidence: {line}" for line in (parsed.get("evidence") or []))
        if isinstance(parsed.get("semantic_summary"), dict):
            history.append("- Proposed semantic lesson: " + json.dumps(parsed["semantic_summary"]))
    user = f"""\
Debate transcript:
{chr(10).join(history)}

Return JSON only:
{{
  "principle": "general reusable evaluation principle",
  "applies_when": "conditions where the principle matters",
  "evidence_to_check": ["2-3 concrete observable editing facts"],
  "scoring_guidance": "how to weigh the evidence without a target score",
  "counter_consideration": "distinct unresolved concern, or empty string"
}}"""
    try:
        output = engine.generate(user, system=_LLM_SYSTEM)
        parsed = parse_json_object(output.get("content") or "")
    except Exception as exc:  # noqa: BLE001 - caller records a visible rule fallback
        return None, f"summarizer_error:{type(exc).__name__}: {exc}"
    return validate_summary(parsed)


def summary_cache_hash(engine_config: dict[str, Any]) -> str:
    """Stable, non-secret cache discriminator for summarizer configuration."""
    import hashlib

    public = {k: v for k, v in engine_config.items() if k not in {"token", "api_key"}}
    blob = json.dumps(public, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:12]
