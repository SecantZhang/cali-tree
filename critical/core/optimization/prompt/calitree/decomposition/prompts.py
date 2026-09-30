"""Packaged, versioned templates shared by the model-backed components."""

from __future__ import annotations

from dataclasses import dataclass
from importlib.resources import files


DEFAULT_PROMPT_VERSION = "calitree_decomposition_v1"


@dataclass(frozen=True)
class DecompositionTemplates:
    compile_policy: str
    decompose_instruction: str
    check_condition: str
    version: str = DEFAULT_PROMPT_VERSION


def load_templates(version: str = DEFAULT_PROMPT_VERSION) -> DecompositionTemplates:
    if not isinstance(version, str) or not version.isidentifier():
        raise ValueError(f"Invalid decomposition template version: {version!r}")
    directory = files("critical.core.prompts").joinpath("templates", version)
    try:
        return DecompositionTemplates(
            compile_policy=directory.joinpath("compile_policy.txt").read_text(encoding="utf-8"),
            decompose_instruction=directory.joinpath("decompose_instruction.txt").read_text(encoding="utf-8"),
            check_condition=directory.joinpath("check_condition.txt").read_text(encoding="utf-8"),
            version=version,
        )
    except (FileNotFoundError, NotADirectoryError) as error:
        raise ValueError(f"Unknown decomposition template version: {version!r}") from error
