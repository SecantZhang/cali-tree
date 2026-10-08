"""Deterministic contract demonstration, not evidence of model accuracy."""
from dataclasses import replace
from pathlib import Path
from PIL import Image

from critical.core.decision.models import ProgramSpec, PredicateSpec, BoundPlan, Outcome, OPERATIONS
from .base import EditProposer
from .models import Case, ProgramEdit

RUBRIC = ("Evaluate only requested image edits. Bind each requested outcome to its intended source target "
          "and reference. Supporting evidence does not count as edit progress. Complete requires full "
          "requested completion; partial requires visible requested progress; absent means no requested "
          "progress; unknown means insufficient evidence. Preserve all requested outcomes.")


def seed_program():
    return ProgramSpec(RUBRIC, (PredicateSpec("fulfillment", "requested", OPERATIONS, (),
        "Bind to the intended source target and its edited counterpart.", "Use the coarse demonstration check.",
        "The requested outcome is fully realized.", "Some requested progress is visible.",
        "No requested progress is visible.", "Evidence is insufficient."),))


class DemoChecker:
    identity = {"name": "deterministic-demo-v1"}

    def __init__(self):
        self.calls = []

    def check(self, predicate, outcome, instruction, evidence, dependencies, *, slot, final=False, template_text=None):
        self.calls.append((predicate.id, instruction, slot))
        with Image.open(evidence["edited_image"]) as image:
            red = image.getpixel((0, 0))[0]
        status = "complete" if predicate.question.startswith("Use the coarse") else (
            "complete" if red == 255 else "partial" if red == 128 else "absent")
        return {"status": status, "evidence": "Synthetic red-channel observation", "completion_tokens": 1}


class DemoProposer(EditProposer):
    def propose(self, program, feedback, *, slot, limit):
        p = program.predicates[0]
        if not p.question.startswith("Use the coarse"):
            return []
        return [ProgramEdit("revise", p.id, (replace(p, question="Measure the demonstrated requested progress."),),
                            "Use the measured state instead of a constant completion response")]


def demo_cases(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    cases = []
    for index, label in enumerate(("no", "partial", "yes") * 4):
        source, edited = directory / f"s{index}.png", directory / f"e{index}.png"
        Image.new("RGB", (8, 8), (0, index + 1, 0)).save(source)
        Image.new("RGB", (8, 8), ({"no": 0, "partial": 128, "yes": 255}[label], index + 1, 0)).save(edited)
        instruction = f"Make object {index} red"
        plan = BoundPlan(instruction, (Outcome("o1", instruction, instruction, f"object {index}", "", "attribute"),))
        cases.append(Case(f"c{index}", f"g{index}", plan,
                          {"source_image": str(source), "edited_image": str(edited)}, label))
    return tuple(cases[:6]), tuple(cases[6:9]), tuple(cases[9:])
