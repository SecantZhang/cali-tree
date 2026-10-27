"""Compare warrant-seeded grading and semantic reliability routing offline."""
import argparse
from pathlib import Path
from dataclasses import replace
import shutil

import numpy as np

from critical.core.calibration import rubric_evidence_v73 as evidence
from critical.core.calibration.seeded_rubric_v73 import SeededRubric, Search, DESCRIPTIONS
from critical.core.decision.artifacts import save_json, digest
from run.calitree_semantic_rubric_v70 import data, FROZEN, STUDY, ROOT, read, fingerprint
from run.calitree_warranted_rubric_v71 import TEACHERS, INNER
from run.calitree_accuracy_headroom_v37 import accuracy


def arrays():
    examples, original_names, X = data()
    selected = [i for i, n in enumerate(original_names) if n in DESCRIPTIONS]
    names = [original_names[i] for i in selected] + list(evidence.SEMANTIC) + list(evidence.VIEWS)
    semantic, rows = [], []
    for raw in read(FROZEN / 'replay_inputs_without_references.json'):
        pair = raw['observation']['image_pair_ref'] if raw['observation'] else None
        flags = evidence.project(raw['program'], raw['observation'], pair, raw['interpretation'])
        semantic.append(flags or dict.fromkeys(evidence.SEMANTIC, False))
        rows.append([int(semantic[-1][n]) for n in evidence.SEMANTIC])
    base = np.concatenate([X[:, selected], np.asarray(rows, dtype=np.float32)], axis=1)
    return examples, names, base, semantic


def attach(base, semantic, support, regular):
    extra = [evidence.views(s, list(map(float, ps)), int(r)) for s, ps, r in zip(semantic, support, regular)]
    return np.concatenate([base, np.asarray([[int(v[n]) for n in evidence.VIEWS] for v in extra], dtype=np.float32)], axis=1)


def run(out):
    if out.exists():
        raise ValueError('Fresh experiment directory required')
    examples, names, raw, semantic = arrays()
    y = np.asarray([e['reference'] for e in examples]);groups = np.asarray([e['source_group'] for e in examples])
    regular = np.asarray([e['regular'] for e in examples]);valid = np.asarray([e['covered'] for e in examples])
    positions = {e['case']: i for i, e in enumerate(examples)}
    configs = [Search(family=f, max_features=192, loss_cost=cost) for f in ('semantic', 'grounded', 'auxiliary') for cost in (1., 2.)]
    configs += [Search(family='auxiliary', mode=mode, max_features=192) for mode in ('grades', 'routes')]
    labels = [c.family + '_' + c.mode + '_cost' + str(c.loss_cost) for c in configs]
    protocol = {'version': SeededRubric.version, 'configs': [vars(c) for c in configs],
                'target': 'Strictly over85% requires235/276; retain99 originals/144 slots and upstream bound-evidence coverage.',
                'semantic_changes': 'Keep distinct semantic columns; begin every search at an explicit grading warrant or a review/defer reason. Same-requirement witnesses prevent cross-requirement shortcuts.',
                'routing': 'An uncertainty rule delegates to the independent existing visual judge, not an unsupported failure grade. Model supports are labelled routing cues, never truth probabilities.',
                'source_control': 'Same five v64 outer source folds and30 inner source-excluded teacher caches. All held-source siblings excluded. Original-source fitting views explicitly supervised.',
                'new_paid_calls': 0, 'reserved_sources_used': 0, 'serving_changed': False}
    out.mkdir(parents=True)
    save_json(out / 'protocol.json', protocol)
    files = [Path(__file__), ROOT/'critical/core/calibration/rubric_evidence_v73.py', ROOT/'critical/core/calibration/seeded_rubric_v73.py']
    hashes = {str(p): fingerprint(p) for p in files}
    for p in files:
        dest=out/'source_snapshot'/p.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
    (out/'run.log').write_text('Warrant-seeded semantic grading/reliability comparison in progress.\n')
    (out/'llm-histories.log').write_text('Zero API calls; cached raw bound evidence and native teacher predictions only.\n')
    baseline = {r['case']:r for r in read(STUDY/'predictions.json') if r['candidate']=='boost_full_vision'}
    records, retention = [], []
    for f in (f for f in read(STUDY/'folds.json') if f['candidate']=='boost_full_vision'):
        train=[positions[c] for c in f['train_cases']];held=[positions[c] for c in f['held_cases']]
        assert not set(groups[train]) & set(groups[held])
        folder=TEACHERS/('fold'+str(f['fold']));saved=read(folder/'predictions.json')
        full_ps=np.asarray(saved['support']);oof_ps=full_ps.copy()
        trace=[]
        for inner in range(5):
            cache=INNER/folder.name/('inner'+str(inner));entry=read(cache/'membership.json')
            excluded=set(entry['held_sources'])
            assert not set(entry['training_sources']) & (excluded | set(groups[held]))
            assert read(cache/'teacher.json')['contract']['rows']==[i for i in train if groups[i] not in excluded]
            indices=[i for i in train if groups[i] in excluded]
            oof_ps[indices]=np.asarray(read(cache/'predictions.json')['support'])[indices]
            trace.append(entry)
        actual=np.argmax(full_ps,axis=1);oof=np.argmax(oof_ps,axis=1)
        actual[~valid]=regular[~valid];oof[~valid]=regular[~valid]
        assert np.all(actual[:99]==y[:99]) and all(actual[i]==baseline[examples[i]['case']]['direct'] for i in held)
        full=attach(raw,semantic,full_ps,regular);training=attach(raw,semantic,oof_ps,regular)
        priority={n:saved['priority'].get(n,0.) + (1000 if n.startswith('meaning_') else 1500 if n.startswith('rubric_') else 0) for n in names}
        fit=[i for i in train if valid[i]];output_folder=out/folder.name
        save_json(output_folder/'memberships.json',{'train_cases':f['train_cases'],'held_cases':f['held_cases'],'inner_folds':trace})
        for name,config in zip(labels,configs):
            rubric=SeededRubric(names,config).fit(training[fit],y[fit],groups=groups[fit].tolist(),base=oof[fit],regular=regular[fit],
                protected_X=full[:99],protected_y=y[:99],protected_base=actual[:99],protected_regular=regular[:99],priority=priority)
            predicted=np.asarray(rubric.predict(full,base=actual,regular=regular));predicted[~valid]=regular[~valid]
            assert np.all(predicted[:99]==y[:99])
            artifact=rubric.artifact(digest(read(folder/'teacher.json')))
            save_json(output_folder/(name+'.json'),artifact);(output_folder/(name+'.txt')).write_text(rubric.render())
            retention.append({'candidate':name,'fold':f['fold'],'original_correct':int(np.sum(predicted[:99]==y[:99])),
                              'rules':len(rubric.rules),'conditions':sum(len(r['conditions']) for r in rubric.rules)})
            for i in held:
                records.append({**examples[i],'teacher':int(actual[i]),'prediction':int(predicted[i]),'candidate':name,'fold':f['fold']})
        save_json(out/'predictions.json',records);save_json(out/'retention.json',retention)
        print({'fold':f['fold'],'held_cases':len(held),'rules':{c['candidate']:c['rules'] for c in retention if c['fold']==f['fold']}},flush=True)
    results={}
    for name in labels:
        rows=[r for r in records if r['candidate']==name]
        results[name]={'accuracy':accuracy(rows,'prediction'),'teacher':accuracy(rows,'teacher'),
            'gains':sum(r['prediction']==r['reference']!=r['teacher'] for r in rows),
            'losses':sum(r['teacher']==r['reference']!=r['prediction'] for r in rows),
            'changes':sum(r['prediction']!=r['teacher'] for r in rows), 'upstream_evidence_coverage':sum(r['covered'] for r in rows),
            'all_original_fits_retained':all(r['original_correct']==99 for r in retention if r['candidate']==name)}
    assert all(fingerprint(p)==sha for p,sha in hashes.items())
    save_json(out/'results.json',results)
    save_json(out/'manifest.json',{'code_sha256':hashes,'matrix_ref':digest(raw.tolist()),'target_ref':digest(y.tolist()),'semantic_contract_ref':evidence.CONTRACT_REF})
    (out/'run.log').write_text('All outer controls reproduced222/276; warrant-seeded grading and review routing compared with original99 retained. No paid or reserved-source use.\n')
    print(results,flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output-dir',type=Path,required=True)
    run(parser.parse_args().output_dir.resolve())
