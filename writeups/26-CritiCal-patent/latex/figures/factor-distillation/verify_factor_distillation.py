"""Check the flowers figure against its saved multi-turn pilot transcript."""
from pathlib import Path
import hashlib,json
P=Path(__file__).resolve().parent
r=json.loads((P/'flowers-debate-record.json').read_text())
c=json.loads((P/'flowers-grounding-check.json').read_text())
assert hashlib.sha256(json.dumps(r,sort_keys=True).encode()).hexdigest()==c['record_sha256']
assert set(r)=={'pair_id','round1_A','round2_B','round3_A','referee'}
assert r['pair_id']==c['pair_id']=='assemblybench-e865b88c0906811e'
assert all(isinstance(r[k],str) and r[k] for k in c['turn_fields'])
assert 'opponent' in r['round2_B'].lower() and 'opponent' in r['round3_A'].lower()
assert r['referee']['probability_a']==.85
assert [(f['favors'],f['decisiveness'],f['maps_to_dimension']) for f in r['referee']['contested_factors']]==[('canonical_a',.9,'relevance'),('canonical_a',.6,'visual_quality')]
source=Path(c['source_archive'])
if source.exists():
 original=next(json.loads(line) for line in source.open() if json.loads(line)['pair_id']==r['pair_id'])
 assert original==r
print(json.dumps({'pair_id':r['pair_id'],'advocate_turns':3,'terminal_referee':True,'intermediate_referee_turns':False,'referee_probability_a':.85,'factor_importance':[.9,.6],'model_calls':0},indent=2))
