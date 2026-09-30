"""Read-only AURORA source for manual and automatic CaliTree workflows."""

from ...database.dl_aurora import AuroraBenchLoader, AURORA_MODELS, AURORA_TASKS
from ..server.registry import NodeExecutor, NodeRunResult, register


@register
class AuroraSourceNodeExecutor(NodeExecutor):
    node_type = "aurora_source"
    category = "node_db"
    input_sockets = {}
    output_sockets = {"raw_dataset": "raw_dataset", "raw_labels": "raw_labels"}
    param_schema = {
        "repeat": {"type": "enum", "options": ["1", "2", "3"], "default": "1"},
        "tasks": {"type": "list[string]", "options": list(AURORA_TASKS), "default": list(AURORA_TASKS)},
        "models": {"type": "list[string]", "options": list(AURORA_MODELS), "default": list(AURORA_MODELS)},
    }

    def run(self, ctx):
        try:
            loader = AuroraBenchLoader(repeat=int(ctx.params.get("repeat", 1)),
                tasks=ctx.params.get("tasks"), models=ctx.params.get("models"))
            samples, labels = loader.load_all()
        except (ValueError, FileNotFoundError) as error:
            return NodeRunResult(status="error", error=str(error))
        return NodeRunResult(outputs={"raw_dataset": samples, "raw_labels": labels},
            meta={"loader": "aurora", "dry_run": ctx.dry_run, "downloads": 0,
                  "n_items": len(samples), "n_labels": len(labels), "seed": loader.seed,
                  "split_counts": {split: sum(row["split"] == split for row in samples.values())
                                   for split in ("train", "test")}})
