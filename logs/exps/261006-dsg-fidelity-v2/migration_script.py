from pathlib import Path
import json,shutil
from hashlib import sha256
from run.calitree_dsg_fidelity import preflight
old=Path('logs/exps/261006-dsg-fidelity-v1');new=Path('logs/exps/261006-dsg-fidelity-v2')
assert not new.exists()
preflight(new)
for name in ('jobs','draws'):
 if (old/name).exists():shutil.copytree(old/name,new/name)
for name in ('budget.json','original_observations.jsonl','llm-histories.log','run.log','verify_run.py'):
 if (old/name).exists():shutil.copy2(old/name,new/name)
(new/'preparation').mkdir()
for path in (old/'preparation').glob('*.json'):
 if path.stem not in ('6','7'):shutil.copy2(path,new/'preparation'/path.name)
b=json.loads((new/'budget.json').read_text())
info={'from':str(old),'reason':'Remove undocumented ID character restriction; retain every attempted slot and completed draw. No question, template, scoring or threshold changes.',
 'recovered_preparation_indices':[6,7],'retained_attempts':b['calls'],'retained_budget_sha256':sha256((old/'budget.json').read_bytes()).hexdigest(),
 'previous_manifest_sha256':sha256((old/'manifest.json').read_bytes()).hexdigest(),'interrupted_slots':[p.stem for p in (old/'jobs').glob('*.json') if json.loads(p.read_text())['outcome']=='interrupted']}
(new/'migration.json').write_text(json.dumps(info,indent=2))
print(json.dumps(info,indent=2))
