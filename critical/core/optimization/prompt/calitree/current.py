"""Load the selected CaliTree inference stack without fitting or model calls."""
import json
from pathlib import Path

from critical.config import CALITREE_SELECTION, PROJECT_ROOT
from ....calibration.visual_semantic_policy_v69 import VisualSemanticPolicy
from ....calibration.semantic_rubric_runtime_v70 import SemanticRubricPolicy
from ....calibration.independent_expert_v87 import IndependentExpertPolicy
from ....calibration.semantic_residual_runtime_v104 import SemanticResidualPolicy
from .semantic_residual_judge_v104 import SemanticResidualJudge


def selected_pipeline(selection=None, *, project_root=None):
    """Resolve the selected artifact identities, failing on a changed component."""
    root = Path(project_root or PROJECT_ROOT).resolve()
    path = Path(selection or CALITREE_SELECTION)
    selected = json.loads(path.read_text(encoding='utf-8'))
    if selected.get('version') != 'calitree-selection-v1' or selected.get('selected_version') != 'v112':
        raise ValueError('The selected CaliTree release must be v112')
    expected = {'visual_teacher', 'semantic_rubric', 'independent_expert', 'semantic_review'}
    if set(selected.get('artifacts', {})) != expected:
        raise ValueError('Complete selected CaliTree stack required')
    artifacts = {}
    for name, spec in selected['artifacts'].items():
        relative = Path(spec['path']); resolved = (root/relative).resolve()
        if relative.is_absolute() or root not in resolved.parents:
            raise ValueError('CaliTree artifacts must use project-relative paths')
        value = json.loads(resolved.read_text(encoding='utf-8'))
        if value.get('artifact_ref') != spec['artifact_ref']:
            raise ValueError('Selected CaliTree component differs: '+name)
        artifacts[name] = value
    review = artifacts['semantic_review']['rubric']
    if (review.get('compilation', {}).get('version') != 'semantic-polynomial-v111' or
            len(review.get('clauses', [])) != 60):
        raise ValueError('v112 requires the verified60-term shared semantic correction')
    return selected, artifacts


def load_current_policy(selection=None, *, project_root=None):
    """Construct the existing bound runtimes from the selected frozen artifacts."""
    _, a = selected_pipeline(selection, project_root=project_root)
    visual = VisualSemanticPolicy(a['visual_teacher'])
    semantic = SemanticRubricPolicy(visual, a['semantic_rubric'])
    expert = IndependentExpertPolicy(semantic, a['independent_expert'])
    return SemanticResidualPolicy(expert, a['semantic_review'])


class CaliTreeJudge(SemanticResidualJudge):
    """Default AURORA judge: selected v112 policy with its existing fallback.

    Pass cached stages for offline inference, or explicitly supply the existing
    call/encoder/observer interfaces for fresh inference. Construction makes no
    model calls and loads no neural checkpoints.
    """
    def __init__(self, calls=None, encoder=None, *, selection=None, project_root=None,
                 observer=None, extractor=None):
        policy = load_current_policy(selection, project_root=project_root)
        super().__init__(calls, policy, encoder, observer=observer, extractor=extractor)
        self.selected_version = 'v112'

    def judge(self, *args, **kwargs):
        result = super().judge(*args, **kwargs)
        return {**result, 'pipeline_version': self.selected_version,
                'policy_ref': self.policy.artifact['artifact_ref']}
