"""Restore exact pinned sources and analyze saved data without model calls."""
import os
from pathlib import Path
import subprocess
import tempfile

from run.calitree_resume_frozen import ROOT,frozen_workspace

OUTPUT=Path(__file__).resolve().parent

with tempfile.TemporaryDirectory(prefix='sol-proposer-frozen-analysis-') as temporary:
    clone=Path(temporary)/'repository';clone.mkdir();frozen_workspace(OUTPUT,clone)
    subprocess.run([str(ROOT/'.venv/bin/python'),str(OUTPUT/'analyze_saved_run.py')],
        cwd=clone,env={**os.environ,'PYTHONPATH':str(clone)},check=True)
