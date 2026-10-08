"""Run saved-data analysis with the exact recorded runtime, without API calls."""
import os
from pathlib import Path
import subprocess
import tempfile

from run.calitree_resume_frozen import ROOT, frozen_workspace


def main():
    output=Path(__file__).resolve().parent
    with tempfile.TemporaryDirectory(prefix='calitree-frozen-analysis-') as temporary:
        workspace=Path(temporary)/'repository';workspace.mkdir()
        frozen_workspace(output,workspace)
        child=subprocess.run([str(ROOT/'.venv/bin/python'),str(output/'analyze_saved_run.py')],
            cwd=workspace,env={**os.environ,'PYTHONPATH':str(workspace)})
        if child.returncode:
            raise RuntimeError('Frozen analysis failed; no provider was contacted')


if __name__=='__main__':main()
