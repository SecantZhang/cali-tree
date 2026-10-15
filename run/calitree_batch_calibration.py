"""Fit on a separate balanced AURORA batch; score twelve cached evidence records."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
import shutil

from critical.core.calibration.evidence_batch import LABELS, VERSION, EvidenceBatchCalibrator, select_and_fit
from critical.core.calibration.registry import CalibrationRegistry
from critical.core.decision.artifacts import digest, save_json
from critical.core.decision.calls import DurableCalls
from critical.core.decision.single_call import SCHEMA, SingleCallEvidenceJudge, apply_label_policy, prompt
from critical.database.dl_aurora.loader import AURORA_MODELS, score_to_label
from run.calitree_single_call import (
    CAP, IDENTITY, ROOT, fingerprint, metrics, paired_comparison, read, verify as verify_evidence,
)


DEFAULT_EVIDENCE = ROOT / 'logs/exps/261013-single-call-evidence-balanced12-v1'
PROTOCOL = 'aurora-batch-evidence-calibration-v1'
SEED = 20261013
PER_CLASS = 12


def assert_disjoint(training, evaluation):
    if (len({r['group'] for r in training}) != len(training)
            or {r['group'] for r in training} & {r['group'] for r in evaluation}
            or {r['id'] for r in training} & {r['id'] for r in evaluation}):
        raise ValueError('Calibration and evaluation must have distinct source groups and IDs')


def select_batch(evidence_manifest):
    from PIL import Image
    from hashlib import sha256

    flat = read(Path(evidence_manifest['baseline_directory']) / 'manifest.json')
    excluded = set(flat['excluded_groups']) | {r['group'] for r in evidence_manifest['cases']}
    train = set(read(ROOT / 'data/aurora/bench/splits/seed_42.json')['train'])
    candidates, groups = [], {}
    for row in map(json.loads, (ROOT / 'data/aurora/bench/metadata.jsonl').read_text().splitlines()):
        if row['model'] != AURORA_MODELS[0] or row['task_uid'] not in train: continue
        source = ROOT / 'data/aurora/bench' / row['source_path']
        if str(source) not in groups:
            with Image.open(source) as image:
                rgb = image.convert('RGB')
                groups[str(source)] = sha256(str(rgb.size).encode() + rgb.tobytes()).hexdigest()
        group = groups[str(source)]
        if group in excluded: continue
        images = {'source_image': str(source),
                  'edited_image': str(ROOT / 'data/aurora/bench' / row['edited_path'])}
        candidates.append({'id': row['item_id'], 'task_uid': row['task_uid'], 'task': row['task'],
                           'instruction': row['instruction'], 'editing_model': row['model'],
                           'group': group, 'reference': score_to_label(row['human_score'])[1],
                           'human_score': row['human_score'], 'evidence': images,
                           'image_hashes': {k: fingerprint(p) for k, p in images.items()}})
    chosen, used, categories = [], set(), Counter()
    for _ in range(PER_CLASS):
        for label in LABELS:
            eligible = [r for r in candidates if r['reference'] == label and r['group'] not in used]
            if not eligible: raise ValueError('Insufficient source-independent official training cases for ' + label)
            row = min(eligible, key=lambda r: (categories[r['task']], digest([PROTOCOL, SEED, r['id']])))
            chosen.append({**row, 'case': f'C{len(chosen)+1:02d}'})
            used.add(row['group']); categories[row['task']] += 1
    assert_disjoint(chosen, evidence_manifest['cases'])
    return chosen, sorted(excluded)


def prepare(output, evidence_dir):
    output.mkdir(parents=True, exist_ok=True)
    if (output / 'manifest.json').exists():
        manifest = read(output / 'manifest.json')
        if manifest['evidence_directory'] != str(evidence_dir): raise ValueError('Changed cached evaluation run')
        verify(output, manifest); return manifest
    previous = read(evidence_dir / 'manifest.json')
    verify_evidence(evidence_dir, previous)
    if previous['judge_identity'] != IDENTITY: raise ValueError('Evidence observer identity mismatch')
    selected, excluded = select_batch(previous)
    files = [p for p in (ROOT / 'critical').rglob('*') if p.is_file() and p.suffix in ('.py', '.txt', '.json')]
    files += [Path(__file__).resolve(), ROOT / 'run/calitree_single_call.py']
    code = {}
    for path in files:
        rel = str(path.relative_to(ROOT)); target = output / 'source_snapshot' / rel
        target.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(path, target)
        code[rel] = fingerprint(path)
    (output / 'observer_prompt.txt').write_text(prompt())
    paths = [evidence_dir / name for name in ('manifest.json', 'seal.json', 'results.json', 'prompt.txt')]
    paths += list((evidence_dir / 'ledgers').glob('*/jobs/*.json'))
    flat_dir = Path(previous['baseline_directory'])
    paths += [flat_dir / name for name in ('manifest.json', 'seal.json', 'results.json')]
    manifest = {
        'version': PROTOCOL, 'calibrator_version': VERSION, 'seed': SEED,
        'judge_identity': IDENTITY, 'calibration_cases': selected,
        'evaluation_cases': previous['cases'], 'evidence_directory': str(evidence_dir),
        'baseline_directory': str(flat_dir), 'cached_files': {str(p): fingerprint(p) for p in paths},
        'excluded_groups': excluded, 'workers': 4, 'max_new_calls': 36,
        'max_completion_tokens_per_case': CAP, 'draws_per_case': 1, 'presentation': 'source_first',
        'http_attempts_per_slot': 1, 'observer_prompt_ref': digest(prompt()), 'observer_schema_ref': digest(SCHEMA),
        'code_hashes': code,
        'metadata_sha256': fingerprint(ROOT / 'data/aurora/bench/metadata.jsonl'),
        'split_sha256': fingerprint(ROOT / 'data/aurora/bench/splits/seed_42.json'),
        'selection': 'Official seed-42 train tasks, AURORA editor only, twelve per reference class; source-pixel unique, category spreading with deterministic hash ties. Exclude twelve evaluation sources, earlier twelve fit sources and reserved fifty holdout.',
        'training': 'Three-fold stratified calibration-only selection of C in [0.1,1,10], tie toward smaller C. Fold-local TF-IDF/scaling; final fit on usable calibration records only. Keep fixed-policy No and unresolved guards.',
        'evaluation': 'Freeze registry artifact before applying to twelve cached records; no evaluation image/model calls and no evaluation labels in fitting.',
        'scope': 'Source-disjoint batch calibration; evaluation cases already inspected historically. Single draws do not measure repeat robustness.',
        'authorization': 'Implement the batch calibration layer using a separate class-balanced AURORA batch, then benchmark it on the same 12 cached evidence records and compare with the flat and uncalibrated judges.',
    }
    save_json(output / 'manifest.json', manifest)
    save_json(output / 'seal.json', {'manifest_ref': digest(manifest)})
    save_json(output / 'estimate.json', {'new_image_judgments_max': 36, 'evaluation_model_calls': 0,
              'calibration_model_calls': 0, 'offline_calibrator_fitting': True,
              'max_completion_tokens': 36*CAP, 'output_token_cost_ceiling_usd': 36*CAP*10/1_000_000,
              'input_cost': 'Additional; actual text/image usage reported after execution.',
              'pricing_source': 'https://developers.openai.com/api/docs/models/gpt-6.1-sol'})
    verify(output, manifest); return manifest


def verify(output, manifest):
    if digest(manifest) != read(output / 'seal.json')['manifest_ref']: raise ValueError('Changed manifest seal')
    if (manifest['version'] != PROTOCOL or manifest['judge_identity'] != IDENTITY
            or manifest['observer_prompt_ref'] != digest(prompt())
            or (output / 'observer_prompt.txt').read_text() != prompt()
            or manifest['observer_schema_ref'] != digest(SCHEMA)):
        raise ValueError('Changed calibration protocol')
    training, evaluation = manifest['calibration_cases'], manifest['evaluation_cases']
    assert_disjoint(training, evaluation)
    if len(training) != 36 or Counter(r['reference'] for r in training) != dict.fromkeys(LABELS, PER_CLASS):
        raise ValueError('Expected balanced thirty-six-case calibration batch')
    train = set(read(ROOT / 'data/aurora/bench/splits/seed_42.json')['train'])
    if any(r['task_uid'] not in train or r['editing_model'] != AURORA_MODELS[0]
           or r['group'] in manifest['excluded_groups'] for r in training):
        raise ValueError('Calibration source split, model, or exclusion violation')
    for r in training + evaluation:
        if score_to_label(r['human_score'])[1] != r['reference']: raise ValueError('Changed reference mapping')
        for k, path in r['evidence'].items():
            if fingerprint(path) != r['image_hashes'][k]: raise ValueError('Changed source/edited image')
    for name, expected in manifest['cached_files'].items():
        if fingerprint(name) != expected: raise ValueError('Changed cached baseline artifact')
    for rel, expected in manifest['code_hashes'].items():
        if fingerprint(ROOT / rel) != expected or fingerprint(output / 'source_snapshot' / rel) != expected:
            raise ValueError('Changed frozen source: ' + rel)
    if (fingerprint(ROOT / 'data/aurora/bench/metadata.jsonl') != manifest['metadata_sha256']
            or fingerprint(ROOT / 'data/aurora/bench/splits/seed_42.json') != manifest['split_sha256']):
        raise ValueError('Changed dataset metadata or split')


def observe_batch(output, manifest, live):
    from critical import config
    from critical.lm_engine import get_engine, load_creds, require_live
    from critical.logging.llm_history import LLMHistoryWriter
    config.PROJECT_ROOT = ROOT; config.CREDENTIALS_FILE = ROOT / '.env'
    creds = None
    if live:
        require_live(True); creds = load_creds(provider='openai', engine='gpt')
        if creds.provider != 'openai' or creds.endpoints != ['https://api.openai.com/v1']:
            raise ValueError('Official OpenAI only')

    def work(case):
        directory = output / 'ledgers' / case['case']
        if not live and not list((directory / 'jobs').glob('*.json')):
            raise ValueError('Replay requires an existing observation slot')
        def factory(cap):
            if not live: raise AssertionError('Replay attempted a provider call')
            return get_engine('gpt', creds=creds, model=IDENTITY['model'], reasoning_effort='high',
                              temperature=None, max_tokens=cap, timeout=180, max_http_attempts=1,
                              history=LLMHistoryWriter(directory / 'llm-histories.log'))
        calls = DurableCalls(directory, factory, identity=IDENTITY, max_calls=1,
                             max_completion_tokens=CAP, scope_limits={'search': 1, 'final': 1})
        row = {k: case[k] for k in ('case', 'id', 'group', 'instruction', 'reference')}
        row.update(prediction=None, decision=None, error=None)
        try:
            decision = SingleCallEvidenceJudge(calls).judge(case['instruction'], case['evidence'],
                                                           case_id=case['id'], max_tokens=CAP)
            row.update(prediction=decision['label'], decision=decision)
        except (RuntimeError, ValueError, TypeError, KeyError) as exc:
            row['error'] = type(exc).__name__ + ': ' + str(exc)
            jobs = list((directory / 'jobs').glob('*.json'))
            if jobs and (job := read(jobs[0]))['outcome'] != 'completed':
                row['error'] = job.get('error') or job['outcome']
        print(json.dumps({k: row[k] for k in ('case', 'reference', 'prediction', 'error')}), flush=True)
        return row
    with ThreadPoolExecutor(max_workers=manifest['workers']) as pool:
        return list(pool.map(work, manifest['calibration_cases']))


def input_record(row):
    return {'instruction': row['instruction'], 'observations': row['decision']['observations']}


def fit_or_load(output, rows, live):
    """This function has no evaluation-data or evaluation-label argument."""
    usable = [r for r in rows if r['decision'] is not None]
    X = [input_record(r) for r in usable]
    y = [LABELS.index(r['reference']) for r in usable]
    training_ref = digest({'X': X, 'y': y})
    seal_path = output / 'calibration_seal.json'
    if seal_path.exists():
        seal = read(seal_path); artifact = read(output / seal['path'])
        if (digest(artifact) != seal['artifact_ref'] or artifact['calibrator']['training_ref'] != training_ref
                or artifact['training_ids'] != [r['id'] for r in usable]):
            raise ValueError('Changed frozen calibration artifact or training inputs')
        return EvidenceBatchCalibrator.restore(artifact['calibrator']), artifact, seal
    if not live: raise ValueError('Replay requires frozen calibration artifact')
    model, cv = select_and_fit(X, y)
    artifact = {'calibrator': model.metadata(), 'training_ids': [r['id'] for r in usable],
                'training_groups': [r['group'] for r in usable], 'training_observations_ref': digest(rows),
                'cross_validation': cv, 'usable_counts': dict(Counter(r['reference'] for r in usable))}
    version, path = CalibrationRegistry(output / 'registry').publish(artifact)
    seal = {'version': version, 'path': str(path.relative_to(output)), 'artifact_ref': digest(artifact)}
    save_json(seal_path, seal)
    print(json.dumps({'phase': 'calibrator_frozen', 'registry_version': version,
                      'training_rows': len(usable), 'selected_C': cv['selected_regularization']}), flush=True)
    return model, artifact, seal


def evaluate_cached(model, cached):
    """No model/image calls; reference labels are copied only for metric scoring."""
    rows = []
    for old in cached['cases']:
        value = model.predict_records([input_record(old)])[0] if old['decision'] is not None else None
        rows.append({k: old[k] for k in ('case', 'id', 'instruction', 'reference')})
        rows[-1].update(prediction=value['label'] if value else None, calibration=value,
                        original_prediction=old['prediction'], cached_execution_ref=(old['decision'] or {}).get('execution_ref'))
    return rows


def execute(output, manifest, live):
    rows = observe_batch(output, manifest, live)
    saved = output / 'calibration_observations.json'
    if saved.exists() and read(saved) != rows: raise ValueError('Changed saved calibration observations')
    if not saved.exists():
        if not live: raise ValueError('Replay requires saved training observations')
        save_json(saved, rows)
    model, artifact, seal = fit_or_load(output, rows, live)
    # Freeze is durable before the evaluation records are passed to the calibrator.
    cached = read(Path(manifest['evidence_directory']) / 'results.json')
    calibrated = evaluate_cached(model, cached)
    flat = read(Path(manifest['baseline_directory']) / 'results.json')
    training_predictions = []
    for row in rows:
        value = model.predict_records([input_record(row)])[0] if row['decision'] is not None else None
        training_predictions.append({**row, 'prediction': value['label'] if value else None})
    jobs = [read(p) for p in sorted((output / 'ledgers').glob('*/jobs/*.json'))]
    responses = [j['response'] for j in jobs if j.get('response')]
    return {'version': PROTOCOL, 'model': IDENTITY, 'registry': seal,
            'calibrated_metrics': metrics(calibrated), 'uncalibrated_metrics': metrics(cached['cases']),
            'flat_metrics': metrics(flat['cases']), 'vs_uncalibrated': paired_comparison(cached, calibrated),
            'vs_flat': paired_comparison(flat, calibrated), 'cases': calibrated,
            'calibration_batch_uncalibrated': metrics(rows),
            'calibration_batch_fitted': metrics(training_predictions),
            'calibration_cross_validation': artifact['cross_validation'], 'usable_counts': artifact['usable_counts'],
            'new_api_attempts': len(jobs), 'call_outcomes': dict(Counter(j['outcome'] for j in jobs)),
            'evaluation_api_calls': 0, 'input_tokens': sum(r.get('promptTokens', 0) for r in responses),
            'completion_tokens': sum(r.get('completionTokens', 0) for r in responses),
            'returned_models': sorted({r.get('model', 'unknown') for r in responses}), 'scope': manifest['scope']}


def report(output, result, manifest):
    lines = ['# Batch-calibrated evidence judge: cached twelve-case comparison', '',
             'Calibration: 36 source-distinct official AURORA training cases, 12 per class, AURORA editor only.',
             'Observer: unchanged single-call evidence prompt, GPT-6.1 Sol high, SOURCE-first, one attempt per case.',
             'Evaluation: the original twelve evidence records and flat responses; zero new evaluation calls.', '',
             '| Method | Correct | No recall | Partial recall | Yes recall | Resolved |',
             '|---|---:|---:|---:|---:|---:|']
    for name, key in [('Flat', 'flat_metrics'), ('Evidence + fixed policy', 'uncalibrated_metrics'),
                      ('Evidence + batch calibration', 'calibrated_metrics')]:
        m = result[key]; rates = ' | '.join(f"{m['per_class_recall'][v]:.0%}" for v in LABELS)
        lines.append(f"| {name} | {m['correct']}/12 ({m['accuracy']:.1%}) | {rates} | {m['resolved']}/12 |")
    for name, key in [('uncalibrated', 'vs_uncalibrated'), ('flat', 'vs_flat')]:
        p = result[key]
        lines += ['', f"Versus {name}: improvements {p['wins']}; regressions {p['losses']}; accuracy change {p['accuracy_difference']:+.1%}; exact paired McNemar p={p['mcnemar_exact_two_sided_p']:.3f}."]
    lines += ['', '| Case | Instruction | Reference | Flat | Uncalibrated | Calibrated | Guard |',
              '|---|---|---|---|---|---|---|']
    flat = read(Path(manifest['baseline_directory']) / 'results.json')
    for old, r in zip(flat['cases'], result['cases']):
        lines.append(f"| {r['case']} | {r['instruction'].replace('|','/')} | {r['reference']} | {old['prediction']} | {r['original_prediction']} | {r['prediction'] or 'unresolved'} | {(r['calibration'] or {}).get('guard') or ''} |")
    lines += ['', '## Calibration diagnostics', '',
              f"Frozen registry version: `{result['registry']['version']}`.",
              f"Usable training records by class: {result['usable_counts']}.",
              f"Batch uncalibrated accuracy: {result['calibration_batch_uncalibrated']['accuracy']:.1%}; fitted training accuracy: {result['calibration_batch_fitted']['accuracy']:.1%} (resubstitution, not test accuracy).", '',
              '| Regularization C | Calibration-only three-fold macro recall |', '|---:|---:|']
    for c in result['calibration_cross_validation']['candidates']:
        lines.append(f"| {c['regularization']} | {c['macro_recall']:.1%} |")
    lines += ['', f"Selected C: {result['calibration_cross_validation']['selected_regularization']}; ties prefer stronger regularization.",
              'Vocabulary and scaling are fitted within each fold; the final model uses only the calibration batch.',
              'CV was used for selection, so its score is not an independent estimate.', '',
              '## What the layer learns', '',
              'The L2 multinomial classifier combines structured state fractions, target/integrity states and TF-IDF words/bigrams from evidence descriptions and scope. It receives no IDs, task labels, editor identity, human means or evaluation references.',
              'Fixed-policy No and unresolved states remain protected. Other resolved records may be relabeled. This is statistical text calibration, not a discovered or human-verified semantic rule tree.', '',
              '## Limits and usage', '',
              'The 12 evaluation sources are disjoint from all calibration sources, but have already been inspected in earlier work. They are a small diagnostic, not an untouched population test.',
              'A 36-record fit can learn lexical or task correlations instead of correct semantic tolerance. Dataset labels remain discretized aggregate means, not per-check human annotations.',
              'Calibration cannot repair missing/misread visual evidence; protected No decisions cannot be corrected by this layer.',
              'One observation per image pair does not establish repeat robustness. No prompt or hyperparameter changes were made using the evaluation results.',
              f"New API attempts: {result['new_api_attempts']}; outcomes {result['call_outcomes']}; input/completion tokens {result['input_tokens']}/{result['completion_tokens']}.",
              'Calibration fitting and all twelve evaluation predictions use no additional model calls.', '']
    (output / 'report.md').write_text('\n'.join(lines))
    (output / 'llm-histories.log').write_text(''.join(p.read_text() for p in sorted((output / 'ledgers').glob('*/llm-histories.log'))))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--evidence-dir', type=Path, default=DEFAULT_EVIDENCE)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--preflight', action='store_true'); modes.add_argument('--live', action='store_true')
    modes.add_argument('--replay', action='store_true')
    args = parser.parse_args(); output, evidence = args.output_dir.resolve(), args.evidence_dir.resolve()
    if output == evidence: raise ValueError('Use a new output directory')
    if args.replay and not (output / 'results.json').exists(): raise ValueError('Replay needs completed results')
    manifest = prepare(output, evidence)
    if args.preflight:
        print(json.dumps({'ready': True, 'calibration_classes': dict(Counter(r['reference'] for r in manifest['calibration_cases'])),
                          'task_counts': dict(Counter(r['task'] for r in manifest['calibration_cases'])),
                          'new_calls_max': 36, 'evaluation_calls': 0})); return
    result = execute(output, manifest, args.live); verify(output, manifest)
    if args.replay:
        if read(output / 'results.json') != result: raise ValueError('Replay result changed')
        save_json(output / 'verification.json', {'exact_replay': True, 'new_api_calls': 0,
                  'source_disjoint': True, 'cached_baselines_unchanged': True,
                  'calibration_ref': result['registry']['artifact_ref'], 'results_sha256': fingerprint(output / 'results.json')})
        print(json.dumps({'exact_replay': True, 'new_api_calls': 0}))
    else:
        if (output / 'results.json').exists() and read(output / 'results.json') != result:
            raise ValueError('Refusing to replace different results')
        save_json(output / 'results.json', result); report(output, result, manifest)
        print(json.dumps({k: result[k] for k in ('flat_metrics', 'uncalibrated_metrics', 'calibrated_metrics', 'vs_uncalibrated', 'vs_flat')}))


if __name__ == '__main__':
    main()
