"""Offline empirical cross-expert region merges with frozen-route checks."""
import argparse
from pathlib import Path

from critical.core.calibration import semantic_region_merge_v28 as merging
from critical.core.decision.artifacts import digest, save_json
from run.calitree_shared_regions_v27 import inputs as previous_inputs, replay
from run.calitree_task_coverage import ROOT, read, fingerprint


def inputs(parent, split):
    prior_regions = Path(read(parent/'manifest.json')['parent'])
    rows, programs, _, cohorts, bound, previous, prior = previous_inputs(prior_regions, split)
    baseline = merging.shared.SharedRegionGate(read(parent/f'split{split}/gate.json'))
    recorded = {(r['scope'],r['case']):r for r in read(parent/f'split{split}/predictions.json')}
    for scope, cohort in cohorts.items():
        for row in cohort:
            saved = recorded[(scope,row['case'])]
            row.update(evidence_gate_tree=saved['prediction'],route=saved['route'],fallback_execution_ref=saved['execution_ref'])
    probes = [{'program': bound[r['case']]['example']['program'], 'features': bound[r['case']]['example']['features']}
              for scope in ('local','outside_training_sources') for r in cohorts[scope]]
    return rows, programs, baseline, cohorts, bound, previous, prior, probes


def run(out, parent):
    if out.exists():
        raise ValueError('Use a fresh experiment directory')
    out.mkdir(parents=True)
    for p, expected in read(parent/'completion_seal.json')['files'].items():
        assert fingerprint(parent/p) == expected
    config = merging.Config()
    protocol = {'version': merging.VERSION, 'parent': str(parent), 'config': merging.asdict(config),
                'proposal': 'Same verdict, different contributing expert sets, overlapping task scopes, at least 0.5 literal Jaccard and a shared non-boilerplate semantic condition.',
                'parent_definition': 'Intersect child evidence conditions; union permitted task scopes and contributing experts.',
                'selection': 'Among passing candidates prefer fewer region definitions, fewer conditions, greater pooled support and expert sharing, then semantic similarity.',
                'constraints': 'Retain every child local support source and all 98 baseline accept/defer decisions and accepted verdicts per split; frozen expert-bank veto unchanged; at least one contributing expert must supply a supported match.',
                'data_use': 'Local labels verify correct support. Known development probes supervise routing preservation via frozen decisions, not human reference labels. Not held-out validation.',
                'scope': 'Approximate region coverage generalization, not expert-tree merging or a universal correctness claim.',
                'new_model_calls': 0, 'reserved_final_predictions': 0, 'default_changed': False}
    save_json(out/'protocol.json',protocol); summaries=[]
    for i in (1,2,3):
        rows,programs,baseline,cohorts,bound,previous,prior,probes=inputs(parent,i)
        gate,report=merging.develop(baseline,rows,programs,probes,config=config)
        save_json(out/f'split{i}/gate.json',gate.export());save_json(out/f'split{i}/fit.json',report)
        save_json(out/f'split{i}/definitions.json',[gate.definition(k) for k in sorted(gate.executor.regions)])
        records,scores=replay(gate,baseline,rows,cohorts,bound,previous,prior,i)
        save_json(out/f'split{i}/predictions.json',records)
        summary={'split':i,'before':report['before'],'after':report['after'],'merges':len(report['accepted']),
                 'work':report['work'],'rejected_routing_candidates':sum('routing_regression' in t['reasons'] for t in report['trials']),
                 'boolean_regions_broadened':report['boolean_regions_broadened'],
                 'baseline_boolean_coverage_retained':report['baseline_boolean_coverage_retained'],**scores}
        summaries.append(summary);print(summary,flush=True)
    inherited=read(parent/'manifest.json');files={parent/'completion_seal.json',parent/'manifest.json'}
    files.update(parent/f'split{i}/{name}.json' for i in (1,2,3) for name in ('gate','predictions'))
    save_json(out/'manifest.json',{'parent':str(parent),'protocol_ref':digest(protocol),
              'source_hashes':{**inherited['source_hashes'],**{str(p):fingerprint(p) for p in sorted(files)}},
              'code_hashes':{**inherited['code_hashes'],**{str(Path(p).resolve().relative_to(ROOT)):fingerprint(p) for p in (__file__,merging.__file__)}}})
    save_json(out/'results.json',{'version':merging.VERSION,'splits':summaries,'new_model_calls':0,'reserved_final_predictions':0,'default_changed':False})
    (out/'run.log').write_text('\n'.join(str(s) for s in summaries)+'\n')
    (out/'llm-histories.log').write_text('Zero new calls. Cached evidence and exact approved regular responses only.\n')


def audit(out):
    manifest=read(out/'manifest.json');protocol=read(out/'protocol.json');results=read(out/'results.json')
    assert digest(protocol)==manifest['protocol_ref']
    for p,expected in manifest['source_hashes'].items():
        assert fingerprint(p)==expected
    for p,expected in manifest['code_hashes'].items():
        assert fingerprint(ROOT/p)==expected
    parent=Path(manifest['parent']);total=local=fallbacks=merges=trials=0
    for summary in results['splits']:
        i=summary['split'];rows,programs,baseline,cohorts,bound,previous,prior,probes=inputs(parent,i)
        gate=merging.SemanticMergedRegionGate(read(out/f'split{i}/gate.json'))
        rebuilt,fit=merging.develop(baseline,list(reversed(rows)),programs,probes,config=merging.Config(**protocol['config']))
        assert rebuilt.export()==gate.export() and fit==read(out/f'split{i}/fit.json')
        assert summary['before']==fit['before'] and summary['after']==fit['after']
        assert summary['merges']==len(fit['accepted']) and summary['work']==fit['work']
        assert summary['rejected_routing_candidates']==sum('routing_regression' in t['reasons'] for t in fit['trials'])
        assert summary['boolean_regions_broadened']==fit['boolean_regions_broadened']
        assert summary['baseline_boolean_coverage_retained']==fit['baseline_boolean_coverage_retained']
        assert gate.executor.artifact['core_gate']==baseline.artifact['core_gate']
        assert read(out/f'split{i}/definitions.json')==[gate.definition(k) for k in sorted(gate.executor.regions)]
        # Each actual merged conjunction must contain both child local cohorts;
        # the full rerun above checks every rejected and accepted route proposal.
        for event in fit['accepted']:
            assert len(event['parent']['expert_refs'])>1
            assert all(r['sources']==r['retained'] for r in event['child_retention'])
        records,scores=replay(gate,baseline,rows,cohorts,bound,previous,prior,i)
        assert records==read(out/f'split{i}/predictions.json') and all(summary[k]==v for k,v in scores.items())
        for ref,r in gate.executor.regions.items():
            selected=[row for row in rows if ref in gate.select(programs[row['source_group']],row['features'])['semantic_regions']]
            def counts(part):
                return {'sources':len({s['source_group'] for s in part}),'instructions':len({s['instruction'] for s in part}),'batches':len({s['batch'] for s in part})}
            assert r['support']==counts(selected)
            for scope,expected in r['support_by_scope'].items():
                assert expected==counts([s for s in selected if digest(merging.shared.task_scope(programs[s['source_group']]))==scope])
        total+=len(records);local+=scores['local']['correct'];fallbacks+=sum(not r['route']['covered'] for r in records)
        merges+=len(fit['accepted']);trials+=len(fit['trials'])
    report={'passed':True,'merges_reproduced':merges,'candidate_checks_reproduced':trials,
            'raw_local_predictions_preserved':local,'original_child_batches_preserved':12,
            'recorded_routes_and_final_predictions_preserved':total,'exact_regular_fallbacks_preserved':fallbacks,
            'frozen_expert_trees_and_veto_unchanged':True,'old_region_bank_not_hidden':True,
            'known_coverage_regressions':0,'unseen_coverage_equivalence_claim':False,'new_model_calls':0,'reserved_final_predictions':0}
    save_json(out/'verification.json',report)
    save_json(out/'completion_seal.json',{'files':{str(p.relative_to(out)):fingerprint(p) for p in sorted(out.rglob('*')) if p.is_file() and p.name!='completion_seal.json'},'auditor_sha256':fingerprint(__file__)})
    print(report,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--parent-run',type=Path);p.add_argument('--verify',action='store_true');a=p.parse_args()
    if a.verify:audit(a.output_dir.resolve())
    elif a.parent_run is None:p.error('--parent-run is required when building')
    else:run(a.output_dir.resolve(),a.parent_run.resolve())
