"""Lazy public exports; historical APIs load only when requested."""
from importlib import import_module
_EXPORTS = {'ProgramSpec': ('.models', 'ProgramSpec'), 'Requirement': ('.models', 'Requirement'), 'Outcome': ('.models', 'Outcome'), 'Check': ('.models', 'Check'), 'Observation': ('.models', 'Observation'), 'DecisionResult': ('.models', 'DecisionResult'), 'ProgramExecutor': ('.executor', 'ProgramExecutor'), 'ModelChecker': ('.executor', 'ModelChecker'), 'export_program': ('.artifacts', 'export_program'), 'restore_program': ('.artifacts', 'restore_program'), 'program_ref': ('.artifacts', 'program_ref')}
__all__ = list(_EXPORTS)
def __getattr__(name):
    if name not in _EXPORTS:
        raise AttributeError(name)
    module, attribute = _EXPORTS[name]
    value = getattr(import_module(module, __name__), attribute)
    globals()[name] = value
    return value
