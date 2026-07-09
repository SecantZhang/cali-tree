"""Import side-effect module: registers the in-scope node executors.

Import this (not the individual ``node_db``/``node_preprocessing``/``node_vejudge``/
``node_eval`` submodules) wherever the full registry needs to be populated — the FastAPI
app, the graph executor, or a test asserting on ``NODE_EXECUTORS``. See ``interface.md``
for the full node/workflow model and why the remaining node types aren't here yet.
"""

from .node_db.dataset_node import DatasetNodeExecutor
from .node_db.peanut_source_node import PeanutSourceNodeExecutor
from .node_eval.eval_node import EvalTextNodeExecutor, EvalVideoNodeExecutor
from .node_preprocessing.preprocessing_node import PreprocessingNodeExecutor
from .node_vejudge.judge_text_node import TextJudgeNodeExecutor
from .node_vejudge.judge_video_node import VideoJudgeNodeExecutor
from .node_vejudge.lm_engine_node import LMEngineNodeExecutor

__all__ = [
    "PeanutSourceNodeExecutor",
    "DatasetNodeExecutor",
    "PreprocessingNodeExecutor",
    "LMEngineNodeExecutor",
    "TextJudgeNodeExecutor",
    "VideoJudgeNodeExecutor",
    "EvalTextNodeExecutor",
    "EvalVideoNodeExecutor",
]
