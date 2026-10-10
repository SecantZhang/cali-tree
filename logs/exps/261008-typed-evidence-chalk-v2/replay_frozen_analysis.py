"""Run saved analysis under exactly the recorded source snapshot, without network."""
import os
from pathlib import Path
import subprocess
import tempfile
from run.calitree_resume_frozen import ROOT, frozen_workspace


def main():
    output=Path(__file__).resolve().parent
    with tempfile.TemporaryDirectory(prefix='calitree-typed-frozen-') as temporary:
        workspace=Path(temporary)/'repository';workspace.mkdir();frozen_workspace(output,workspace)
        process=subprocess.run([str(ROOT/'.venv/bin/python'),str(output/'analyze_saved_run.py')],cwd=workspace,
            env={**os.environ,'PYTHONPATH':str(workspace)})
        if process.returncode:raise RuntimeError('Frozen analysis failed; no API calls made')


if __name__=='__main__':main()
