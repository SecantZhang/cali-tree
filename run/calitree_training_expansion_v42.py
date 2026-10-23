"""Prepare/collect 160 additional training outputs, excluding reserved sources.

Frozen compiler-v3/observer-v2/interpreter-v5 and regular Luna judge. Up to 32
compiler repairs are budgeted; failed provider slots are never retried. Human
labels are joined only after label-blind extraction. No validation-set scoring.
"""
import argparse
from collections import Counter
from pathlib import Path

from critical.core.decision.artifacts import digest, save_json
from critical.core.decision.compiler import media_inputs
from critical.core.optimization.prompt.calitree.evidence_covered_judge import BoundEvidencePipeline
from critical.core.optimization.prompt.calitree import task_coverage as task
from critical.core.calibration import shared_regions_v27 as shared
from critical.database.dl_aurora.loader import AURORA_TASKS, AURORA_MODELS
from run.calitree_aurora_pilot_v29 import ROOT, IDENTITY, read, fingerprint, exact, recent_exclusions
from run.calitree_m0 import pixel_hash
from run.collect_calitree_aurora_pilot_v29r1 import validate_regular

VERSION = 'source-disjoint-training-expansion-v42'
SOURCE_ROOT = Path('/Users/zzhang/Documents/Projects/Adobe/calitree-mlsys')
CATALOG = ROOT / 'logs/exps/261020-aurora-pilot80-v29/exposure/original/exposure_ledger.json'
RESERVED = ROOT / 'logs/exps/261020-validation-reservation-v39'
MAX_CALLS = 32 * 2 + 160 * 3
MAX_OUTPUT = 32 * 2 * 8192 + 160 * (16384 + 8192 + 2048)


def prepare(out):
    if out.exists():
        raise ValueError('Fresh output directory required')
    reserved = read(RESERVED / 'inputs_without_labels.json')
    excluded, provenance = recent_exclusions(SOURCE_ROOT)
    excluded |= {e['source_group'] for e in read(ROOT / 'logs/exps/261020-aurora-pilot80-v29-run1/inputs.json')}
    excluded |= {e['source_group'] for e in reserved}
    catalog = read(CATALOG)['tasks']
    sources, seen = [], set(excluded)
    for category in AURORA_TASKS:
        eligible = sorted((t for t in catalog if t['task'] == category and t['source_group'] not in seen),
                          key=lambda t: digest([VERSION, t['task_uid']]))
        count = 0
        for t in eligible:
            if t['source_group'] in seen or {e['editor'] for e in t['outputs']} != set(AURORA_MODELS):
                continue
            sources.append(t)
            seen.add(t['source_group'])
            count += 1
            if count == 4:
                break
        if count != 4:
            raise ValueError('Insufficient unreserved sources for ' + category)
    entries, refs, images = [], {}, {}
    for i, t in enumerate(sources, 1):
        source = SOURCE_ROOT / 'data/aurora/bench' / t['source_path']
        assert pixel_hash(source) == t['source_group'] and fingerprint(source) == t['source_sha256']
        for j, editor in enumerate(AURORA_MODELS, 1):
            o = next(o for o in t['outputs'] if o['editor'] == editor)
            edited = SOURCE_ROOT / 'data/aurora/bench' / o['edited_path']
            assert fingerprint(edited) == o['edited_sha256']
            case = f'T{i:02}M{j}'
            entries.append({'case': case, 'source_group': t['source_group'], 'instruction': o['instruction'],
                            'task': t['task'], 'editor': editor,
                            'evidence': {'source_image': str(source), 'edited_image': str(edited)}})
            refs[case] = task.LABELS.index(o['reference'])
            images[str(source)] = t['source_sha256']
            images[str(edited)] = o['edited_sha256']
    assert len(entries) == 160 and len({e['source_group'] for e in entries}) == 32
    assert not {e['source_group'] for e in entries} & {e['source_group'] for e in reserved}
    out.mkdir(parents=True)
    protocol = {'version': VERSION, 'identity': IDENTITY, 'cases': 160, 'sources': 32,
                'per_category_sources': 4, 'per_category_outputs': 20, 'max_requests': MAX_CALLS,
                'max_completion_tokens': MAX_OUTPUT, 'transport_retries': 0,
                'compiler_repairs_included': 32, 'per_case_normal_calls': 3,
                'scope': 'Training expansion only. Reserved 80 validation sources and all earlier recent exclusions are excluded.',
                'cost': {'expected_usd_range': [.27, .60], 'completion_cap_usd': MAX_OUTPUT * .50 / 1e6,
                         'input_charges_additional': True, 'basis': 'Twice the completed 80-output Luna pilot usage; no cache discounts.',
                         'pricing_source': 'https://developers.openai.com/api/docs/models/gpt-6-luna'},
                'older_exposure': True, 'paid_authorization_required': True, 'new_model_calls': 0}
    save_json(out / 'protocol.json', protocol)
    save_json(out / 'inputs.json', entries)
    save_json(out / 'references.json', refs)
    save_json(out / 'manifest.json', {'protocol_ref': digest(protocol), 'input_ref': digest(entries), 'reference_ref': digest(refs),
              'image_hashes': images, 'code_hashes': {str(Path(__file__).resolve()): fingerprint(__file__)},
              'reserved_input_sha256': fingerprint(RESERVED / 'inputs_without_labels.json'),
              'catalog_sha256': fingerprint(CATALOG), 'recent_exclusion_provenance': provenance})
    save_json(out / 'class_counts_training_only.json', dict(Counter(refs.values())))
    (out / 'run.log').write_text('Training-only expansion prepared; no extraction calls authorized yet. Reserved validation labels not read.\n')
    (out / 'llm-histories.log').write_text('Zero model calls.\n')
    print({'prepared_cases': 160, 'sources': 32, 'max_requests': MAX_CALLS, 'max_completion_tokens': MAX_OUTPUT,
           'expected_cost_usd': [.27, .60], 'completion_cap_usd': MAX_OUTPUT * .50 / 1e6}, flush=True)


def verify(out):
    m, p = read(out / 'manifest.json'), read(out / 'protocol.json')
    entries, refs = read(out / 'inputs.json'), read(out / 'references.json')
    assert digest(p) == m['protocol_ref'] and digest(entries) == m['input_ref'] and digest(refs) == m['reference_ref']
    assert fingerprint(RESERVED / 'inputs_without_labels.json') == m['reserved_input_sha256']
    for file, expected in {**m['image_hashes'], **m['code_hashes']}.items():
        assert fingerprint(file) == expected, file
    assert len(entries) == 160 and len({e['source_group'] for e in entries}) == 32
    reserved = {e['source_group'] for e in read(RESERVED / 'inputs_without_labels.json')}
    assert not reserved & {e['source_group'] for e in entries}
    assert all('reference' not in e and 'human_score' not in e for e in entries)
    assert set(refs) == {e['case'] for e in entries}
    return p


def collect(out, live=False):
    if not live or not (out / 'authorization.json').exists():
        raise ValueError('Separate explicit paid authorization and --live required')
    verify(out)
    preflight = read(out / 'preflight_seal.json')
    for file, expected in preflight['files'].items():
        assert fingerprint(out / file) == expected, file
    for file, expected in preflight['upstream_code_and_prompt_hashes'].items():
        assert fingerprint(file) == expected, file
    from critical import config
    from critical.core.decision.calls import DurableCalls, ProviderStopped, BudgetExhausted
    from critical.lm_engine import load_creds, get_engine, require_live
    from critical.logging.llm_history import LLMHistoryWriter
    require_live(True)
    config.PROJECT_ROOT = SOURCE_ROOT
    config.CREDENTIALS_FILE = SOURCE_ROOT / '.env'
    creds = load_creds(provider='openai', engine='gpt')
    if creds.endpoints != ['https://api.openai.com/v1']:
        raise ValueError('Official endpoint required')
    def factory(cap):
        return get_engine('gpt', creds=creds, model=IDENTITY['model'], temperature=0, max_tokens=cap,
                          timeout=180, max_http_attempts=1, history=LLMHistoryWriter(out / 'ledger/llm-histories.log'))
    calls = DurableCalls(out / 'ledger', factory, identity=IDENTITY, max_calls=MAX_CALLS,
                         max_completion_tokens=MAX_OUTPUT, scope_limits={'search': 3, 'final': 0})
    pipeline = BoundEvidencePipeline(calls)
    entries = read(out / 'inputs.json')
    programs = {}
    for instruction in dict.fromkeys(e['instruction'] for e in entries):
        key = digest(instruction)
        path = out / 'programs' / (key + '.json')
        if path.exists():
            programs[instruction] = read(path)
            continue
        try:
            program = pipeline.compile(instruction, case_id='compile-' + key)
            result = {'program': program, 'error': None}
        except (ProviderStopped, BudgetExhausted):
            raise
        except (ValueError, RuntimeError, KeyError, TypeError) as exc:
            result = {'program': None, 'error': type(exc).__name__}
        exact(path, result)
        programs[instruction] = result
        print({'compiled_instruction': len(programs), 'error': result['error']}, flush=True)
    for e in entries:
        path = out / 'cases' / (e['case'] + '.json')
        if path.exists():
            continue
        program = programs[e['instruction']]['program']
        observation = interpretation = features = pair = None
        extraction_error = programs[e['instruction']]['error']
        if program is not None:
            try:
                observation, interpretation, pair = pipeline.extract(program, e['evidence'], case_id=e['case'])
                features = shared.evidence.project(program, observation, pair, interpretation)
            except (ProviderStopped, BudgetExhausted):
                raise
            except (ValueError, RuntimeError, KeyError, TypeError) as exc:
                extraction_error = type(exc).__name__
        regular = None
        regular_ref = None
        regular_error = None
        try:
            regular, regular_ref = calls.call('flat_judge', {'instruction': e['instruction']}, task.SCHEMA,
                                             template=(task.TEMPLATES / 'regular.txt').read_text(), media=media_inputs(e['evidence']),
                                             case_id=e['case'], slot='once', max_tokens=2048)
            validate_regular(regular)
        except (ProviderStopped, BudgetExhausted):
            raise
        except (ValueError, RuntimeError, KeyError, TypeError) as exc:
            regular = None
            regular_error = type(exc).__name__
        exact(path, {'program': program, 'observation': observation, 'interpretation': interpretation, 'pair_ref': pair,
                     'features': features, 'regular_judgment': regular, 'regular_execution_ref': regular_ref,
                     'extraction_error': extraction_error, 'regular_error': regular_error})
        print({'case': e['case'], 'extraction_error': extraction_error, 'regular_error': regular_error}, flush=True)
    report(out)


def report(out):
    verify(out)
    refs = read(out / 'references.json')
    rows = []
    for e in read(out / 'inputs.json'):
        c = read(out / 'cases' / (e['case'] + '.json'))
        value = c['regular_judgment']
        label = task.LABELS.index(value['label']) if value is not None and value['label'] in task.LABELS else -1
        rows.append({**e, 'reference': refs[e['case']], 'program': c['program'], 'features': c['features'],
                     'regular': label, 'extraction_error': c['extraction_error'], 'regular_error': c['regular_error']})
    exact(out / 'training_data.json', rows)
    result = {'cases': 160, 'sources': 32, 'valid_feature_cases': sum(e['features'] is not None for e in rows),
              'regular_correct': sum(e['reference'] == e['regular'] for e in rows),
              'scope': 'Additional training data only; no generalization accuracy claimed.'}
    exact(out / 'results.json', result)
    print(result, flush=True)


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
