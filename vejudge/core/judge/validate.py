"""Validate parsed judge output: JSON validity, score ranges, required fields, rationale.

Per CLAUDE.md, invalid/missing fields are *flagged*, never silently defaulted. The
benchmark can then choose to drop flagged items rather than feed garbage into metrics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from ..rubric.definitions import SCORE_MAX, SCORE_MIN

# Score-bearing keys we range-check wherever they appear (top-level or nested).
_SCORE_KEYS = {"score_1_to_5", "overall_av_sync_score"}


@dataclass
class ValidationResult:
    ok: bool
    flags: list[str] = field(default_factory=list)

    def __bool__(self) -> bool:  # truthy when valid
        return self.ok


def _iter_scores(obj: Any) -> list[tuple[str, Any]]:
    """Recursively collect (key, value) pairs for score-bearing keys."""
    found: list[tuple[str, Any]] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in _SCORE_KEYS:
                found.append((k, v))
            else:
                found.extend(_iter_scores(v))
    elif isinstance(obj, list):
        for item in obj:
            found.extend(_iter_scores(item))
    return found


def validate_judge_output(
    parsed: Optional[dict[str, Any]],
    *,
    required_fields: Optional[list[str]] = None,
    require_rationale: bool = True,
) -> ValidationResult:
    flags: list[str] = []

    if parsed is None:
        return ValidationResult(ok=False, flags=["invalid_json"])
    if not isinstance(parsed, dict):
        return ValidationResult(ok=False, flags=["not_an_object"])

    for f in required_fields or []:
        if f not in parsed:
            flags.append(f"missing_field:{f}")

    scores = _iter_scores(parsed)
    for key, val in scores:
        if not isinstance(val, (int, float)) or isinstance(val, bool):
            flags.append(f"non_numeric_score:{key}")
        elif not (SCORE_MIN <= val <= SCORE_MAX):
            flags.append(f"score_out_of_range:{key}={val}")

    if require_rationale:
        lines = parsed.get("reasoning_lines")
        has_text_reasoning = any(
            isinstance(v, str) and v.strip() for v in parsed.values()
        )
        if not (isinstance(lines, list) and any(str(x).strip() for x in lines)):
            # M6 sub-dimensions carry "reasoning" strings instead of reasoning_lines.
            if not has_text_reasoning:
                flags.append("empty_rationale")

    return ValidationResult(ok=not flags, flags=flags)
