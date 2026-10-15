"""Offline gate-free M2 fitting, semantic regrouping, and conflict diagnostics."""
import argparse
from copy import deepcopy
from pathlib import Path
import json
import shutil

from critical.core.decision.artifacts import digest, save_json
from critical.core.decision.bound_evidence_v2 import VERSION as M1_VERSION
from critical.core.calibration.semantic_hierarchy.features_v4 import project, CONTRACT_REF, SPECS
from critical.core.calibration.semantic_hierarchy.conflict_tree_v4 import ConflictAwareSemanticTree, LIMITS, metrics, conflict_report
from run.calitree_single_call import ROOT, read, fingerprint

VERSION = 'm2-conflict-regrouping-v4'
OLD = ROOT / 'logs/exps/261014-m2-m4-semantic-baselines-v3'
M0 = ROOT / 'logs/exps/261014-semantic-hierarchy-m0-fifty-v1'
M1 = ROOT / 'logs/exps/261014-m1-bound-evidence-development12-v2'
TRAIN = ROOT / 'logs/exps/261014-m2-m4-bound-training48-v1'


def exact(path, value):
    if path.exists():
        if read(path) != value:
            raise ValueError('Frozen experiment changed: ' + str(path))
    else:
        save_json(path,value)


def load_data():
    old = read(OLD/'data.json'); result = {}
    forbidden = {c['group'] for c in read(M0/'splits/test.json')['cases']}
    for partition, directory in [('train',TRAIN),('validation',M1)]:
        observations = {r['case']: r for r in read(directory/'observations.json')}
        cases = {c['case']: c for c in read(M0/'splits'/(partition+'.json'))['cases']}
        rows = []
        for original in old[partition]:
            c = cases[original['case']]; r = observations[c['case']]
            if c['group'] != original['source_group'] or c['group'] in forbidden:
                raise ValueError('Source pairing or reserved source violation')
            features = None
            if r['compilation'] is not None and r['observation'] is not None:
                pair = digest([M1_VERSION,'source_first',c['image_hashes']['source_image'],c['image_hashes']['edited_image']])
                program = r['compilation']['program']
                if program['instruction'] != c['instruction']:
                    raise ValueError('Wrong instruction binding')
                features = project(program,r['observation']['observation'],pair)
            rows.append({**deepcopy(original), 'features': features})
        result[partition] = rows
    if {r['source_group'] for r in result['train']} & {r['source_group'] for r in result['validation']}:
        raise ValueError('Source overlap')
    return result


def prepare(output):
    output.mkdir(parents=True,exist_ok=True)
    protocol = {'version':VERSION, 'feature_contract_ref':CONTRACT_REF, 'limits':LIMITS,
                'target':'Fit all 47 observed training records; retain the missing 48th as unresolved. This is local fitting capacity, not generalization.',
                'grouping':'Jointly supervised partitions after M1; reusable role/kind evidence predicates. Original random batch IDs are not routing inputs.',
                'unknowns':'Preserved as explicit evidence-state indicators; no mandatory label veto. A predicted label does not assert an unknown physical fact is true.',
                'support':'At least two distinct training sources per terminal rule; no source IDs, object names, or instructions in conditions.',
                'selection':'Train48 only. Frozen supplementary dev12 and source-grouped outer folds are diagnostics, not tuning inputs.',
                'new_model_calls':0,'reserved_test_predictions':0}
    exact(output/'protocol.json',protocol)
    code=[Path(__file__).resolve(),ROOT/'critical/core/calibration/semantic_hierarchy/features_v4.py',
          ROOT/'critical/core/calibration/semantic_hierarchy/conflict_tree_v4.py',
          ROOT/'critical/core/decision/bound_evidence_v2.py',ROOT/'critical/core/decision/bound_evidence.py',
          ROOT/'critical/core/decision/artifacts.py',ROOT/'run/calitree_single_call.py']
    inputs=[OLD/'data.json',OLD/'results.json',OLD/'completion_seal.json',M0/'completion_seal.json',
            M0/'splits/train.json',M0/'splits/validation.json',M0/'splits/test.json',
            M1/'observations.json',M1/'completion_seal.json',TRAIN/'observations.json',TRAIN/'results.json']
    manifest={'version':VERSION,'protocol_ref':digest(protocol),
              'code_hashes':{str(p.relative_to(ROOT)):fingerprint(p) for p in code},
              'source_hashes':{str(p.relative_to(ROOT)):fingerprint(p) for p in inputs}}
    exact(output/'manifest.json',manifest)
    for p in code:
        dest=output/'source_snapshot'/p.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True)
        if dest.exists():
            if fingerprint(dest)!=fingerprint(p):raise ValueError('Code snapshot changed')
        else:shutil.copyfile(p,dest)
    data=load_data();exact(output/'data.json',data)
    return data


def fit(rows, path, replay=False):
    if path.exists():
        model=ConflictAwareSemanticTree.restore(read(path))
        ordered=sorted(rows,key=lambda r:r['source_group'])
        t=model.metadata()['training']
        if (t['source_groups']!=[r['source_group'] for r in ordered] or t['target_ref']!=digest([r['reference'] for r in ordered])
                or t['feature_ref']!=digest([r['features'] for r in ordered])):
            raise ValueError('Fit cache mismatch')
        return model
    if replay:raise ValueError('Missing fitted policy in replay')
    model=ConflictAwareSemanticTree().fit([r['features'] for r in rows],[r['reference'] for r in rows],
            source_groups=[r['source_group'] for r in rows],source_batches=[r['batch'] for r in rows])
    exact(path,model.metadata());path.with_suffix('.txt').write_text(model.render()+'\n')
    return model


def evaluate(model, rows):
    predictions=model.predict_records([r['features'] for r in rows])
    return {'metrics':metrics([p['prediction'] for p in predictions],[r['reference'] for r in rows]),
            'cases':[{'case':r['case'],'source_group':r['source_group'],'reference':r['reference'],**p} for r,p in zip(rows,predictions)]}


def run(output, replay=False):
    data=prepare(output);train,dev=data['train'],data['validation']
    # Freeze the selected full-training model before any dev/outer scores.
    model=fit(train,output/'pooled_policy.json',replay)
    training=evaluate(model,train)
    print({'training':training['metrics'],'groups':len(model.metadata()['groups'])},flush=True)
    local={}
    for group in ('G1','G2','G3','G4'):
        rows=[r for r in train if r['batch']==group]
        m=fit(rows,output/'original_groups'/(group+'.json'),replay)
        local[group]=evaluate(m,rows)
    folds={};oof=[]
    for held in ('G1','G2','G3','G4'):
        fitting=[r for r in train if r['batch']!=held];evaluation=[r for r in train if r['batch']==held]
        m=fit(fitting,output/'outer_folds'/(held+'.json'),replay)
        assert not set(m.metadata()['training']['source_groups'])&{r['source_group'] for r in evaluation}
        folds[held]=evaluate(m,evaluation);oof.extend(folds[held]['cases'])
        print({'held_group':held,'correct':folds[held]['metrics']['correct']},flush=True)
    development=evaluate(model,dev)
    old=read(OLD/'results.json')
    conflicts=conflict_report([r['features'] for r in train],[r['reference'] for r in train],[r['source_group'] for r in train])
    bycase={r['case']:r for r in train};a,b=bycase['G1C10'],bycase['G2C08']
    resolved_collision={'cases':[a['case'],b['case']],
        'old_features_equal':next(r for r in read(OLD/'data.json')['train'] if r['case']==a['case'])['features']==next(r for r in read(OLD/'data.json')['train'] if r['case']==b['case'])['features'],
        'new_differences':[k for k in SPECS if a['features']['features'][k]!=b['features']['features'][k]]}
    result={'version':VERSION,'training':training,'original_group_local_fits':local,'outer_folds':folds,
            'oof_metrics':metrics([r['prediction'] for r in oof],[r['reference'] for r in oof]),
            'development12':development,'conflict_report':conflicts,'resolved_old_collision':resolved_collision,
            'semantic_groups':model.metadata()['groups'],
            'baseline':{'training':old['training_pooled_metrics'],'pooled_oof':old['pooled_oof_metrics'],'development12':old['development12']['pooled_metrics']},
            'new_model_calls':0,'reserved_test_predictions':0,
            'limitation':'Training capacity experiment. Group selection is supervised on train48 and evidence-state based; two-source support and generic vocabulary do not establish transfer or repeat robustness.'}
    exact(output/'results.json',result)
    if replay:exact(output/'replay.json',{'exact_replay':True,'new_fits':0,'new_model_calls':0,'results_sha256':fingerprint(output/'results.json')})
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--replay',action='store_true')
    a=p.parse_args();run(a.output_dir.resolve(),a.replay)
