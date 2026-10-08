"""Pure edits with explicit field-level permissions and preserved operation coverage."""
from dataclasses import replace

from critical.core.decision.validation import validate_program

OPERATORS = ("add", "remove", "split", "rebind", "applicability", "revise")


def apply_edit(program, edit):
    validate_program(program)
    if edit.operator not in OPERATORS or not isinstance(edit.reason, str) or not edit.reason.strip():
        raise ValueError("Invalid edit")
    by_id = {p.id: p for p in program.predicates}
    new = list(program.predicates)
    replacements = list(edit.replacements)
    if edit.operator == "add":
        if len(replacements) != 1 or replacements[0].id in by_id:
            raise ValueError("Add needs one new predicate")
        if replacements[0].role == "support":
            if edit.target not in by_id or by_id[edit.target].role != "requested":
                raise ValueError("Supporting additions must attach to a requested predicate")
            new = [replace(p, dependencies=p.dependencies + (replacements[0].id,)) if p.id == edit.target else p for p in new]
        elif edit.target:
            raise ValueError("Requested additions use an empty target")
        new.extend(replacements)
    else:
        if edit.target not in by_id:
            raise ValueError("Unknown edit target")
        original = by_id[edit.target]
        if edit.operator == "remove":
            if replacements:
                raise ValueError("Remove cannot insert predicates")
        elif edit.operator == "split":
            if len(replacements) < 2 or any(p.role != original.role for p in replacements):
                raise ValueError("Split must preserve predicate role")
        else:
            if len(replacements) != 1 or replacements[0].id != original.id:
                raise ValueError("Revision preserves predicate identity")
            allowed = {"rebind": {"binding"}, "applicability": {"applies_to"},
                       "revise": {"question", "complete_when", "partial_when", "absent_when", "unknown_when"}}[edit.operator]
            before, after = original.to_dict(), replacements[0].to_dict()
            if any(before[k] != after[k] for k in before if k not in allowed):
                raise ValueError("Edit changes a forbidden field")
        new = [p for p in new if p.id != edit.target] + replacements
        if edit.operator == "split":
            new = [replace(p, dependencies=tuple(d for old in p.dependencies for d in
                   ([r.id for r in replacements] if old == edit.target else [old]))) for p in new]
    candidate = replace(program, predicates=tuple(new))
    validate_program(candidate)
    coverage = lambda ps: {operation for p in ps if p.role == "requested" for operation in p.applies_to}
    if not coverage(program.predicates) <= coverage(candidate.predicates):
        raise ValueError("Edit deletes required operation coverage")
    if candidate == program:
        raise ValueError("Edit has no effect")
    return candidate
