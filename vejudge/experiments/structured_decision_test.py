"""Pure helpers for structured-decision prompt equivalence experiments."""

from __future__ import annotations

import json
import math
from typing import Any

from vejudge.experiments.aurora_prompt_repair import robustness_stats


REQUIRED_KEYS = {
    "objective", "evidence_rules", "decision_steps", "label_boundaries",
    "tie_breaks", "output_contract",
}


def parse_decision_spec(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("extractor response does not contain a JSON object")
    value = json.loads(text[start : end + 1])
    if not isinstance(value, dict):
        raise ValueError("decision specification must be a JSON object")
    missing = sorted(REQUIRED_KEYS - value.keys())
    if missing:
        raise ValueError(f"decision specification missing keys: {missing}")
    boundaries = value.get("label_boundaries")
    if not isinstance(boundaries, dict) or not {"no", "partial", "yes"} <= boundaries.keys():
        raise ValueError("label_boundaries must define no, partial, and yes")
    if not isinstance(value.get("decision_steps"), list) or not value["decision_steps"]:
        raise ValueError("decision_steps must be a non-empty list")
    return value


def compile_structured_prompt(spec: dict[str, Any]) -> str:
    policy = json.dumps(spec, ensure_ascii=False, indent=2, sort_keys=True)
    return (
        "You are a vision-language judge. Execute the structured semantic decision policy "
        "below in its listed order. Use only visible evidence from the SOURCE and EDITED "
        "images and the supplied edit instruction. Do not invent, remove, or reorder criteria.\n\n"
        "<semantic_decision_policy>\n" + policy + "\n</semantic_decision_policy>\n\n"
        "Return exactly one compact JSON object and nothing else:\n"
        '{"label":"no|partial|yes","rationale":"brief condition-by-condition image evidence"}\n'
    )


def compile_controlled_prose_prompt(spec: dict[str, Any]) -> str:
    """Render the extracted decisions into fixed natural-language scaffolding."""
    lines = [
        "You are a vision-language judge. Apply the following semantic decision policy in order.",
        "Use only the SOURCE image, EDITED image, and edit instruction.",
        "", "Objective:", str(spec["objective"]), "", "Evidence rules:",
    ]
    lines.extend(f"- {rule}" for rule in spec.get("evidence_rules") or [])
    lines.extend(["", "Ordered decisions:"])
    for step in sorted(spec.get("decision_steps") or [], key=lambda row: row.get("order", 0)):
        lines.append(f"{step.get('order')}. {step.get('decision')} Outcome: {step.get('outcomes')}")
    lines.extend(["", "Label boundaries:"])
    for label in ("no", "partial", "yes"):
        lines.append(f"- {label}:")
        lines.extend(f"  - {condition}" for condition in spec["label_boundaries"].get(label) or [])
    lines.extend(["", "Tie breaks (apply in order):"])
    lines.extend(f"{index}. {rule}" for index, rule in enumerate(spec.get("tie_breaks") or [], 1))
    lines.extend(["", "Return exactly one compact JSON object and nothing else:",
                  '{"label":"no|partial|yes","rationale":"brief condition-by-condition image evidence"}'])
    return "\n".join(lines) + "\n"


def compile_alternate_prose_prompt(spec: dict[str, Any]) -> str:
    """A second direct-prose rendering used to reject representation-sensitive specs."""
    lines = [
        "Act as a vision-language evaluator for the provided SOURCE, EDITED image, and edit instruction.",
        f"Evaluation goal: {spec['objective']}", "", "Assign labels using these boundaries:",
    ]
    for label in ("no", "partial", "yes"):
        conditions = "; ".join(str(value) for value in spec["label_boundaries"].get(label) or [])
        lines.append(f"- Choose {label} when: {conditions}")
    lines.extend(["", "Apply these evidence requirements:"])
    lines.extend(f"- {rule}" for rule in spec.get("evidence_rules") or [])
    lines.extend(["", "Follow this decision sequence:"])
    for step in sorted(spec.get("decision_steps") or [], key=lambda row: row.get("order", 0)):
        lines.append(f"{step.get('order')}. {step.get('decision')} Then: {step.get('outcomes')}")
    lines.extend(["", "Resolve close calls in this order:"])
    lines.extend(f"{index}. {rule}" for index, rule in enumerate(spec.get("tie_breaks") or [], 1))
    lines.extend(["", "Respond with exactly this compact JSON shape and no other text:",
                  '{"label":"no|partial|yes","rationale":"brief condition-by-condition image evidence"}'])
    return "\n".join(lines) + "\n"


def compile_mechanical_json_prompt(prompt: str) -> str:
    """Encode all original lines losslessly while changing only the representation."""
    document = {
        "format": "lossless_ordered_prompt_lines_v1",
        "ordered_lines": [{"order": index, "text": line}
                          for index, line in enumerate(prompt.splitlines(), 1)],
    }
    return (
        "Execute the following losslessly encoded system prompt. Treat each ordered line as "
        "a direct instruction, preserving its exact text, order, repetition, and priority.\n\n"
        "<encoded_system_prompt>\n"
        + json.dumps(document, ensure_ascii=False, indent=2)
        + "\n</encoded_system_prompt>\n"
    )


def select_candidate_rounds(traces: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return every screen-correct round, tagging accepted rounds as the primary cohort."""
    selected = []
    for trace in traces:
        for round_row in trace.get("rounds") or []:
            screen = round_row.get("screen") or {}
            if not screen.get("valid") or screen.get("label") != trace.get("target_label"):
                continue
            selected.append({
                "item_id": trace["item_id"],
                "task_uid": trace.get("task_uid"),
                "method": trace.get("method"),
                "round": round_row.get("round"),
                "target_label": trace.get("target_label"),
                "cohort": "accepted_primary" if round_row.get("accepted") else "screen_correct_secondary",
                "original_prompt": round_row.get("candidate_prompt") or "",
                "original_prompt_sha256": round_row.get("candidate_prompt_sha256"),
                "original_screen": screen,
                "original_repeats": round_row.get("repeats") or [],
                "original_robustness": round_row.get("robustness") or {},
            })
    return sorted(selected, key=lambda row: (row["item_id"], row["method"], row["round"]))


def _distribution(stats: dict[str, Any]) -> list[float]:
    counts = stats.get("label_distribution") or {}
    values = [float(counts.get(label, 0)) for label in ("no", "partial", "yes", "invalid")]
    total = sum(values)
    return [value / total for value in values] if total else [0.0] * 4


def _js_divergence(left: list[float], right: list[float]) -> float:
    middle = [(a + b) / 2 for a, b in zip(left, right)]
    def kl(values, reference):
        return sum(a * math.log2(a / b) for a, b in zip(values, reference) if a and b)
    return (kl(left, middle) + kl(right, middle)) / 2


def compare_behavior(
    candidate: dict[str, Any], structured_screen: dict[str, Any],
    structured_repeats: list[dict[str, Any]], required: int,
) -> dict[str, Any]:
    target = candidate["target_label"]
    structured_stats = robustness_stats(structured_repeats, target, required=required)
    original_stats = candidate.get("original_robustness") or {}
    left, right = _distribution(original_stats), _distribution(structured_stats)
    return {
        "screen_label_preserved": (
            structured_screen.get("valid")
            and structured_screen.get("label") == candidate["original_screen"].get("label")
        ),
        "screen_correct": (
            structured_screen.get("valid") and structured_screen.get("label") == target
        ),
        "robustness_preserved": bool(structured_stats["robust"]),
        "original_target_hits": original_stats.get("target_hits", 0),
        "structured_target_hits": structured_stats["target_hits"],
        "target_hit_delta": structured_stats["target_hits"] - original_stats.get("target_hits", 0),
        "total_variation_distance": sum(abs(a - b) for a, b in zip(left, right)) / 2,
        "jensen_shannon_divergence_bits": _js_divergence(left, right),
        "structured_robustness": structured_stats,
    }


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    def one(rows):
        n = len(rows)
        valid = [row for row in rows if row.get("extraction", {}).get("valid", False)]
        valid_n = len(valid)
        preserved = sum(row.get("comparison", {}).get("screen_label_preserved", False) for row in valid)
        correct = sum(row.get("comparison", {}).get("screen_correct", False) for row in valid)
        robust = sum(row.get("comparison", {}).get("robustness_preserved", False) for row in valid)
        return {
            "n": n,
            "extraction_valid": valid_n,
            "screen_label_preserved": preserved,
            "screen_label_preservation_rate": preserved / valid_n if valid_n else None,
            "screen_correct": correct,
            "screen_accuracy": correct / valid_n if valid_n else None,
            "robustness_preserved": robust,
            "robustness_preservation_rate": robust / valid_n if valid_n else None,
            "mean_target_hit_delta": (
                sum(row["comparison"]["target_hit_delta"] for row in valid) / valid_n if valid_n else None
            ),
            "mean_total_variation_distance": (
                sum(row["comparison"]["total_variation_distance"] for row in valid) / valid_n if valid_n else None
            ),
        }
    primary = [row for row in results if row.get("cohort") == "accepted_primary"]
    secondary = [row for row in results if row.get("cohort") == "screen_correct_secondary"]
    by_label = {label: one([row for row in primary if row.get("target_label") == label])
                for label in ("no", "partial", "yes")}
    methods = sorted({str(row.get("method")) for row in primary})
    by_method = {method: one([row for row in primary if row.get("method") == method])
                 for method in methods}
    return {"all_screen_correct": one(results), "accepted_primary": one(primary),
            "screen_correct_secondary": one(secondary),
            "accepted_primary_by_label": by_label, "accepted_primary_by_method": by_method}
