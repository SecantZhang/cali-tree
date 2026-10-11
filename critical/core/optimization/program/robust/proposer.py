"""Compatibility import; historical implementation lives in legacy/."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module("critical.core.optimization.program.legacy.robust.proposer")
