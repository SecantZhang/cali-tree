"""Import side-effect module: registers the in-scope node executors.

Import this (not the individual ``node_db``/``node_preprocessing``/``node_vejudge``/
``node_eval`` submodules) wherever the full registry needs to be populated — the FastAPI
app, the graph executor, or a test asserting on ``NODE_EXECUTORS``. See ``interface.md``
for the full node/workflow model and why the remaining node types aren't here yet.
"""

from .node_calibration.cl_adversarial_node import ClAdversarialNodeExecutor
from .node_calibration.cl_rule_tree_node import ClRuleTreeNodeExecutor
from .node_calibration.cl_semantic_tree_node import ClSemanticTreeNodeExecutor
from .node_calibration.edit_aware_calibration_node import EditAwareCalibrationNodeExecutor
from .node_calibration.calitree_nodes import (
    CaliTreeEvalNodeExecutor,
    CaliTreeJudgeNodeExecutor,
    CaliTreeTrainNodeExecutor,
)
from .node_calibration.rubric_lite_nodes import (
    RubricLiteFrozenNodeExecutor,
    RubricLiteTrainNodeExecutor,
)
from .node_db.coconut_source_node import CoconutSourceNodeExecutor
from .node_db.dataset_node import DatasetNodeExecutor
from .node_db.editinspector_source_node import EditInspectorSourceNodeExecutor
from .node_db.grapenut_source_node import GrapenutSourceNodeExecutor
from .node_db.imagenhub_source_node import ImagenHubSourceNodeExecutor
from .node_db.peanut_source_node import PeanutSourceNodeExecutor
from .node_db.unit_labels_node import UnitLabelsNodeExecutor
from .node_db.vebench_source_node import VeBenchSourceNodeExecutor
from .node_eval.alignment_report_node import AlignmentReportNodeExecutor
from .node_eval.cl_rule_eval_node import ClRuleEvalNodeExecutor
from .node_eval.eval_node import EvalNodeExecutor
from .node_preprocessing.preprocessing_node import PreprocessingNodeExecutor
from .node_preprocessing.edit_decomposition_node import EditDecompositionNodeExecutor
from .node_vejudge.area_aggregation_node import AreaAggregationNodeExecutor
from .node_vejudge.area_judge_node import AreaJudgeNodeExecutor
from .node_vejudge.area_rubric_node import AreaRubricNodeExecutor
from .node_vejudge.judge_node import JudgeNodeExecutor
from .node_vejudge.judge_prompt_node import JudgePromptNodeExecutor
from .node_vejudge.lm_engine_node import LMEngineNodeExecutor

__all__ = [
    "PeanutSourceNodeExecutor",
    "CoconutSourceNodeExecutor",
    "GrapenutSourceNodeExecutor",
    "VeBenchSourceNodeExecutor",
    "ImagenHubSourceNodeExecutor",
    "EditInspectorSourceNodeExecutor",
    "DatasetNodeExecutor",
    "UnitLabelsNodeExecutor",
    "PreprocessingNodeExecutor",
    "EditDecompositionNodeExecutor",
    "LMEngineNodeExecutor",
    "JudgePromptNodeExecutor",
    "JudgeNodeExecutor",
    "AreaRubricNodeExecutor",
    "AreaJudgeNodeExecutor",
    "AreaAggregationNodeExecutor",
    "EvalNodeExecutor",
    "AlignmentReportNodeExecutor",
    "ClRuleEvalNodeExecutor",
    "ClAdversarialNodeExecutor",
    "ClRuleTreeNodeExecutor",
    "ClSemanticTreeNodeExecutor",
    "EditAwareCalibrationNodeExecutor",
    "CaliTreeTrainNodeExecutor",
    "CaliTreeJudgeNodeExecutor",
    "CaliTreeEvalNodeExecutor",
    "RubricLiteTrainNodeExecutor",
    "RubricLiteFrozenNodeExecutor",
]
