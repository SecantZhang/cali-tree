"""EditInspector external image-edit benchmark source node."""

from __future__ import annotations

from ...database.dl_editinspector import EditInspectorLoader
from ..server.registry import NodeExecutor, NodeRunContext, NodeRunResult, register


@register
class EditInspectorSourceNodeExecutor(NodeExecutor):
    node_type = "editinspector_source"
    category = "node_db"
    input_sockets: dict[str, str] = {}
    output_sockets = {
        "raw_dataset": "raw_dataset",
        "raw_labels": "raw_labels",
    }
    param_schema = {
        "partition": {
            "type": "enum",
            "options": [
                "all", "calibration", "development",
                "confirmation", "final",
            ],
            "default": "all",
        },
    }

    def run(self, ctx: NodeRunContext) -> NodeRunResult:
        loader = EditInspectorLoader()
        try:
            samples, labels = loader.load_all()
        except FileNotFoundError as exc:
            if not ctx.dry_run:
                return NodeRunResult(status="error", error=str(exc))
            samples, labels = {}, {}
        except ValueError as exc:
            return NodeRunResult(status="error", error=str(exc))
        partition = str(ctx.params.get("partition") or "all")
        if partition not in {
            "all", "calibration", "development",
            "confirmation", "final",
        }:
            return NodeRunResult(
                status="error",
                error=f"Unknown EditInspector partition {partition!r}",
            )
        if partition == "calibration":
            samples = {
                item_id: sample
                for item_id, sample in samples.items()
                if sample.get("external_partition")
                in {"development", "confirmation"}
            }
            labels = {
                item_id: label
                for item_id, label in labels.items()
                if item_id in samples
            }
        elif partition != "all":
            samples = {
                item_id: sample
                for item_id, sample in samples.items()
                if sample.get("external_partition") == partition
            }
            labels = {
                item_id: label
                for item_id, label in labels.items()
                if item_id in samples
            }
        counts = {
            label: sum(
                1 for row in labels.values()
                if row.get("target_label") == label
            )
            for label in ("no", "partial", "yes")
        }
        return NodeRunResult(
            outputs={"raw_dataset": samples, "raw_labels": labels},
            meta={
                "dry_run": ctx.dry_run,
                "loader": "editinspector",
                "partition": partition,
                "n_items": len(samples),
                "n_labels": len(labels),
                "label_counts": counts,
                "downloads": 0,
                "local_data_available": bool(samples),
                "expected_full_items": 783,
                "split_counts": {"train": 0, "test": len(samples)},
            },
        )
