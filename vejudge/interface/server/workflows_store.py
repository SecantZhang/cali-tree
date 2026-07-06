"""Load/save/list/delete saved workflow graphs (JSON) under ``config.WORKFLOWS_ROOT``.

The stored shape is the same ``GraphIn`` schema used to launch a run, so there's one
graph-JSON format, not a frontend-only and backend-only variant.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

from ... import config
from .schemas import GraphIn, WorkflowOut, utcnow_iso

_SLUG_RE = re.compile(r"^[A-Za-z0-9_-]{1,100}$")


class InvalidWorkflowName(ValueError):
    """The workflow name isn't a safe filename component."""


def _slug(name: str) -> str:
    if not _SLUG_RE.match(name):
        raise InvalidWorkflowName(
            f"Invalid workflow name {name!r}: use only letters, digits, '_', '-' (max 100 chars)"
        )
    return name


def _path(name: str) -> Path:
    return config.WORKFLOWS_ROOT / f"{_slug(name)}.json"


def list_workflows() -> list[str]:
    root = config.WORKFLOWS_ROOT
    if not root.is_dir():
        return []
    return sorted(p.stem for p in root.glob("*.json"))


def load_workflow(name: str) -> Optional[WorkflowOut]:
    path = _path(name)
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return WorkflowOut(
        name=data["name"],
        graph=GraphIn(**data["graph"]),
        created_at=data["created_at"],
        updated_at=data["updated_at"],
    )


def save_workflow(name: str, graph: GraphIn) -> WorkflowOut:
    path = _path(name)
    config.WORKFLOWS_ROOT.mkdir(parents=True, exist_ok=True)
    now = utcnow_iso()
    created_at = now
    if path.is_file():
        existing = json.loads(path.read_text(encoding="utf-8"))
        created_at = existing.get("created_at", now)
    out = WorkflowOut(name=name, graph=graph, created_at=created_at, updated_at=now)
    path.write_text(out.model_dump_json(indent=2), encoding="utf-8")
    return out


def delete_workflow(name: str) -> bool:
    path = _path(name)
    if not path.is_file():
        return False
    path.unlink()
    return True
