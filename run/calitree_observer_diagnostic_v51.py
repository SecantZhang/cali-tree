"""Prepare a training-only observer-model diagnostic with frozen controllers.

Six previous errors and six controls, two per reference class in each arm.
Change only observer Luna->Sol; keep compiler, Luna interpreter, regular labels,
and source-excluded semantic controllers fixed. No final/reserved-set access.
"""
import argparse
from collections import Counter
from pathlib import Path

import numpy as np
from sklearn.model_selection import StratifiedGroupKFold

from critical.core.decision import bound_evidence_v2 as physical
from critical.core.decision import semantic_interpretation_v5 as meaning
from critical.core.calibration import shared_regions_v27 as shared
from critical.core.calibration.semantic_expert_policy_v49 import export_forest, SemanticExpertPolicy
from critical.core.decision.artifacts import digest, save_json
from run.calitree_accuracy_headroom_v37 import encoded, Probe
from run.calitree_continuous_policy_v43 import examples_and_scores, EXPANSION, RESERVED
from run.calitree_simplified_policy_v44 import feature_columns
from run.calitree_guarded_forward_v32 import SOURCE
from run.calitree_aurora_pilot_v29 import ROOT, read, fingerprint, exact, IDENTITY as LUNA

VERSION = 'frozen-controller-observer-model-diagnostic-v51'
SOL = {'provider': 'openai', 'model': 'gpt-6.1-sol', 'temperature': None, 'reasoning_effort': 'medium'}
MAX_CALLS, MAX_OUTPUT = 24, 12 * (16384 + 8192)


def prepare(out):
    if out.exists():
        raise ValueError('Fresh output directory required')
    local, recent, experts, _ = examples_and_scores(True)
    previous = ROOT / 'logs/exps/261020-expanded-simplified-v44'
    predictions = {r['case']: r for r in read(previous / 'predictions.json') if r['candidate'] == 'dedup_noexpert_sqrt'}
    selected, seen = [], set()
    for label in (0, 1, 2):
        for correct in (False, True):
            eligible = sorted((e for e in recent if e['features'] is not None and e['reference'] == label and
                               (predictions[e['case']]['routed'] == label) == correct), key=lambda e: digest([VERSION, label, correct, e['case']]))
            count = 0
            for e in eligible:
                if e['source_group'] in seen:
                    continue
                selected.append(e)
                seen.add(e['source_group'])
                count += 1
                if count == 2:
                    break
            assert count == 2
    images = {e['case']: e for e in read(SOURCE / 'manifest.json')['cases']}
    images.update({e['case']: e for e in read(ROOT / 'logs/exps/261020-aurora-pilot80-v29-run1/inputs.json')})
    images.update({e['case']: e for e in read(EXPANSION / 'inputs.json')})
    examples = local + recent
    n = len(local)
    names, X, _ = encoded(examples, experts)
    y = np.asarray([e['reference'] for e in examples])
    splitter = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=20261020)
    out.mkdir(parents=True)
    memberships, models = [], {}
    for fold, (tr, te) in enumerate(splitter.split(np.zeros(len(recent)), y[n:], [e['source_group'] for e in recent])):
        train, held = list(range(n)) + [n + int(i) for i in tr], [n + int(i) for i in te]
        columns = feature_columns(names, X, train, 'dedup_noexpert')
        model = Probe('forest', 'sqrt').fit(X[train][:, columns], y[train]).model
        artifact = export_forest(model, [names[i] for i in columns], experts)
        controller = SemanticExpertPolicy(artifact)
        assert all(controller.resolve(e['program'], e['features'], e['regular'])['prediction'] == e['reference'] for e in local)
        for i in held:
            e = examples[i]
            assert controller.resolve(e['program'], e['features'], e['regular'])['prediction'] == predictions[e['case']]['routed']
        save_json(out / f'controllers/fold{fold}.json', artifact)
        models[fold] = artifact['artifact_ref']
        memberships.append({'fold': fold, 'held_sources': sorted({examples[i]['source_group'] for i in held}),
                            'training_sources': sorted({examples[i]['source_group'] for i in train}), 'original_correct': 99})
    inputs, references, hashes = [], {}, {}
    for e in selected:
        p, meta = predictions[e['case']], images[e['case']]
        assert e['source_group'] == meta.get('source_group', meta.get('group'))
        assert e['program']['instruction'] == meta['instruction']
        evidence = meta['evidence']
        image_hashes, pair = physical.image_identity(evidence)
        if 'image_hashes' in meta:
            assert image_hashes == meta['image_hashes']
        hashes.update({evidence[key]: value for key, value in image_hashes.items()})
        inputs.append({'case': e['case'], 'source_group': e['source_group'], 'cohort': e['cohort'], 'evidence': evidence,
                       'program': e['program'], 'pair_ref': pair, 'regular': e['regular'], 'cached_features': e['features'],
                       'baseline_prediction': p['routed'], 'fold': p['fold']})
        references[e['case']] = {'reference': e['reference'], 'baseline_correct': p['routed'] == e['reference']}
    protocol = {'version': VERSION, 'observer_identity': SOL, 'interpreter_identity': LUNA, 'cases': 12,
                'max_requests': MAX_CALLS, 'max_completion_tokens': MAX_OUTPUT, 'observer_output_cap': 16384,
                'interpreter_output_cap': 8192, 'transport_retries': 0, 'compiler_calls': 0, 'regular_calls': 0,
                'selection': 'Training-only, six known controller errors and six controls, two per class/status; 12 distinct sources, fixed hash ranking. Missing-feature cases excluded to isolate semantic grounding.',
                'scope': 'Biased diagnostic sample, not an accuracy/generalization estimate. Frozen historical final set and reserved 80 sources are excluded.',
                'change': 'Only the image observer changes Luna->Sol. Physical prompt/schema, compiled program, Luna interpretation prompt, regular prediction, and held-source controller remain frozen.',
                'failure_policy': 'Retain failed teacher slots without retry; report teacher availability and use cached baseline prediction for the safe-path comparison. All 12 remain in denominator.',
                'fitting': False, 'paid_authorization_required': True, 'new_model_calls': 0,
                'cost': {'expected_usd_range': [.4, 1.0], 'full_output_allowance_usd': 12 * 16384 * 10 / 1e6 + 12 * 8192 * .5 / 1e6,
                         'input_charges_additional': True, 'sol_input_per_million': 2., 'sol_output_per_million': 10.,
                         'luna_input_per_million': .1, 'luna_output_per_million': .5,
                         'pricing_sources': ['https://developers.openai.com/api/docs/models/gpt-6.1-sol', 'https://developers.openai.com/api/docs/models/gpt-6-luna']}}
    save_json(out / 'protocol.json', protocol)
    save_json(out / 'inputs_without_labels.json', inputs)
    save_json(out / 'references_training_only.json', references)
    save_json(out / 'folds.json', memberships)
    code = [Path(__file__).resolve(), ROOT / 'critical/core/decision/bound_evidence_v2.py', ROOT / 'critical/core/decision/bound_evidence.py',
            ROOT / 'critical/core/decision/semantic_interpretation_v5.py', ROOT / 'critical/core/decision/calls.py',
            ROOT / 'critical/lm_engine/provider_api.py', ROOT / 'critical/lm_engine/openai_compat.py',
            ROOT / 'critical/core/calibration/semantic_expert_policy_v49.py', physical.TEMPLATES / 'observe.txt']
    save_json(out / 'manifest.json', {'protocol_ref': digest(protocol), 'inputs_ref': digest(inputs), 'reference_ref': digest(references),
              'image_hashes': hashes, 'code_hashes': {str(p): fingerprint(p) for p in code},
              'controller_refs': models, 'source_prediction_sha256': fingerprint(previous / 'predictions.json'),
              'reserved_inputs_sha256': fingerprint(RESERVED / 'inputs_without_labels.json')})
    (out / 'run.log').write_text('Prepared training-only observer diagnostic; no paid calls authorized. Frozen controllers reproduce all 276 source-held baseline predictions and retain original 99 in each fold.\n')
    (out / 'llm-histories.log').write_text('Zero model calls.\n')
    print({'cases': 12, 'requests_cap': MAX_CALLS, 'completion_cap': MAX_OUTPUT, 'expected_usd': [.4, 1.0],
           'full_output_allowance_usd': protocol['cost']['full_output_allowance_usd']}, flush=True)


def verify(out):
    m, p = read(out / 'manifest.json'), read(out / 'protocol.json')
    entries, refs = read(out / 'inputs_without_labels.json'), read(out / 'references_training_only.json')
    assert digest(p) == m['protocol_ref'] and digest(entries) == m['inputs_ref'] and digest(refs) == m['reference_ref']
    for file, expected in {**m['code_hashes'], **m['image_hashes']}.items():
        assert fingerprint(file) == expected, file
    assert fingerprint(RESERVED / 'inputs_without_labels.json') == m['reserved_inputs_sha256']
    assert len(entries) == len({e['source_group'] for e in entries}) == 12
    assert Counter((r['reference'], r['baseline_correct']) for r in refs.values()) == {(label, truth): 2 for label in (0, 1, 2) for truth in (False, True)}
    reserved = {e['source_group'] for e in read(RESERVED / 'inputs_without_labels.json')}
    folds = {f['fold']: f for f in read(out / 'folds.json')}
    for e in entries:
        assert not {'reference', 'human_score', 'baseline_correct'} & set(e)
        assert e['source_group'] not in reserved | set(folds[e['fold']]['training_sources'])
        assert e['source_group'] in folds[e['fold']]['held_sources']
        a = read(out / f"controllers/fold{e['fold']}.json")
        assert a['artifact_ref'] == m['controller_refs'][str(e['fold'])]
        controller = SemanticExpertPolicy(a)
        assert controller.resolve(e['program'], e['cached_features'], e['regular'])['prediction'] == e['baseline_prediction']
        physical.validate_program(e['program'])
        assert physical.image_identity(e['evidence'])[1] == e['pair_ref']
    return p


def collect(out, live=False):
    if not live or not (out / 'authorization.json').exists():
        raise ValueError('Separate explicit paid authorization and --live required')
    p = verify(out)
    from critical import config
    from critical.core.decision.calls import DurableCalls, ProviderStopped, BudgetExhausted
    from critical.lm_engine import load_creds, get_engine, require_live
    from critical.logging.llm_history import LLMHistoryWriter
    require_live(True)
    config.PROJECT_ROOT = Path('/Users/zzhang/Documents/Projects/Adobe/calitree-mlsys')
    config.CREDENTIALS_FILE = config.PROJECT_ROOT / '.env'
    creds = load_creds(provider='openai', engine='gpt')
    if creds.endpoints != ['https://api.openai.com/v1']:
        raise ValueError('Official endpoint required')
    history = LLMHistoryWriter(out / 'ledger/llm-histories.log')
    def sol_factory(cap):
        return get_engine('gpt', creds=creds, model=SOL['model'], temperature=None, reasoning_effort='medium',
                          max_tokens=cap, timeout=180, max_http_attempts=1, history=history)
    def luna_factory(cap):
        return get_engine('gpt', creds=creds, model=LUNA['model'], temperature=0, max_tokens=cap, timeout=180,
                          max_http_attempts=1, history=history)
    calls = DurableCalls(out / 'ledger', sol_factory, identity=SOL, max_calls=MAX_CALLS, max_completion_tokens=MAX_OUTPUT,
                         scope_limits={'search': 2, 'final': 0}, routes={'interpretation': {'identity': LUNA, 'engine_factory': luna_factory}})
    for e in read(out / 'inputs_without_labels.json'):
        path = out / 'cases' / (e['case'] + '.json')
        if path.exists():
            continue
        result = {'observation': None, 'interpretation': None, 'features': None, 'error': None}
        try:
            observation = physical.BoundVisualObserver(calls).observe(e['program'], e['evidence'], case_id=e['case'], max_tokens=16384)
            result['observation'] = observation
            payload = meaning.make_input(e['program'], observation['observation'], e['pair_ref'])
            value, ref = calls.call('instruction_relative_interpretation', payload, meaning.schema(payload), template=meaning.PROMPT,
                                    slot='once', max_tokens=8192, case_id=e['case'], route='interpretation')
            meaning.validate(payload, value)
            result.update(interpretation=value, interpretation_execution_ref=ref,
                          features=shared.evidence.project(e['program'], observation['observation'], e['pair_ref'], value))
        except (ProviderStopped, BudgetExhausted):
            raise
        except (ValueError, RuntimeError, KeyError, TypeError) as exc:
            result['error'] = type(exc).__name__
        exact(path, result)
        print({'case': e['case'], 'teacher_error': result['error']}, flush=True)
    report(out)


def report(out):
    verify(out)
    refs = read(out / 'references_training_only.json')
    rows = []
    for e in read(out / 'inputs_without_labels.json'):
        value = read(out / 'cases' / (e['case'] + '.json'))
        controller = SemanticExpertPolicy(read(out / f"controllers/fold{e['fold']}.json"))
        available = value['features'] is not None
        teacher = controller.resolve(e['program'], value['features'], e['regular'])['prediction'] if available else -1
        rows.append({'case': e['case'], 'reference': refs[e['case']]['reference'], 'baseline': e['baseline_prediction'],
                     'teacher': teacher, 'teacher_available': available,
                     'safe_path': teacher if available else e['baseline_prediction']})
    exact(out / 'results.json', {'cases': 12, 'correct': {arm: sum(r[arm] == r['reference'] for r in rows) for arm in ('baseline', 'teacher', 'safe_path')},
          'teacher_failures': sum(not r['teacher_available'] for r in rows), 'rows': rows,
          'scope': 'Selected training-only diagnostic; no fitting, serving changes or generalization accuracy claim.'})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    for name in ('prepare', 'verify', 'live', 'report'):
        mode.add_argument('--' + name, action='store_true')
    args = parser.parse_args()
    out = args.output_dir.resolve()
    if args.prepare:
        prepare(out)
    elif args.verify:
        print(verify(out))
    elif args.live:
        collect(out, True)
    else:
        report(out)
