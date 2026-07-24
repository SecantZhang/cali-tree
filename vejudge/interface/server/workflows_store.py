"""Load/save/list/delete saved workflow graphs (JSON) under ``config.WORKFLOWS_ROOT``.

The stored shape is the same ``GraphIn`` schema used to launch a run, so there's one
graph-JSON format, not a frontend-only and backend-only variant.
"""

from __future__ import annotations

import json
import re
from pathlib import Path, PurePosixPath
from typing import Optional

from ... import config
from .schemas import GraphIn, WorkflowOut, utcnow_iso

_SEGMENT_RE = re.compile(r"^[A-Za-z0-9_-]{1,100}$")


class InvalidWorkflowName(ValueError):
    """The workflow name isn't a safe filename component."""


def _relative_name(name: str) -> PurePosixPath:
    """Validate a portable workflow identifier such as ``examples/quick_eval``."""
    if not isinstance(name, str) or not name or len(name) > 500 or "\\" in name:
        raise InvalidWorkflowName(
            f"Invalid workflow name {name!r}: use folder/name with only letters, "
            "digits, '_', and '-' (100 characters per component)"
        )
    path = PurePosixPath(name)
    if (
        path.is_absolute()
        or not path.parts
        or name != path.as_posix()
        or any(
            part in {"", ".", ".."} or not _SEGMENT_RE.fullmatch(part)
            for part in path.parts
        )
    ):
        raise InvalidWorkflowName(
            f"Invalid workflow name {name!r}: use folder/name with only letters, "
            "digits, '_', and '-' (100 characters per component)"
        )
    return path


def _path(name: str) -> Path:
    relative = _relative_name(name)
    return config.WORKFLOWS_ROOT.joinpath(*relative.parts).with_suffix(".json")


def list_workflows() -> list[str]:
    root = config.WORKFLOWS_ROOT
    if not root.is_dir():
        return []
    root_resolved = root.resolve()
    names: list[str] = []
    for path in root.rglob("*.json"):
        if not path.is_file():
            continue
        try:
            relative = path.resolve().relative_to(root_resolved)
        except ValueError:
            continue
        names.append(relative.with_suffix("").as_posix())
    return sorted(names)


def load_workflow(name: str) -> Optional[WorkflowOut]:
    path = _path(name)
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return WorkflowOut(
        name=_relative_name(name).as_posix(),
        graph=GraphIn(**data["graph"]),
        created_at=data["created_at"],
        updated_at=data["updated_at"],
    )


def save_workflow(name: str, graph: GraphIn) -> WorkflowOut:
    path = _path(name)
    canonical_name = _relative_name(name).as_posix()
    path.parent.mkdir(parents=True, exist_ok=True)
    now = utcnow_iso()
    created_at = now
    if path.is_file():
        existing = json.loads(path.read_text(encoding="utf-8"))
        created_at = existing.get("created_at", now)
    out = WorkflowOut(
        name=canonical_name, graph=graph, created_at=created_at, updated_at=now
    )
    path.write_text(out.model_dump_json(indent=2), encoding="utf-8")
    return out


def delete_workflow(name: str) -> bool:
    path = _path(name)
    if not path.is_file():
        return False
    path.unlink()
    parent = path.parent
    root = config.WORKFLOWS_ROOT.resolve()
    while parent != root:
        try:
            parent.rmdir()
        except OSError:
            break
        parent = parent.parent
    return True
