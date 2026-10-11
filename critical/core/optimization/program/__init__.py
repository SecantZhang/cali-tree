"""Lazy public exports; historical APIs load only when requested."""
from importlib import import_module
_EXPORTS = {'create_leaf_optimizer': ('.fulfillment', 'create_fulfillment_leaf_optimizer'), 'FulfillmentLeafOptimizer': ('.fulfillment', 'FulfillmentLeafOptimizer'), 'Case': ('.models', 'Case'), 'Edit': ('.models', 'Edit'), 'Transaction': ('.models', 'Transaction'), 'LeafResult': ('.models', 'LeafResult'), 'CasewiseOptimizer': ('.search', 'CasewiseOptimizer'), 'ModelEditProposer': ('.proposer', 'ModelEditProposer'), 'RepeatedEvaluator': ('.evaluation', 'RepeatedEvaluator'), 'LocalAcceptance': ('.evaluation', 'LocalAcceptance')}
__all__ = list(_EXPORTS)
def __getattr__(name):
    if name not in _EXPORTS:
        raise AttributeError(name)
    module, attribute = _EXPORTS[name]
    value = getattr(import_module(module, __name__), attribute)
    globals()[name] = value
    return value
