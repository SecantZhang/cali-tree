"""Materializes a tiny ``data/`` + ``evaluation/``-shaped fixture tree for interface tests.

One definition, shared by two consumers:
- ``tests/integration/interface/conftest.py`` imports :func:`build` directly.
- The Playwright E2E suite (``web/e2e/global-setup.ts``) shells out to this file as a
  script (``python3 tests/e2e_fixture.py <target-dir>``) so both test suites exercise the
  exact same "what does a test project look like" definition, in one language.

Deliberately dependency-free (stdlib only, no pytest import) so it works as a plain script.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

PROJECTS = ("prj-a", "prj-b")
USE_CASES = {"prj-a": "visual montage", "prj-b": "speech-driven"}


@dataclass
class FixturePaths:
    data_root: Path
    rendered_root: Path
    annotations_root: Path
    use_cases_path: Path


def build(root: Path) -> FixturePaths:
    """Create the fixture tree under ``root`` (created if missing) and return its paths."""
    root = Path(root)
    data_root = root / "data"
    rendered_root = root / "rendered"
    annotations_root = root / "human_annotations"

    for project in PROJECTS:
        (data_root / project).mkdir(parents=True, exist_ok=True)
        (data_root / project / "user_query.json").write_text(
            json.dumps({"prompts": [{"user_request": "make a video"}]})
        )
        base = rendered_root / "peanut-v4-multi-track-gpt-5-1-medium" / project
        (base / "videos").mkdir(parents=True, exist_ok=True)
        (base / "notes").mkdir(parents=True, exist_ok=True)
        (base / "videos" / "20260101_000000_prompt_0_final.mp4").write_text("x")
        (base / "notes" / "20260101_000000_prompt_0_notes.json").write_text("{}")

        ann_dir = annotations_root / project
        ann_dir.mkdir(parents=True, exist_ok=True)
        (ann_dir / f"ann1_prompt0_{project}_peanut_humaneval.json").write_text(
            json.dumps(
                {
                    "annotator": "ann1", "project": project, "model": "peanut",
                    "prompt_idx": 0, "cell_key": "prompt_0__peanut", "output_slot": 1,
                    "annotation": {"video_addresses_prompt": "4", "_complete": True},
                }
            )
        )

    use_cases_path = data_root / "use_cases_config.json"
    use_cases_path.write_text(
        json.dumps({p: {"use_case": uc} for p, uc in USE_CASES.items()})
    )
    return FixturePaths(
        data_root=data_root, rendered_root=rendered_root,
        annotations_root=annotations_root, use_cases_path=use_cases_path,
    )


def main(argv: "list[str] | None" = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print("usage: e2e_fixture.py <target-dir>", file=sys.stderr)
        return 2
    paths = build(Path(args[0]))
    print(json.dumps({
        "data_root": str(paths.data_root),
        "rendered_root": str(paths.rendered_root),
        "annotations_root": str(paths.annotations_root),
        "use_cases_path": str(paths.use_cases_path),
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
