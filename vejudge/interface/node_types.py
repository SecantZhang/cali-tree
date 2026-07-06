"""Import side-effect module: registers the 3 in-scope node executors.

Import this (not the individual ``node_db``/``node_vejudge``/``node_eval`` submodules)
wherever the full registry needs to be populated — the FastAPI app, the graph executor,
or a test asserting on ``NODE_EXECUTORS``. Deliberately limited to Dataset/Judge/Eval;
see ``interface.md`` and the branch plan for why the other 5 node types aren't here.
"""

from .node_db.dataset_node import DatasetNodeExecutor
from .node_eval.eval_node import EvalNodeExecutor
from .node_vejudge.judge_node import JudgeNodeExecutor

__all__ = ["DatasetNodeExecutor", "JudgeNodeExecutor", "EvalNodeExecutor"]
