"""Deterministic manual canvas example; no credentials, network or model calls.

Run: .venv/bin/python -m run.calitree_canvas_demo
"""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from critical.checkpoint import CheckpointStore
from critical.logging.exp_logger import make_exp_run
from critical.interface.server.registry import NodeRunContext
from critical.interface.node_calibration.calitree_manual_nodes import (
    CaliTreePartitionNodeExecutor, CaliTreeLeafNodeExecutor, CaliTreeMergeNodeExecutor,
)
from critical.interface.node_calibration.calitree_nodes import CaliTreeJudgeNodeExecutor
from critical.core.optimization.prompt.calitree.decomposition import load_templates
from .calitree_modular_demo import RUBRIC, DemoRubricCompiler, DemoInstructionCompiler


class OfflineEngine:
    name, model, temperature, max_tokens = "offline", "offline", 0, 1000
    def generate(self, user, system=None, **kwargs):
        templates = load_templates()
        if system == templates.compile_policy:
            rubric = "\n".join(row["text"] for row in json.loads(user)["rubric_lines"])
            value = DemoRubricCompiler().compile(rubric).specification
        elif system == templates.decompose_instruction:
            value = DemoInstructionCompiler().decompose(user).to_dict()
        elif system == templates.check_condition:
            value = {"status": "satisfied", "rationale": "Deterministic red observation"}
        elif "Synthesize one reusable" in user:
            value = {"prompt": RUBRIC, "conflict": False}
        else:
            value = {"label": "yes", "rationale": "Deterministic prompt judgment"}
        return {"content": json.dumps(value), "completionTokens": 1}


def main():
    engine = OfflineEngine()
    with TemporaryDirectory(prefix="calitree-canvas-") as directory:
        root = Path(directory)
        def context(node_id, inputs, params=None):
            run = make_exp_run(run_dir=root / node_id)
            return NodeRunContext(node_id, params or {}, inputs, run, CheckpointStore(run.run_dir / "checkpoint.jsonl"), dry_run=False, allow_live=True)
        def execute(executor, ctx):
            result = executor.run(ctx)
            ctx.run.close()
            if result.status != "done": raise RuntimeError(result.error)
            return result.outputs
        samples = {f"task{index}": {"item_id": f"task{index}", "task_uid": f"task{index}",
            "split": "test" if index == 8 else "train", "input": {"instruction": "Make it red"}, "evidence": {"color": "red"}} for index in range(9)}
        labels = {key: {"target_label": "yes", "task_uid": key, "split": sample["split"]} for key, sample in samples.items()}
        with patch('critical.interface.node_calibration.calitree_nodes._engine_from', return_value=engine), patch('critical.interface.server.run_manager.run_dir_for', side_effect=lambda identity: root / identity):
            partition = execute(CaliTreePartitionNodeExecutor(), context('partition', {'samples': samples, 'labels': labels}))['partition']
            settings = {'initial_prompt': RUBRIC, 'optimizer_plan': 'evaluate_only', 'decomposition_strategy': 'two_way', 'output_mode': 'decision_sets', 'optimization_evaluator': 'decomposed'}
            engines = {'judge_engine': {'model': 'offline'}, 'optimizer_engine': {'model': 'offline'}}
            leaves = [execute(CaliTreeLeafNodeExecutor(), context(f'leaf{index}', {'partition': partition, **engines},
                {**settings, 'selected_ids': [key]}))['node'] for index, key in enumerate(partition['fit_ids'][:3])]
            parent = execute(CaliTreeMergeNodeExecutor(), context('parent', {'partition': partition, 'children': leaves, **engines}, settings))['node']
            saved = root / 'node.json'
            saved.write_text(json.dumps(parent))
            restored = json.loads(saved.read_text())
            output = execute(CaliTreeJudgeNodeExecutor(), context('judge', {'calitree_node': restored, 'samples': {'test': samples['task8']}, 'judge_engine': {'model': 'offline'}}))
            print(json.dumps({'version': restored['version'], 'children': restored['children'], 'validation_state': restored['validation_state'],
                              'reloaded_label': output['judge_result']['test']['calitree']['label']}, indent=2))


if __name__ == '__main__': main()
