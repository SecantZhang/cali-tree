"""Lazy public exports; historical APIs load only when requested."""
from importlib import import_module
_EXPORTS = {'RobustLeafOptimizer': ('.search', 'RobustLeafOptimizer'), 'RobustEvaluator': ('.metrics', 'RobustEvaluator'), 'RobustPolicy': ('.metrics', 'RobustPolicy'), 'NodeTextGrad': ('.proposer', 'NodeTextGrad'), 'StructuralProposer': ('.proposer', 'StructuralProposer'), 'VisualEvidenceDiagnosis': ('.discovery', 'VisualEvidenceDiagnosis'), 'VisualReviewer': ('.discovery', 'VisualReviewer'), 'create_evidence_refinement_optimizer': ('.refinement', 'create_evidence_refinement_optimizer'), 'create_typed_evidence_optimizer': ('.typed', 'create_typed_evidence_optimizer'), 'apply_typed_transaction': ('.typed', 'apply_typed_transaction'), 'create_adaptive_evidence_optimizer': ('.adaptive', 'create_adaptive_evidence_optimizer'), 'ProposerPolicy': ('..shared.search', 'ProposerPolicy'), 'create_counting_leaf_optimizer': ('.counting', 'create_counting_leaf_optimizer'), 'create_fulfillment_leaf_optimizer': ('.fulfillment', 'create_fulfillment_leaf_optimizer')}
__all__ = list(_EXPORTS)
def __getattr__(name):
    if name not in _EXPORTS:
        raise AttributeError(name)
    module, attribute = _EXPORTS[name]
    value = getattr(import_module(module, __name__), attribute)
    globals()[name] = value
    return value
