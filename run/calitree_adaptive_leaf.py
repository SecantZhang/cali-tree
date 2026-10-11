"""Compatibility runner; new runs default to fulfillment. Historical modes remain explicit."""
from importlib import import_module
import sys
_module=import_module('run.legacy.calitree_adaptive_leaf')
if __name__=='__main__':
    _module.main()
else:
    sys.modules[__name__]=_module
