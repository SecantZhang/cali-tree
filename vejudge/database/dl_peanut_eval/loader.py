"""PeanutEvalLoader — enumerate (project, prompt_idx, model) items and build samples."""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any, Optional

from ... import config
from ..dl_template import DataLoader, ItemId
from .curate import curate_sample
from .video_resolver import resolve_peanut_output, resolve_peanut_outputs


@lru_cache(maxsize=1)
def _use_cases() -> dict[str, str]:
    path = config.USE_CASES_CONFIG
    if not path.is_file():
        return {}
    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)
    return {proj: (meta or {}).get("use_case", "unknown") for proj, meta in cfg.items()}


def use_case_for(project: str) -> str:
    return _use_cases().get(project, "unknown")


def parse_item_id(item_id: ItemId) -> tuple[str, int, str]:
    project, idx, model = item_id.split("::")
    return project, int(idx), model


class PeanutEvalLoader(DataLoader):
    """Loads judge samples for the peanut model from the rendered-output tree."""

    def __init__(
        self,
        *,
        model: str = "peanut",
        projects: Optional[list[str]] = None,
        require_video: bool = True,
    ) -> None:
        self.model = model
        self.projects = projects
        self.require_video = require_video

    def _all_projects(self) -> list[str]:
        if self.projects:
            return self.projects
        base = config.RENDERED_ROOT / config.MODEL_DIR_ALIASES.get(self.model, self.model)
        if not base.is_dir():
            return []
        return sorted(p.name for p in base.iterdir() if p.is_dir())

    def list_items(self) -> list[ItemId]:
        items: list[ItemId] = []
        for project in self._all_projects():
            for out in resolve_peanut_outputs(project, self.model):
                if self.require_video and not out.video_path:
                    continue
                items.append(f"{project}::{out.prompt_idx}::{self.model}")
        return items

    def load_sample(self, item_id: ItemId) -> dict[str, Any]:
        project, prompt_idx, model = parse_item_id(item_id)
        out = resolve_peanut_output(project, prompt_idx, model)
        project_dir = str(config.DATA_ROOT / project)
        return curate_sample(
            project=project,
            project_dir=project_dir,
            prompt_index=prompt_idx,
            model=model,
            use_case=use_case_for(project),
            notes_path=out.notes_path or "",
            output_video_path=out.video_path or "",
            otio_path=out.otio_path or "",
            plan_path=out.plan_path or "",
        )
