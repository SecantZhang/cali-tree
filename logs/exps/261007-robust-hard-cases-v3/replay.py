"""Verify completed saved execution with provider construction forbidden."""
import json
from pathlib import Path
import shutil
import tempfile

from run.calitree_robust_leaf_optimization import execute

root = Path(__file__).resolve().parent
manifest = json.loads((root/'manifest.json').read_text())
original = json.loads((root/'results.json').read_text())
assert original['status'] == 'completed'

def forbidden(_):
    raise AssertionError('Replay attempted to construct a provider engine')

with tempfile.TemporaryDirectory(prefix='calitree-hard-replay-') as temporary:
    copied = Path(temporary)/'run'
    shutil.copytree(root, copied)
    before = json.loads((copied/'budget.json').read_text())
    replayed = execute(copied, manifest, forbidden)
    after = json.loads((copied/'budget.json').read_text())
    assert replayed['status'] == 'completed'
    assert replayed['cases'] == original['cases']
    assert replayed['returned_models'] == original['returned_models']
    assert before == after == original['budget']
    result = {'verification': 'passed', 'case_arm_results': sum(len(v) for v in replayed['cases'].values()),
              'additional_calls': after['calls']-before['calls'], 'budget_exact': True, 'cases_exact': True}
(root/'replay_verification.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
