"""Structural and provenance checks; these do not certify visual truth."""
import re

from .models import OPERATIONS, BoundPlan, ProgramSpec


def validate_program(program: ProgramSpec):
    if program.version != "decision-program-v1" or program.aggregation != "requested-all-some-none-v1":
        raise ValueError("Unsupported program version or aggregation")
    if not isinstance(program.rubric, str) or not program.rubric.strip() or not program.predicates:
        raise ValueError("Program requires a rubric and predicates")
    if not isinstance(program.checker_template, str) or not program.checker_template.strip():
        raise ValueError("Program requires its frozen checker template")
    by_id = {p.id: p for p in program.predicates}
    if len(by_id) != len(program.predicates) or len(by_id) > 12:
        raise ValueError("Duplicate predicates or excessive program size")
    for p in program.predicates:
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,39}", p.id) or p.role not in {"requested", "support"}:
            raise ValueError("Invalid predicate identity or role")
        if not p.applies_to or len(set(p.applies_to)) != len(p.applies_to) or not set(p.applies_to) <= set(OPERATIONS):
            raise ValueError("Invalid applicability")
        if p.provenance not in {"instruction", "rubric"} or (p.role == "requested" and p.provenance != "instruction"):
            raise ValueError("Requested checks must derive from instruction outcomes")
        for name in ("binding", "question", "complete_when", "partial_when", "absent_when", "unknown_when"):
            value = getattr(p, name)
            if not isinstance(value, str) or not value.strip() or len(value) > 1800:
                raise ValueError(f"Invalid predicate {name}")
        if len(set(p.dependencies)) != len(p.dependencies):
            raise ValueError("Duplicate dependency")
        for dep in p.dependencies:
            if dep not in by_id or by_id[dep].role != "support":
                raise ValueError("Dependencies must reference supporting checks")
            if not set(p.applies_to) <= set(by_id[dep].applies_to):
                raise ValueError("Dependency is not applicable to every dependent outcome")
    visited, pending = set(), set()

    def visit(key):
        if key in pending:
            raise ValueError("Cyclic predicate dependency")
        if key not in visited:
            pending.add(key)
            for dep in by_id[key].dependencies:
                visit(dep)
            pending.remove(key)
            visited.add(key)
    for key in by_id:
        visit(key)
    if not any(p.role == "requested" for p in program.predicates):
        raise ValueError("Program must preserve requested outcome coverage")


def validate_plan(plan: BoundPlan):
    if not plan.instruction.strip() or not plan.outcomes or len(plan.outcomes) > 12:
        raise ValueError("Expected nonempty instruction and outcomes")
    if len({o.id for o in plan.outcomes}) != len(plan.outcomes):
        raise ValueError("Duplicate outcome")
    for o in plan.outcomes:
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,39}", o.id) or o.operation not in OPERATIONS:
            raise ValueError("Invalid outcome identity or operation")
        if any(not isinstance(getattr(o, k), str) or not getattr(o, k).strip()
               for k in ("requirement", "target", "source_phrase")):
            raise ValueError("Missing outcome binding")
        if not isinstance(o.reference, str) or o.source_phrase not in plan.instruction:
            raise ValueError("Outcome must cite the exact instruction")
    words = lambda text: set(re.findall(r"\w+", text.lower()))
    if words(plan.instruction) - words(" ".join(o.source_phrase for o in plan.outcomes)) - {"and", "then", "please", "to"}:
        raise ValueError("Instruction content was omitted from outcome provenance")


def bound_checks(program, plan, max_checks=4):
    validate_program(program)
    validate_plan(plan)
    checks = []
    for outcome in plan.outcomes:
        applicable = {p.id: p for p in program.predicates if outcome.operation in p.applies_to}
        requested = [p for p in applicable.values() if p.role == "requested"]
        if not requested:
            raise ValueError("Program omitted a requested outcome")
        added = set()

        def append(p):
            if p.id in added:
                return
            for dep in p.dependencies:
                append(applicable[dep])
            checks.append((outcome, p))
            added.add(p.id)
        for p in requested:
            append(p)
    if len(checks) > max_checks:
        raise ValueError("Bound plan exceeds check cap; requirements were not truncated")
    return checks
