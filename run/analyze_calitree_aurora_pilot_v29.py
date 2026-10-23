"""Paired source-cluster comparisons for the completed frozen pilot."""
import argparse
from collections import Counter
from pathlib import Path
import random

from critical.core.decision.artifacts import save_json
from run.calitree_aurora_pilot_v29 import read, fingerprint
from run.collect_calitree_aurora_pilot_v29r1 import metrics,verify_execution


def paired(rows,arm,baseline='regular',draws=4000):
    groups={key:[r for r in rows if r['source_group']==key]for key in sorted({r['source_group']for r in rows})}
    differences={key:sum(int(r[arm]==r['reference'])-int(r[baseline]==r['reference'])for r in rs) for key,rs in groups.items()}
    rng=random.Random(20261020);keys=list(groups);distribution=[]
    for _ in range(draws):
        sample=rng.choices(keys,k=len(keys))
        distribution.append(sum(differences[k]for k in sample)/sum(len(groups[k])for k in sample))
    distribution.sort()
    return {'versus':baseline,'wins':sum(r[arm]==r['reference'] and r[baseline]!=r['reference']for r in rows),
            'losses':sum(r[arm]!=r['reference'] and r[baseline]==r['reference']for r in rows),
            'accuracy_difference':sum(differences.values())/len(rows),
            'paired_source_bootstrap_95':[distribution[int(draws*.025)],distribution[int(draws*.975)-1]],
            'changed_prediction_cases':[r['case']for r in rows if r[arm]!=r[baseline]]}


def analyze(out):
    verify_execution(out);assert read(out/'collection/verification.json')['passed']
    rows=read(out/'collection/predictions.json');arms=['regular']+[f'{v}_split{i}'for v in ('v27','v28')for i in (1,2,3)]
    comparisons={a:{'metrics':metrics(rows,a),'versus_regular':paired(rows,a),
                    'wrong_accepted_cases':[r['case']for r in rows if a!='regular' and r['routes'][a]['covered'] and r[a]!=r['reference']]}
                 for a in arms}
    comparison_v28={str(i):paired(rows,f'v28_split{i}',f'v27_split{i}')for i in (1,2,3)}
    result={'outputs':len(rows),'source_groups':len({r['source_group']for r in rows}),
            'class_counts':dict(Counter(r['reference']for r in rows)),
            'always_no_accuracy':sum(r['reference']==0 for r in rows)/len(rows),
            'comparisons':comparisons,'v28_versus_v27':comparison_v28,
            'routing_reasons':{a:dict(Counter(r['routes'][a]['reason']for r in rows))for a in arms if a!='regular'},
            'case_errors':[{'case':r['case'],'regular_error':r['regular_error'],'extraction_error':r['extraction_error']}for r in rows if r['regular_error'] or r['extraction_error']],
            'common_successful_cases':{a:metrics([r for r in rows if not r['regular_error'] and not r['extraction_error']],a)for a in arms},
            'exposure_breakdown':{value:{a:metrics([r for r in rows if r['historical_exposure']==value],a)for a in arms}
                                  for value in sorted({r['historical_exposure']for r in rows})},
            'notes':['Frozen banks are reported separately, not selected on pilot outcomes.',
                     '80 outputs are clustered into 16 sources; half the sources have disclosed older exposure.',
                     'Intervals are descriptive paired source-cluster bootstrap estimates from a small pilot.']}
    save_json(out/'collection/comparison.json',result)
    save_json(out/'analysis_seal.json',{'completion_seal_sha256':fingerprint(out/'completion_seal.json'),
              'comparison_sha256':fingerprint(out/'collection/comparison.json'),'analyzer_sha256':fingerprint(__file__)})
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True)
    result=analyze(p.parse_args().output_dir.resolve())
    for name,row in result['comparisons'].items():print(name,row['metrics'],row['versus_regular'],flush=True)
