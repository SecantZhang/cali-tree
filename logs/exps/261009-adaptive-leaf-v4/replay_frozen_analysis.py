"""Restore pinned sources in a temporary checkout and verify zero-call replay."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from run.calitree_resume_frozen import frozen_workspace

source=Path(__file__).resolve().parent
with tempfile.TemporaryDirectory(prefix='calitree-v4-replay-') as temporary:
    clone=Path(temporary)/'repository';clone.mkdir()
    frozen_workspace(source,clone)
    legacy=Path('logs/exps/261006-optimizer-comparison-v1/manifest.json')
    (clone/legacy).parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/legacy,clone/legacy)
    script=clone/'logs/exps/261009-adaptive-leaf-v4/analyze_saved_run.py'
    script.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source/'analyze_saved_run.py',script)
    subprocess.run([str(ROOT/'.venv/bin/python'),str(script),'--directory',str(source),'--replay'],
                   cwd=clone,env={**os.environ,'PYTHONPATH':str(clone)},check=True)
