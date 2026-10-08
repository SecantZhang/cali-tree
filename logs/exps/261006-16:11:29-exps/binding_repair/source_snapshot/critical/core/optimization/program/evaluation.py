"""Equal-case repeated measurements with unresolved outcomes in denominators."""
from collections import Counter
from hashlib import sha256
from PIL import Image

from .base import ProgramEvaluator

LABELS = ("no", "partial", "yes")


def source_group(path):
    with Image.open(path) as image:
        image = image.convert("RGB")
        return sha256(str(image.size).encode() + image.tobytes()).hexdigest()


def validate_partitions(*partitions):
    seen_ids, seen_groups, seen_pixels = set(), set(), set()
    for cases in partitions:
        ids = [c.id for c in cases]
        groups = {c.group for c in cases}
        pixels = {source_group(c.evidence["source_image"]) for c in cases}
        if len(ids) != len(set(ids)) or set(ids) & seen_ids or groups & seen_groups or pixels & seen_pixels:
            raise ValueError("Case/source group leakage across partitions")
        if any(not c.id or not c.group or c.target not in LABELS for c in cases):
            raise ValueError("Invalid labeled case")
        seen_ids.update(ids)
        seen_groups.update(groups)
        seen_pixels.update(pixels)


def summarize(rows, program):
    confusion = {label: Counter() for label in LABELS}
    totals = Counter()
    case_flip_rates, case_atomic_rates = [], []
    resolved = correct = expected_checks = completion_tokens = 0.0
    for row in rows:
        flips, pairs, atomic_flips, atomic_pairs = 0, 0, 0, 0
        draws, target = row["draws"], row["target"]
        totals[target] += 1
        for draw in draws:
            weight = 1 / len(draws)
            label = draw["label"] or "unresolved"
            confusion[target][label] += weight
            correct += weight * (label == target)
            resolved += weight * (label in LABELS)
            expected_checks += weight * len(draw["observations"])
            completion_tokens += weight * sum(o.get("completion_tokens", 0) for o in draw["observations"])
        for i, a in enumerate(draws):
            for b in draws[i + 1:]:
                # Include unresolved as a distinct outcome; never reward unknown-only atomic stability.
                pairs += 1
                flips += a["label"] != b["label"]
                ai = {(o["outcome_id"], o["predicate_id"]): o for o in a["observations"]}
                bi = {(o["outcome_id"], o["predicate_id"]): o for o in b["observations"]}
                for key in ai.keys() | bi.keys():
                    atomic_pairs += 1
                    x, y = ai.get(key), bi.get(key)
                    atomic_flips += not (x and y and x["valid"] and y["valid"] and
                                         x["status"] == y["status"] != "unknown")
        if pairs:
            case_flip_rates.append(flips / pairs)
        if atomic_pairs:
            case_atomic_rates.append(atomic_flips / atomic_pairs)
    recall = {label: confusion[label][label] / totals[label] if totals[label] else None for label in LABELS}
    f1 = []
    for label in LABELS:
        if totals[label]:
            tp = confusion[label][label]
            predicted = sum(confusion[t][label] for t in LABELS)
            f1.append(2 * tp / (predicted + totals[label]))
    n = len(rows)
    return {"accuracy": correct / n if n else 0, "coverage": resolved / n if n else 0,
            "resolved_accuracy": correct / resolved if resolved else None,
            "balanced_accuracy": sum(v for v in recall.values() if v is not None) / len(f1) if f1 else 0,
            "macro_f1": sum(f1) / len(f1) if f1 else 0, "recall": recall,
            "flip_rate": sum(case_flip_rates) / len(case_flip_rates) if case_flip_rates else 0,
            "atomic_unstable_or_unknown_rate": sum(case_atomic_rates) / len(case_atomic_rates) if case_atomic_rates else None,
            "predicate_count": len(program.predicates), "mean_executed_checks": expected_checks / n if n else 0,
            "mean_completion_tokens": completion_tokens / n if n else 0,
            "confusion": {k: dict(v) for k, v in confusion.items()}, "cases": rows,
            "case_count": n, "group_count": len({r["group"] for r in rows})}


class RepeatedEvaluator(ProgramEvaluator):
    def __init__(self, executor):
        self.executor = executor

    def evaluate(self, program, cases, *, repeats, namespace, final=False):
        if repeats < 1 or not cases:
            raise ValueError("Evaluation needs cases and positive repeats")
        rows = []
        for case in cases:
            draws = [self.executor.execute(program, case.plan, case.evidence,
                     repeat=f"{namespace}/{i}", final=final).to_dict() for i in range(repeats)]
            rows.append({"case_id": case.id, "group": case.group, "target": case.target, "draws": draws})
        return summarize(rows, program)
