"""Immutable JSON artifacts confined to managed interface run directories."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import tempfile

from . import run_manager


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     allow_nan=False).encode()).hexdigest()


def _path(reference):
    if not isinstance(reference, dict) or set(reference) != {"run_id", "node_id", "stage", "digest"}:
        raise ValueError("Invalid stage artifact reference")
    if not all(isinstance(reference[key], str) for key in reference):
        raise ValueError("Artifact reference fields must be strings")
    if not re.fullmatch(r"[A-Za-z0-9_:-]+", reference["run_id"]):
        raise ValueError("Invalid artifact run identity")
    if not re.fullmatch(r"[a-z_]+", reference["stage"]) or not re.fullmatch(r"[0-9a-f]{64}", reference["digest"]):
        raise ValueError("Invalid artifact stage/digest")
    node = hashlib.sha256(reference["node_id"].encode()).hexdigest()
    return run_manager.run_dir_for(reference["run_id"]) / "artifacts" / node / reference["stage"] / (reference["digest"] + ".json")


def save_artifact(run, node_id, stage, value):
    run_id = run.run_dir.name.removesuffix("-exps")
    reference = {"run_id": run_id, "node_id": node_id, "stage": stage, "digest": _digest(value)}
    # Tests and embedded executors can use their own run directory. Reads are still
    # resolved only through the managed run root, never through a client-supplied path.
    node = hashlib.sha256(node_id.encode()).hexdigest()
    path = run.run_dir / "artifacts" / node / stage / (reference["digest"] + ".json")
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False, encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, allow_nan=False)
            temporary = Path(stream.name)
        temporary.replace(path)
    return reference


def load_artifact(reference):
    path = _path(reference)
    if not path.is_file():
        raise ValueError(f"Missing pinned artifact for stage {reference['stage']}; rerun and pin that stage")
    value = json.loads(path.read_text(encoding="utf-8"))
    if _digest(value) != reference["digest"]:
        raise ValueError("Artifact digest mismatch")
    return deepcopy(value)
