"""Deterministic, coverage-reporting unit selection for bounded judge cost."""

from __future__ import annotations

import hashlib
import math
from typing import Any

DEFAULT_UNIT_CAPS = {
    "edit_boundary": 32,
    "shot": 24,
    "sequence": 12,
    "audio_event": 24,
}


def _anomaly_score(unit: dict[str, Any]) -> float:
    measurements = unit.get("measurements") or {}
    score = 1.0 - float(unit.get("confidence", 1.0) or 0.0)
    for key in ("flicker_score", "blur_score", "energy_discontinuity", "motion_change"):
        value = measurements.get(key)
        if isinstance(value, (int, float)) and math.isfinite(float(value)):
            score += abs(float(value))
    return score


def select_units(
    units: list[dict[str, Any]], *, rubric_id: str, unit_types: list[str],
    caps: dict[str, int] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    limits = {**DEFAULT_UNIT_CAPS, **(caps or {})}
    eligible = [
        unit for unit in units
        if unit.get("unit_type") in unit_types
        and rubric_id in (unit.get("applicable_rubrics") or [])
    ]
    selected: list[dict[str, Any]] = []
    by_type: dict[str, dict[str, int]] = {}
    for unit_type in unit_types:
        candidates = sorted(
            [unit for unit in eligible if unit.get("unit_type") == unit_type],
            key=lambda unit: (float(unit.get("start_seconds") or 0), str(unit.get("unit_id"))),
        )
        cap = max(0, int(limits.get(unit_type, len(candidates))))
        if len(candidates) <= cap:
            chosen = candidates
        elif cap == 0:
            chosen = []
        else:
            extreme_count = min(max(1, cap // 3), len(candidates), cap)
            extremes = sorted(
                candidates, key=lambda unit: (-_anomaly_score(unit), str(unit.get("unit_id")))
            )[:extreme_count]
            extreme_ids = {unit["unit_id"] for unit in extremes}
            remainder = [unit for unit in candidates if unit["unit_id"] not in extreme_ids]
            slots = cap - len(extremes)
            if slots:
                # Stable strata over timeline order. Hash breaks exact-index ties without
                # introducing run-to-run randomness.
                stride = len(remainder) / slots
                indexes = {
                    min(len(remainder) - 1, int((slot + 0.5) * stride))
                    for slot in range(slots)
                }
                uniform = [remainder[index] for index in sorted(indexes)]
                if len(uniform) < slots:
                    remaining = [unit for unit in remainder if unit not in uniform]
                    remaining.sort(
                        key=lambda unit: hashlib.sha256(
                            str(unit.get("unit_id")).encode()
                        ).hexdigest()
                    )
                    uniform.extend(remaining[:slots - len(uniform)])
            else:
                uniform = []
            chosen = sorted(
                [*extremes, *uniform],
                key=lambda unit: (float(unit.get("start_seconds") or 0), unit["unit_id"]),
            )
        selected.extend(chosen)
        by_type[unit_type] = {"selected": len(chosen), "total": len(candidates), "cap": cap}
    selected_ids = {unit["unit_id"] for unit in selected}
    annotated = [
        {**unit, "selected_for_judging": unit.get("unit_id") in selected_ids}
        for unit in eligible
    ]
    return [
        next(unit for unit in annotated if unit["unit_id"] == selected_unit["unit_id"])
        for selected_unit in selected
    ], {
        "selected": len(selected),
        "total": len(eligible),
        "coverage": len(selected) / len(eligible) if eligible else 0.0,
        "by_type": by_type,
        "omitted_unit_ids": [
            unit["unit_id"] for unit in annotated if not unit["selected_for_judging"]
        ],
    }
