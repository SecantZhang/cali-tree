"""Lazy legacy runtime exports; persisted v3 contracts retain their executor."""
from importlib import import_module
_EXPORTS={name:('.models',name) for name in ('RobustProgram','Node','Inference','export_program','restore_program')}
_EXPORTS.update({name:('.executor',name) for name in ('RobustExecutor','RobustChecker')})
__all__=list(_EXPORTS)
def __getattr__(name):
    if name not in _EXPORTS:raise AttributeError(name)
    module,attribute=_EXPORTS[name]
    value=getattr(import_module(module,__name__),attribute)
    globals()[name]=value
    return value
