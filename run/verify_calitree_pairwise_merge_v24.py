"""Audit parent retention, shared support, rebuilt gates and full routed replay."""
import argparse
from collections import Counter
from pathlib import Path

from critical.core.calibration import pairwise_merge_v24 as merge
from critical.core.calibration import shared_tree_fit_v24 as learner
from critical.core.calibration.counterexample_coverage_v23 import RejectionCoverageGate
from critical.core.decision.artifacts import digest
from critical.core.optimization.prompt.calitree.bound_evidence_cache import BoundEvidenceCache, CachedEvidenceCoveredJudge
from critical.core.optimization.prompt.calitree.task_coverage import LABELS
from run.calitree_counterexample_coverage_v23 import load_examples
from run.calitree_evidence_coverage_v20 import CachedRegularCalls, scores
from run.calitree_task_coverage import ROOT, IDENTITY, read, fingerprint, exact


def independent_sharing(model, rows):
    buckets = {}
    executor = merge.local.PortableRuleExecutor(model['runtime'])
    for row, decision in zip(rows, executor.predict_records([r['features'] for r in rows])):
        if decision['prediction'] == row['reference']:
            path = tuple((c['feature'], c['value']) for c in decision['trace'])
            buckets.setdefault(path, Counter())[row['batch']] += 1
    return {'shared_correct': sum(sum(b.values()) for b in buckets.values() if len(b) > 1),
            'cross_batch_support': sum(sum(b.values()) - max(b.values()) for b in buckets.values()),
            'shared_rules': sum(len(b) > 1 for b in buckets.values())}


def audit(out):
    manifest = read(out / 'manifest.json'); protocol = read(out / 'protocol.json'); summary = read(out / 'results.json')
    assert digest(protocol) == manifest['protocol_ref']
    for name, expected in manifest['source_hashes'].items():
        assert fingerprint(name) == expected, name
    for name, expected in manifest['code_hashes'].items():
        assert fingerprint(ROOT / name) == expected, name
    previous = Path(manifest['previous_gate_run']); prior = Path(manifest['prior_directory'])
    meta = read(prior / 'manifest.json')['cases']; calls = CachedRegularCalls(prior)
    parent_checks = gate_checks = route_checks = local_checks = fallback_checks = child_batches = accepted_count = 0
    all_rows = []; rebuilt_summary = []
    for overview in summary['splits']:
        i = overview['split']; folder = out / f'split{i}'
        result = read(folder / 'development.json'); data = read(folder / 'training_data.json')
        baseline = RejectionCoverageGate(read(folder / 'baseline_gate.json'))
        bank = {m['runtime']['artifact_ref']: m for m in read(folder / 'baseline_models.json')}
        assert set(bank) == set(merge.expert_artifacts(baseline))
        cohorts, bound, _, _, _ = load_examples(previous, i)
        programs = {r['source_group']: bound[r['case']]['example']['program'] for r in data}
        probes = [bound[r['case']]['example'] for scope in ('local', 'outside_training_sources') for r in cohorts[scope]]
        current = baseline
        accepted_by_round = {a['round']: a for a in result['accepted']}
        for round_index in sorted({t['round'] for t in result['trials']}):
            qualified = []
            for trial in (t for t in result['trials'] if t['round'] == round_index and 'parent' in t):
                children = [bank[k] for k in trial['children']]; parent = trial['parent']
                union = set().union(*(set(c['policy']['training']['source_groups']) for c in children))
                selected = sorted((r for r in data if r['source_group'] in union), key=lambda r: r['source_group'])
                reqs = merge.requirements(children, selected); limit = sum(c['complexity']['rules'] for c in children) - 1
                retention = merge.local.gate(parent, selected, reqs, max_rules=limit)
                assert retention == parent['pairwise_lineage']['child_retention'] and retention['status'] == 'accepted'
                assert parent['preserved_requirements'] == reqs and set(parent['fit_sources']) == union
                for key, value in independent_sharing(parent, selected).items():
                    assert parent['sharing'][key] == value
                parent_checks += 1
                proposed = {k: v for k, v in bank.items() if k not in trial['children']}
                proposed[parent['runtime']['artifact_ref']] = parent
                raw_gate, gate_report = merge.rebuild_gate(list(proposed.values()), data, programs, current)
                assert gate_report == trial['gate_fit']
                raw_check = merge.routing_regressions(baseline, raw_gate, probes)
                assert raw_check == trial['routing_before_support']
                rebuilt, preservation = merge.route_support.preserve_routes(baseline, raw_gate, probes)
                assert preservation == trial['route_support_fit']
                candidate = rebuilt if rebuilt is not None else raw_gate
                assert candidate.export() == trial['gate']
                core = merge.route_support.core_artifact(candidate)
                assert core['support_clauses'] == baseline.artifact['support_clauses']
                assert core['calibration_counts'] == baseline.artifact['calibration_counts']
                routing = merge.routing_regressions(baseline, candidate, probes)
                assert routing == trial['routing']
                assert merge.complexity(current) == trial['before'] and merge.complexity(candidate) == trial['after']
                assert set(merge.expert_artifacts(candidate)) <= set(proposed)
                gate_checks += 1; route_checks += len(probes)
                if trial['status'] == 'qualified':
                    assert routing['passed']
                    assert trial['after']['experts'] < trial['before']['experts']
                    assert trial['after']['terminal_rules'] < trial['before']['terminal_rules']
                    assert parent['runtime']['artifact_ref'] in merge.expert_artifacts(candidate)
                    qualified.append((merge.proposal_rank(parent, trial['after']), trial, candidate, proposed))
                else:
                    assert trial['status'] == 'rejected' and trial['reasons']
            if round_index in accepted_by_round:
                event = accepted_by_round[round_index]
                assert qualified
                _, winner, candidate, proposed = min(qualified, key=lambda x: x[0])
                assert event['parent'] == winner['parent'] and event['gate'] == candidate.export()
                assert event['children'] == winner['children'] and event['sharing'] == winner['parent']['sharing']
                parent = event['parent']; children = [bank[k] for k in event['children']]
                if parent['policy']['search'].get('version') == learner.VERSION:
                    union = set(parent['fit_sources']); selected = sorted((r for r in data if r['source_group'] in union), key=lambda r:r['source_group'])
                    preferred = set().union(*(set(c['runtime']['predicate_descriptions']) for c in children))
                    fitted, _ = learner.fit(selected, merge.requirements(children, selected),
                                            max_rules=sum(c['complexity']['rules'] for c in children)-1,
                                            config=learner.Config(**parent['policy']['search']['config']), preferred=preferred)
                    assert fitted['policy'] == parent['policy'] and fitted['runtime'] == parent['runtime']
                current = candidate; bank = {k:v for k,v in proposed.items() if k in merge.expert_artifacts(candidate)}
                accepted_count += 1
            else:
                assert not qualified
        final_gate = merge.route_support.restore(read(folder / 'gate.json'))
        assert final_gate.export() == current.export() == result['gate']
        assert {m['runtime']['artifact_ref']:m for m in result['models']} == bank
        assert result['initial_complexity'] == merge.complexity(baseline) and result['final_complexity'] == merge.complexity(final_gate)
        assert result['final_routing_check'] == merge.routing_regressions(baseline, final_gate, probes)
        assert result['final_routing_check']['passed']
        assert result['work']['pair_fits'] <= result['config']['max_pair_fits']
        assert result['work']['gate_rebuilds'] <= result['config']['max_gate_rebuilds']
        for trial in result['trials']:
            for entry in trial['fits']:
                if 'report' in entry:
                    s=entry['report'];assert s['states'] <= s['config']['max_states'] and s['transitions'] <= s['config']['max_transitions']
        cache = BoundEvidenceCache(IDENTITY, artifact=read(previous / f'split{i}/evidence_cache.json'))
        judge = CachedEvidenceCoveredJudge(calls, final_gate, cache, identity=IDENTITY)
        comparisons = {}
        for scope, old_rows in cohorts.items():
            records = read(folder / f'{scope}_predictions.json'); assert [r['case'] for r in records] == [r['case'] for r in old_rows]
            for record, before in zip(records, old_rows):
                case = meta[record['case']]; b=bound[record['case']]
                kwargs={} if scope=='local' else {'program':b['example']['program'],'observation':b['observation'],'interpretation':b['interpretation']}
                response = judge.judge(case['instruction'],case['evidence'],case_id='independent-merge-audit',**kwargs)
                label = LABELS.index(response['judgment']['label']) if response['judgment']['label'] in LABELS else -1
                assert response['route']==record['route'] and label==record['evidence_gate_tree']==before['evidence_gate_tree']
                assert response['route']['covered']==before['route']['covered']
                if scope=='local':
                    assert response['evidence_source']=='content_cache' and response['source']=='frozen_tree' and label==record['reference'];local_checks+=1
                elif not response['route']['covered']:
                    assert response['execution_ref']==before['fallback_execution_ref']==record['fallback_execution_ref'];fallback_checks+=1
            if scope=='local':
                for b in {r['batch'] for r in records}:
                    selected=[r for r in records if r['batch']==b];assert len(selected)==12 and all(r['evidence_gate_tree']==r['reference'] for r in selected);child_batches+=1
            comparisons[scope]=scores(records);all_rows.extend(records)
        assert comparisons==overview['comparisons']
        assert overview['before']==result['initial_complexity'] and overview['after']==result['final_complexity']
        assert overview['accepted_merges']==len(result['accepted'])
    assert summary['local']==scores([r for r in all_rows if r['scope']=='local'])
    assert summary['development']==scores([r for r in all_rows if r['scope']!='local'])
    checks={'passed':True,'candidate_parent_retention_checks':parent_checks,'fresh_gate_rebuilds_verified':gate_checks,
            'candidate_routing_decisions_replayed':route_checks,'accepted_merges':accepted_count,
            'raw_local_predictions_preserved':local_checks,'original_child_batches_preserved':child_batches,
            'final_local_and_development_predictions_preserved':len(all_rows),'exact_regular_fallbacks_preserved':fallback_checks,
            'fixed_v23_rejection_checks_unchanged':True,'removed_children_not_hidden_in_runtime':True,
            'new_model_calls':0,'reserved_final_predictions':0}
    exact(out/'verification.json',checks)
    exact(out/'completion_seal.json',{'files':{str(p.relative_to(out)):fingerprint(p) for p in sorted(out.rglob('*')) if p.is_file() and p.name!='completion_seal.json'},'auditor_sha256':fingerprint(__file__)})
    print(checks)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True)
    audit(p.parse_args().output_dir.resolve())
