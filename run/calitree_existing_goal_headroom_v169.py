"""Reference-informed ceilings for cached goal opinions, never achieved accuracy."""
import argparse
from pathlib import Path
import shutil

from critical.core.decision.bound_evidence_v2 import derive_record
from critical.core.decision.artifacts import digest, save_json
from critical.lm_engine.local_qwen_v94 import file_hash
from run.calitree_compact_balance_v143 import CACHE, CACHE_AUDIT, VERIFIED
from run.verify_calitree_semantic_residual_v105 import load
from run.calitree_semantic_rubric_v70 import ROOT, FROZEN, read
from run.verify_calitree_facet_probe_v151 import classification_metrics


def goal_complete(raw):
    """Separate the interpreter's endpoint opinion from physical verification."""
    if raw['observation'] is None or raw['interpretation'] is None:
        return False, False
    program = raw['program']; observation = raw['observation']; pair = observation['image_pair_ref']
    bound = derive_record(program, observation, pair)
    semantic = []; physical = []
    for key, meaning in raw['interpretation']['requirements'].items():
        complete = (meaning['progress'] == 'requested_endpoint' and meaning['endpoint_gap'] == 'none' and
                    meaning['evidence_consistency'] == 'coherent')
        states = [c['desired_state'] for c in bound['checks'].values() if c['role'] == 'outcome' and
                  key in c['requirement_ids'] and c['desired_state'] != 'not_applicable']
        semantic.append(complete)
        physical.append(complete and bool(states) and all(s == 'true' for s in states))
    return bool(semantic) and all(semantic), bool(physical) and all(physical)


def run(out):
    if out.exists():
        raise ValueError('Fresh cached-goal ceiling diagnostic required')
    protocol = {'version': 'existing-goal-opinion-headroom-v169',
        'semantic_goal_complete': 'Every bound interpreted requirement coherently reports requested_endpoint and endpoint_gap=none. This is a model opinion, not a physical certificate.',
        'physical_goal_complete': 'Additionally every applicable outcome-role physical check is true; identity/preservation roles are not universal caps.',
        'proposal_sets': ['existing_warrants', 'physical_goal_relaxed', 'semantic_goal_relaxed', 'combined_with_regular'],
        'oracle': 'For each case, use the reference only to ask whether ANY offered grade could correct V112. If not, retain V112. No gates fitted and no predictions deployed.',
        'domain': 'All276 source-held development cases; new opinions offered only inside existing valid/covered domain. No prior-priority restriction or local veto is applied to this optimistic ceiling.',
        'scope': 'Reference-informed conditional upper bounds, NOT achieved accuracy or proof of learnability. No API calls, new facts, fitting or final-set access.'}
    out.mkdir(parents=True); save_json(out/'protocol.json', protocol)
    d = load(CACHE, CACHE_AUDIT); raw = {r['case']: r for r in read(FROZEN/'replay_inputs_without_references.json')}
    published = read(VERIFIED/'predictions.json'); rows = []
    for record in published:
        case = record['case']; i = d['pos'][case]; reference = record['reference']; base = record['prediction']
        semantic, physical = goal_complete(raw[case])
        prior = {k for k, label in enumerate(('no', 'partial', 'yes')) if d['semantic'][i]['rubric_'+label+'_ready']}
        if not d['valid'][i]:
            prior = set(); semantic = physical = False
        choices = {'existing_warrants': prior,
            'physical_goal_relaxed': prior|({2} if physical else set()),
            'semantic_goal_relaxed': prior|({2} if semantic else set()),
            'combined_with_regular': prior|({2} if semantic else set())|({int(d['regular'][i])} if d['valid'][i] and d['regular'][i] >= 0 else set())}
        row = {'case': case, 'source_group': record['source_group'], 'reference': reference, 'baseline': base,
            'semantic_goal_complete': semantic, 'physical_goal_complete': physical}
        for name, proposals in choices.items():
            row[name+'_proposals'] = sorted(proposals)
            row[name+'_oracle'] = reference if reference in proposals else base
        rows.append(row)
    results = {name: classification_metrics(rows, name+'_oracle') for name in protocol['proposal_sets']}
    baseline = classification_metrics(rows, 'baseline')
    report = {'type': 'reference_informed_proposal_ceiling_not_a_model', 'cases': len(rows), 'baseline': baseline,
        'ceilings': results, 'new_fits': 0, 'new_api_calls': 0, 'serving_changed': False,
        'target_achieved': False, 'warning': protocol['scope']}
    save_json(out/'results.json', report); save_json(out/'diagnostic_rows.json', rows)
    sources = [Path(__file__)]
    for p in sources:
        dest = out/'source_snapshot'/p.relative_to(ROOT); dest.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(p, dest)
    save_json(out/'manifest.json', {'code_sha256': {str(p): file_hash(p) for p in sources}, 'protocol_ref': digest(protocol),
        'parent_predictions_sha256': file_hash(VERIFIED/'predictions.json'), 'cache_audit_manifest_sha256': file_hash(CACHE_AUDIT/'manifest.json')})
    (out/'run.log').write_text('Reference-informed cached-goal proposal ceilings computed. No model or accuracy improvement is claimed.\n')
    (out/'llm-histories.log').write_text('No new API/observer/encoder calls or refitting.\n')
    print({'reference_informed_ceilings_only': {n: (r['correct'], r['balanced_accuracy']) for n, r in results.items()},
           'baseline': (baseline['correct'], baseline['balanced_accuracy']), 'target_achieved': False}, flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--output-dir', type=Path, required=True)
    run(p.parse_args().output_dir.resolve())
