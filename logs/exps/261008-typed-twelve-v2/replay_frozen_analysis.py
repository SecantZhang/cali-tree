"""Restore recorded source snapshots for offline twelve-case replay."""
import os
from pathlib import Path
import subprocess
import tempfile
from run.calitree_resume_frozen import ROOT,frozen_workspace


def main():
    output=Path(__file__).resolve().parent
    with tempfile.TemporaryDirectory(prefix='calitree-twelve-frozen-') as temporary:
        workspace=Path(temporary)/'repository';workspace.mkdir();frozen_workspace(output,workspace)
        r=subprocess.run([str(ROOT/'.venv/bin/python'),str(output/'analyze_saved_run.py')],cwd=workspace,
                         env={**os.environ,'PYTHONPATH':str(workspace)})
        if r.returncode:raise RuntimeError('Frozen twelve-case analysis failed')


if __name__=='__main__':main()
