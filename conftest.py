"""Make the package importable during tests without an install."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
