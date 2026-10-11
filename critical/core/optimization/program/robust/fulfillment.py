"""Compatibility import for the canonical fulfillment optimizer."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module("critical.core.optimization.program.fulfillment")
