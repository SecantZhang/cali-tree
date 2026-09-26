"""ImagenHub text-guided image-editing source node."""

from __future__ import annotations

from ...database.dl_imagenhub import EDITORS, IMAGENMUSEUM_EDITORS, ImagenHubLoader
from ..server.registry import NodeExecutor, NodeRunContext, NodeRunResult, register


@register
class ImagenHubSourceNodeExecutor(NodeExecutor):
    node_type = "imagenhub_source"
    category = "node_db"
    input_sockets: dict[str, str] = {}
    output_sockets = {
        "raw_dataset": "raw_dataset",
        "raw_labels": "raw_labels",
    }
    param_schema = {
        "repeat": {"type": "enum", "options": [1, 2, 3], "default": 1},
        "editors": {
            "type": "list[string]",
            "options": list(EDITORS),
            "default": list(IMAGENMUSEUM_EDITORS),
        },
    }

    def run(self, ctx: NodeRunContext) -> NodeRunResult:
        # A dry graph is a planning operation. If setup already exists, expose the local
        # records so downstream sampling and Cali-Tree can report exact case/call counts.
        # Loading is filesystem-only; missing setup falls back to public cardinalities and
        # never triggers setup or network work.
        if ctx.dry_run:
            try:
                loader = ImagenHubLoader(
                    repeat=int(ctx.params.get("repeat") or 1),
                    editors=ctx.params.get("editors") or IMAGENMUSEUM_EDITORS,
                )
            except ValueError as exc:
                return NodeRunResult(status="error", error=str(exc))
            editors = loader.editors
            try:
                samples, labels = loader.load_all()
            except FileNotFoundError:
                samples, labels = {}, {}
            if samples:
                split_counts = {
                    split: sum(
                        1
                        for sample in samples.values()
                        if sample["split"] == split
                    )
                    for split in ("train", "test")
                }
                return NodeRunResult(
                    outputs={
                        "raw_dataset": samples,
                        "raw_labels": labels,
                    },
                    meta={
                        "dry_run": True,
                        "loader": "imagenhub",
                        "n_items": len(samples),
                        "n_labels": len(labels),
                        "seed": loader.seed,
                        "split_counts": split_counts,
                        "downloads": 0,
                        "local_data_available": True,
                    },
                )
            return NodeRunResult(
                outputs={"raw_dataset": {}, "raw_labels": {}},
                meta={
                    "dry_run": True,
                    "loader": "imagenhub",
                    "expected_tasks": 179,
                    "expected_items": 179 * len(editors),
                    "expected_train": 29 * len(editors),
                    "expected_test": 150 * len(editors),
                    "seed": loader.seed,
                    "downloads": 0,
                    "local_data_available": False,
                },
            )
        try:
            loader = ImagenHubLoader(
                repeat=int(ctx.params.get("repeat") or 1),
                editors=ctx.params.get("editors") or IMAGENMUSEUM_EDITORS,
            )
            samples, labels = loader.load_all()
        except (FileNotFoundError, ValueError) as exc:
            return NodeRunResult(status="error", error=str(exc))
        split_counts = {
            split: sum(1 for sample in samples.values() if sample["split"] == split)
            for split in ("train", "test")
        }
        return NodeRunResult(
            outputs={"raw_dataset": samples, "raw_labels": labels},
            meta={
                "loader": "imagenhub",
                "n_items": len(samples),
                "n_labels": len(labels),
                "repeat": loader.repeat,
                "seed": loader.seed,
                "split_counts": split_counts,
            },
        )
