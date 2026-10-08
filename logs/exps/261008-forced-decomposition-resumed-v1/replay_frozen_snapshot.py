"""Replay the original experiment after code updates, using its frozen sources."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

DIRECTORY=Path(__file__).resolve().parent
ROOT=DIRECTORY.parents[2]


def replay():
    manifest=json.loads((DIRECTORY/'manifest.json').read_text())
    with tempfile.TemporaryDirectory() as temporary:
        clone=Path(temporary).resolve()/'repository';clone.mkdir()
        ignored=shutil.ignore_patterns('__pycache__','.DS_Store','*.pyc')
        for folder in ('critical','run'):
            shutil.copytree(ROOT/folder,clone/folder,ignore=ignored)
        for relative,expected in manifest['code_hashes'].items():
            source=DIRECTORY/'source_snapshot'/relative
            assert hashlib.sha256(source.read_bytes()).hexdigest()==expected
            dest=clone/relative;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,dest)
        # Remove later format-guidance files from the old template inventory.
        for path in (clone/'critical/core/prompts/templates/forced_decomposition_v1').glob('*.txt'):
            if str(path.relative_to(clone)) not in manifest['code_hashes']:path.unlink()
        historical='logs/exps/261007-robust-hard-cases-v3'
        (clone/historical).mkdir(parents=True)
        shutil.copyfile(ROOT/historical/'manifest.json',clone/historical/'manifest.json')
        shutil.copytree(ROOT/historical/'prepared',clone/historical/'prepared')
        output=clone/'logs/exps'/DIRECTORY.name
        shutil.copytree(DIRECTORY,output,ignore=shutil.ignore_patterns('llm-histories.log','textgrad-v3','source_snapshot'))
        shutil.copytree(DIRECTORY/'source_snapshot',output/'source_snapshot')
        completed=subprocess.run([str(ROOT/'.venv/bin/python'),str(output/'verify_saved_run.py')],
            cwd=clone,env={**os.environ,'PYTHONPATH':str(clone)},capture_output=True,text=True)
        if completed.returncode:raise RuntimeError(completed.stdout+'\n'+completed.stderr)
        verification=json.loads((output/'protocol_verification.json').read_text())
        verification['frozen_sources_verified']=True
        (DIRECTORY/'snapshot_replay_verification.json').write_text(json.dumps(verification,indent=2)+'\n')
        print(json.dumps({'status':'verified','calls':verification['calls'],'zero_call_replay':True,'frozen_sources_verified':True}))


if __name__=='__main__':replay()
