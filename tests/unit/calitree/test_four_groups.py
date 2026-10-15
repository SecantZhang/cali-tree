"""Group sampling, fit isolation, infeasibility and denominator handling; no APIs."""
from collections import Counter

from run import calitree_four_groups as experiment


def test_four_batches_are_balanced_disjoint_and_deterministic():
    candidates = [{'id':f'{label}-{i}','group':f'{label}-{i}','reference':label,'task':str(i%3)}
                  for label in experiment.LABELS for i in range(20)]
    candidates += [{**candidates[0],'id':'duplicate-source'}]
    excluded = {'no-0','partial-0','yes-0'}
    rows = experiment.select_batches(candidates,excluded)
    assert len(rows) == len({r['group'] for r in rows}) == 48
    assert not {r['group'] for r in rows}&excluded
    assert rows == experiment.select_batches(candidates[::-1],excluded)
    for name in ('G1','G2','G3','G4'):
        assert Counter(r['reference'] for r in rows if r['batch']==name) == {'no':4,'partial':4,'yes':4}


def data():
    cases,observations=[],[]
    for group in range(1,5):
        batch=f'G{group}'
        for i in range(12):
            label=experiment.LABELS[i%3];uid=f'{batch}-{i}'
            cases.append({'case':uid,'id':uid,'batch':batch,'group':'source-'+uid,
                          'instruction':uid,'reference':label})
            observations += [
                {'case':uid,'id':uid,'batch':batch,'arm':'flat','instruction':uid,'prediction':label,'error':None},
                {'case':uid,'id':uid,'batch':batch,'arm':'calitree','instruction':uid,
                 'extraction':{'observations':{'batch_marker':batch}},'error':None}]
    return cases,observations


def spy_class(seen,fail=None):
    class Spy:
        def fit(self,X,y,*,source_groups):
            markers={r['observations']['batch_marker'] for r in X}
            assert len(markers)==1
            name=next(iter(markers));seen.append((name,len(X),list(source_groups)))
            assert all(r['instruction'].startswith(name+'-') for r in X)
            assert all(s.startswith('source-'+name+'-') for s in source_groups)
            if name==fail:raise ValueError('No supported class-complete policy')
            self.targets=dict(zip([r['instruction'] for r in X],y));return self
        def predict_records(self,X):
            return [{'label':experiment.LABELS[self.targets[x['instruction']]]} for x in X]
        def metadata(self):return {'test_policy':True}
    return Spy


def test_each_policy_fits_only_its_own_twelve_cases(monkeypatch):
    seen=[];monkeypatch.setattr(experiment,'ClassBalancedEvidenceRuleCalibrator',spy_class(seen))
    cases,observations=data();batches,summary,artifacts=experiment.fit_batches(cases,observations)
    assert [(name,n) for name,n,_ in seen]==[(f'G{i}',12) for i in range(1,5)]
    assert summary['qualified_count']==4 and summary['qualified_local']['correct']==48
    for name,entry in artifacts.items():
        assert len(entry['fit_case_ids'])==12 and all(uid.startswith(name+'-') for uid in entry['fit_case_ids'])


def test_infeasible_group_is_not_replaced_or_silently_relaxed(monkeypatch):
    seen=[];monkeypatch.setattr(experiment,'ClassBalancedEvidenceRuleCalibrator',spy_class(seen,fail='G2'))
    cases,observations=data();batches,summary,_=experiment.fit_batches(cases,observations)
    assert len(seen)==4 and batches['G2']['fit_status']=='infeasible'
    assert batches['G2']['local_metrics'] is None
    assert summary['qualified_count']==3
    assert summary['qualified_local']['total']==36 and summary['flat_same_qualified_cases']['total']==36
    assert summary['all48_with_failed_group_abstentions']['total']==48
    assert summary['all48_with_failed_group_abstentions']['correct']==36


def test_invalid_extraction_stays_in_twelve_case_denominator(monkeypatch):
    seen=[];monkeypatch.setattr(experiment,'ClassBalancedEvidenceRuleCalibrator',spy_class(seen))
    cases,observations=data()
    for row in observations:
        if row['id']=='G1-0' and row['arm']=='calitree':row['extraction']=None;row['error']='retained failure'
    batches,_,_=experiment.fit_batches(cases,observations)
    assert batches['G1']['valid_extractions']==11
    assert batches['G1']['local_metrics']['total']==12 and batches['G1']['local_metrics']['correct']==11
