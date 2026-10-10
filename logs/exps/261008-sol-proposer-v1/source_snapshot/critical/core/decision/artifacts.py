"""Canonical executable identity and atomic JSON persistence."""
import hashlib
import json
from pathlib import Path

from .models import ProgramSpec
from .validation import validate_program


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def program_ref(program):
    validate_program(program)
    return digest(program.to_dict())


def save_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False))
    temporary.replace(path)


def export_program(program):
    return {"program_ref": program_ref(program), "program": program.to_dict()}


def restore_program(row):
    program = ProgramSpec.from_dict(row["program"])
    if row["program_ref"] != program_ref(program):
        raise ValueError("Program hash mismatch")
    return program
