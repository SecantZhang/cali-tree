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
    vebench_root: Path


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

    # A tiny VE-Bench DB fixture (label.txt + edited/src videos), plus its MOS materialized
    # as edit_quality humaneval JSON under the annotations root — so the vebench_source node
    # + Dataset label lookup work in tests without the real 700MB dataset.
    vebench_root = rendered_root / "ve-bench" / "VE-Bench-DB"
    (vebench_root / "train_samples" / "edited").mkdir(parents=True, exist_ok=True)
    (vebench_root / "train_samples" / "src").mkdir(parents=True, exist_ok=True)
    _VEBENCH_ITEMS = {"001tokenflow_dog": 5.5, "02t2vzero_ship": 3.2}
    (vebench_root / "label.txt").write_text(
        "".join(f"{stem}.mp4|{mos}|edit prompt for {stem}\n" for stem, mos in _VEBENCH_ITEMS.items())
    )
    ve_ann = annotations_root / "vebench"
    ve_ann.mkdir(parents=True, exist_ok=True)
    for stem, mos in _VEBENCH_ITEMS.items():
        (vebench_root / "train_samples" / "edited" / f"{stem}.mp4").write_text("x")
        (vebench_root / "train_samples" / "src" / f"{stem}.mp4").write_text("x")
        (ve_ann / f"vebench_{stem}_humaneval.json").write_text(
            json.dumps({
                "annotator": "vebench_mos", "project": stem, "model": "vebench",
                "prompt_idx": 0, "cell_key": "prompt_0__vebench", "output_slot": 1,
                "annotation": {"edit_quality": mos, "_complete": True},
            })
        )

    return FixturePaths(
        data_root=data_root, rendered_root=rendered_root,
        annotations_root=annotations_root, use_cases_path=use_cases_path,
        vebench_root=vebench_root,
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
        "vebench_root": str(paths.vebench_root),
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
