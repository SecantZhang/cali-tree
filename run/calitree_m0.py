"""M0 data inventory, historical exposure audit, and sealed 50-case reservation.

This module never imports a model client or performs inference. Catalog entries
and dry-run dataset nodes are not model exposure. Ambiguous evaluation-context
references are conservatively ineligible for a globally untouched test set.
"""
import argparse
from collections import Counter, defaultdict
from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import shutil

from critical.core.decision.artifacts import digest, save_json
from critical.database.dl_aurora.loader import AURORA_MODELS, score_to_label
from run.calitree_single_call import ROOT, IDENTITY, read, fingerprint

VERSION = 'semantic-hierarchy-m0-v1'
SEED = 20261014
LABELS = ('no', 'partial', 'yes')
QUOTAS = {'no': 17, 'partial': 17, 'yes': 16}
DATA = ROOT / 'data/aurora/bench'
LOCAL = ROOT / 'logs/exps/261014-instruction-semantic-distillation-v16'
TRAIN = ROOT / 'logs/exps/261013-four-groups-local-v4'
TRANSFER = ROOT / 'logs/exps/261014-frozen-semantic-transfer12-v1'
AUDIT_ROOTS = ('logs/exps', '.cache/calitree-tests', 'docs/experiments', 'tests/unit/calitree/fixtures')
SKIP_DIRS = {'source_snapshot', 'source_snapshots', 'frozen_sources', '__pycache__', '.git', 'node_modules'}
UID_RE = re.compile(r'aurora-task-[0-9a-f]{20}')
SHA_RE = re.compile(r'(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])')
PATH_RE = re.compile(r'human_ratings/[^"\n\r<>]+\.(?:png|jpg|jpeg)')
EXCLUDE_KEYS = {'raw_dataset', 'raw_labels', 'samples', 'labels', 'excluded_sibling_item_ids',
                'remaining_untouched_task_uids', 'remaining_pixel_disjoint_task_uids',
                'unused_task_uids_reusing_seen_pixels', 'candidate_task_uids',
                'pixel_disjoint_candidate_task_uids', 'code_hashes', 'source_hashes',
                'pinned_files', 'prior_sources', 'excluded_source_pixels', 'excluded_groups',
                'excluded_fit_development_groups', 'excluded_source_groups'}
EXEC_NAMES = ('result', 'prediction', 'observation', 'draws', 'calls', 'checkpoint', 'evaluation', 'judgment', 'histories')
ALIASES = ('case', 'case_id', 'cohort_id', 'key', 'name')
IDENTIFIERS = ('id', 'item_id', 'task_uid', 'case_id')


def pixel_hash(path):
    from PIL import Image
    with Image.open(path) as im:
        rgb = im.convert('RGB')
        return sha256(str(rgb.size).encode() + rgb.tobytes()).hexdigest()


def catalog():
    rows = [json.loads(line) for line in (DATA / 'metadata.jsonl').read_text().splitlines()]
    pixels, hashes, sources = {}, {}, defaultdict(set)
    for r in rows:
        for key in ('source_path', 'edited_path'):
            rel = r[key]
            if rel not in hashes:
                hashes[rel] = fingerprint(DATA / rel)
            sources[hashes[rel]].add(r['task_uid'])
        if r['source_path'] not in pixels:
            pixels[r['source_path']] = pixel_hash(DATA / r['source_path'])
    tasks = {}
    for r in rows:
        uid = r['task_uid']; group = pixels[r['source_path']]
        t = tasks.setdefault(uid, {'task_uid': uid, 'source_group': group, 'source_path': r['source_path'],
                                   'source_sha256': hashes[r['source_path']], 'task': r['task'], 'outputs': []})
        assert t['source_group'] == group
        t['outputs'].append({'item_id': r['item_id'], 'editor': r['model'], 'edited_path': r['edited_path'],
                             'edited_sha256': hashes[r['edited_path']], 'instruction': r['instruction'],
                             'human_score': r['human_score'], 'reference': score_to_label(r['human_score'])[1]})
    by_path = defaultdict(set)
    for r in rows:
        for key in ('source_path', 'edited_path'):
            by_path[r[key]].add(r['task_uid'])
    for uid, t in tasks.items():
        sources[t['source_group']].add(uid)
    return tasks, by_path, sources


def scrub(value):
    """Remove catalogs, exclusion lists, and unused-pool metadata before attribution."""
    if isinstance(value, dict):
        return {k: scrub(v) for k, v in value.items()
                if k not in EXCLUDE_KEYS and not k.startswith(('remaining_', 'unused_', 'excluded_', 'prior_'))}
    if isinstance(value, list):
        return [scrub(v) for v in value]
    return value


def refs(value, tasks, by_path, by_hash, *, broad=True):
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    found = set(UID_RE.findall(text)) & set(tasks)
    if broad:
        for h in SHA_RE.findall(text):
            found.update(by_hash.get(h, ()))
        for rel in PATH_RE.findall(text.replace('\\/', '/')):
            found.update(by_path.get(rel, ()))
    return found


def case_refs(row, tasks, by_path, by_hash):
    if not isinstance(row, dict):
        return set()
    selected = {k: v for k, v in row.items()
                if k in IDENTIFIERS or k in ('evidence', 'image_hashes')
                or k.startswith(('source_image', 'edited_image')) or k in ('source_path', 'edited_path')}
    return refs(selected, tasks, by_path, by_hash)


def context_aliases(value, tasks, by_path, by_hash):
    result = defaultdict(set)
    def walk(v, key=None):
        if isinstance(v, dict):
            ids = case_refs(v, tasks, by_path, by_hash)
            if ids:
                for alias in [key, *(v.get(k) for k in ALIASES)]:
                    if isinstance(alias, str) and alias and len(alias) < 120:
                        result[alias].update(ids)
            for k, child in v.items():
                if isinstance(child, (dict, list)):
                    walk(child, k)
        elif isinstance(v, list):
            for child in v:
                walk(child)
    walk(value)
    return result


def execution_artifact(path, value):
    if 'aurora-panel-layout-audit-20260926' in path.parts:
        return False
    if isinstance(value, dict) and ('node_results' in value or ('meta' in value and 'outputs' in value)):
        # Canvas dataset/partition snapshots contain the entire catalog. Model
        # execution ledgers and explicitly selected leaf artifacts are audited
        # separately; an exported catalog is never counted as 400 judgments.
        return False
    return 'jobs' in path.parts or any(word in path.name.lower() for word in EXEC_NAMES)


def execution_value(value):
    """Keep executed canvas outputs without attaching dataset/partition catalogs."""
    if not isinstance(value, dict):
        return value
    catalog_keys = {'raw_dataset', 'raw_labels', 'samples', 'labels', 'partition',
                    'fit_samples', 'validation_samples', 'test_samples', 'test_dataset', 'train_dataset'}
    def node(v):
        if not isinstance(v, dict) or v.get('status') != 'done' or v.get('meta', {}).get('dry_run'):
            return None
        outputs = v.get('outputs', {})
        return {k: item for k, item in outputs.items() if k not in catalog_keys} or None
    if 'node_results' in value:
        return {k: v for k, item in value['node_results'].items() if (v := node(item)) is not None}
    if 'meta' in value and 'outputs' in value:
        return node(value)
    return value


def execution_aliases(value):
    """Find case aliases in actual prediction/draw records, not whole manifests."""
    found = set()
    def walk(v, inherited=None):
        if isinstance(v, dict):
            alias = next((v[k] for k in ALIASES if isinstance(v.get(k), str)), inherited)
            marker = ('prediction' in v or 'predicted_label' in v or 'arms' in v or
                      ('label' in v and any(k in v for k in ('rationale', 'valid', 'confidence'))) or
                      ('outcome' in v and 'payload' in v) or 'completionTokens' in v)
            if marker and alias:
                found.add(alias)
            for k, child in v.items():
                if k not in ('manifest', 'cases', 'config', *EXCLUDE_KEYS):
                    walk(child, k if re.fullmatch(r'[A-Za-z][A-Za-z_-]*\d+', k) else alias)
        elif isinstance(v, list):
            for child in v:
                walk(child, inherited)
    walk(value)
    return found


def files_to_audit(output):
    entries, excluded = [], Counter()
    for rel in AUDIT_ROOTS:
        base = ROOT / rel
        if not base.exists():
            continue
        for directory, dirs, files in os.walk(base):
            dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and (Path(directory) / d).resolve() != output.resolve())
            for name in sorted(files):
                p = Path(directory) / name
                if p.suffix in ('.json', '.jsonl', '.log', '.md', '.csv', '.html'):
                    entries.append(p)
                else:
                    excluded[p.suffix] += 1
    return sorted(entries), dict(excluded)


def audit_exposure(output):
    tasks, by_path, by_hash = catalog()
    files, excluded_types = files_to_audit(output)
    inventory, contexts, references, errors = [], defaultdict(lambda: defaultdict(set)), [], []
    for i, p in enumerate(files):
        raw = p.read_bytes(); rel = str(p.relative_to(ROOT))
        inventory.append({'path': rel, 'sha256': sha256(raw).hexdigest(), 'bytes': len(raw)})
        text = raw.decode('utf-8', errors='replace')
        value = None
        try:
            if p.suffix == '.json':
                value = json.loads(text)
            elif p.suffix == '.jsonl':
                value = [json.loads(line) for line in text.splitlines() if line.strip()]
        except (ValueError, TypeError) as exc:
            errors.append({'path': rel, 'error': str(exc)[:200], 'aurora_references': sorted(refs(text, tasks, by_path, by_hash))})
        if value is not None:
            # Case aliases are resolved against the nearest available directory
            # context, after the complete inventory has been read.
            if ('manifest' in p.name or 'cases' in p.name or 'config' in p.name or
                    p.parent == ROOT / 'tests/unit/calitree/fixtures' or
                    isinstance(value, dict) and 'manifest' in value):
                for alias, ids in context_aliases(value, tasks, by_path, by_hash).items():
                    contexts[str(p.parent)][alias].update(ids)
            candidate_value = execution_value(value)
            if candidate_value and execution_artifact(p, candidate_value):
                clean = scrub(candidate_value)
                ids = refs(clean, tasks, by_path, by_hash)
                aliases = execution_aliases(candidate_value)
                if ids or aliases:
                    references.append({'path': rel, 'kind': 'execution_artifact', 'task_uids': sorted(ids), 'aliases': sorted(aliases)})
            elif p.parent == ROOT / 'tests/unit/calitree/fixtures':
                ids = refs(scrub(value), tasks, by_path, by_hash)
                if ids:
                    references.append({'path': rel, 'kind': 'development_fixture', 'task_uids': sorted(ids), 'aliases': []})
        elif p.suffix in ('.log', '.md', '.csv', '.html'):
            ids = refs(text, tasks, by_path, by_hash, broad=False)
            # A text report or history can establish prior use, but not the
            # number of provider calls. Keep that distinction in the ledger.
            if ids and (execution_artifact(p, None) or p.suffix in ('.md', '.csv', '.html')):
                references.append({'path': rel, 'kind': 'historical_text_reference', 'task_uids': sorted(ids), 'aliases': []})
        if (i + 1) % 5000 == 0:
            print({'audited_files': i + 1, 'total': len(files)}, flush=True)
    by_task = defaultdict(list); unresolved_aliases = []
    for event in references:
        ids = set(event.pop('task_uids')); aliases = event.pop('aliases')
        for alias in aliases:
            direct = set(UID_RE.findall(alias)) & set(tasks)
            if direct:
                ids.update(direct); continue
            resolved = set()
            for parent in (ROOT / event['path']).parents:
                if alias in contexts.get(str(parent), {}):
                    resolved = contexts[str(parent)][alias]; break
                if parent == ROOT:
                    break
            if resolved:
                ids.update(resolved)
            elif not ids:
                unresolved_aliases.append({'path': event['path'], 'alias': alias})
        for uid in sorted(ids):
            by_task[uid].append(event)
    # Shared decoded source pixels propagate exposure across tasks and editors.
    group_tasks = defaultdict(list)
    for uid, t in tasks.items():
        group_tasks[t['source_group']].append(uid)
    ledger = []
    for uid, t in sorted(tasks.items()):
        events = [dict(e, referenced_task_uid=sibling) for sibling in sorted(group_tasks[t['source_group']]) for e in by_task[sibling]]
        unique = {(e['path'], e['kind'], e['referenced_task_uid']): e for e in events}
        ledger.append({**t, 'status': 'historically_referenced' if unique else 'no_exposure_found',
                       'events': list(unique.values()), 'sibling_task_uids': sorted(group_tasks[t['source_group']])})
    result = {'version': VERSION, 'dataset_sha256': fingerprint(DATA / 'metadata.jsonl'),
              'audit_roots': list(AUDIT_ROOTS), 'skipped_directory_names': sorted(SKIP_DIRS),
              'excluded_file_types': excluded_types, 'files': inventory, 'tasks': ledger,
              'parse_errors': errors, 'unresolved_aliases': unresolved_aliases,
              'meaning': 'Historical inference/evaluation artifacts, development fixtures, and case-specific reports conservatively disqualify a source. Catalog-only presence and dry-run dataset nodes do not. Events prove a reference in that context, not a successful model call for every referenced task.',
              'scope': 'Repository records in the listed roots; does not certify absence of exposure outside this checkout.'}
    save_json(output / 'exposure_ledger.json', result)
    return result


def eligible_rows(ledger, excluded, *, allow_historical=False):
    selected = []
    for t in ledger['tasks']:
        if t['source_group'] in excluded or (t['status'] != 'no_exposure_found' and not allow_historical):
            continue
        for o in t['outputs']:
            if o['editor'] == AURORA_MODELS[0]:
                selected.append({'id': o['item_id'], 'task_uid': t['task_uid'], 'group': t['source_group'],
                                 'task': t['task'], 'instruction': o['instruction'], 'editing_model': o['editor'],
                                 'reference': o['reference'], 'human_score': o['human_score'],
                                 'evidence': {'source_image': str(DATA / t['source_path']), 'edited_image': str(DATA / o['edited_path'])},
                                 'image_hashes': {'source_image': t['source_sha256'], 'edited_image': o['edited_sha256']},
                                 'historical_status': t['status'], 'historical_artifact_count': len(t['events'])})
    return selected


def select_test(candidates, quotas=QUOTAS):
    used, chosen, task_counts = set(), [], Counter()
    for _ in range(max(quotas.values())):
        for label in LABELS:
            if sum(c['reference'] == label for c in chosen) >= quotas[label]:
                continue
            eligible = [c for c in candidates if c['reference'] == label and c['group'] not in used]
            if not eligible:
                raise ValueError('Insufficient distinct eligible sources for ' + label)
            c = min(eligible, key=lambda r: (task_counts[r['task']], digest([VERSION, SEED, r['id']])))
            chosen.append({**c, 'case': f'F{len(chosen)+1:02d}'})
            used.add(c['group']); task_counts[c['task']] += 1
    return chosen


def public_input(case):
    return {k: deepcopy(case[k]) for k in ('instruction', 'evidence')}


def protocol(test_scope):
    return {'version': VERSION, 'seed': SEED, 'test_size': 50, 'test_class_quotas': QUOTAS,
            'test_scope': test_scope, 'test_access': 'Reserved; no inference, optimization, or model selection in M0.',
            'editor': AURORA_MODELS[0], 'judge': IDENTITY, 'presentation': 'source_first',
            'attempts_per_stage_per_case': 1, 'label_policy': {'no': 'mean < 0.5', 'partial': '0.5 <= mean < 1.5', 'yes': 'mean >= 1.5'},
            'targets': 'Released mean-derived labels; no recovered annotator votes or majority-vote claim.',
            'arms': ['flat_judge', 'pooled_semantic_policy', 'routed_local_policies', 'merged_recalibrated_hierarchy'],
            'primary_metric': 'macro_f1', 'required_metrics': ['full_denominator_accuracy', 'no_recall', 'partial_recall', 'yes_recall', 'coverage', 'confusion', 'paired_source_differences', 'rule_complexity', 'inference_cost'],
            'merge_gates': {'source_union_complete': True, 'question_binding_valid': True, 'uses_actual_router': True,
                            'macro_f1_min_delta': 0, 'max_additional_errors_total': 1, 'partial_recall_min_delta': 0,
                            'max_additional_errors_other_class_or_scope': 1, 'coverage_min_delta': 0,
                            'min_validation_sources_per_label': 8, 'min_validation_sources_per_scope': 8,
                            'require_gain_or_lossless_complexity_reduction': True},
            'search_budget': {'max_depth': 3, 'active_candidates_per_initial_batch': 2, 'parent_proposals': 24,
                              'tests_per_clause': 3, 'clauses_per_boundary': 3, 'candidate_regions_per_boundary': 2048},
            'calls': {'m0': 0, 'm0_model_calls_forbidden': True,
                      'historical_v16_stages_per_case': 4, 'planned_bound_stages_per_case': 2,
                      'final_semantic_calls_max_if_two_stage_extractor_validated': 100,
                      'final_flat_calls_max': 50, 'final_total_max_if_two_stage_extractor_validated': 150,
                      'max_completion_tokens_per_call': 16384, 'final_completion_token_ceiling': 2457600,
                      'concurrency': 8, 'parent_fit_model_calls': 0,
                      'note': 'Future budget reservation only, not a request to execute final evaluation. New evidence schemas require separately recorded development budgets.'},
            'retention': 'Keep failures and unresolved cases in denominators. No redraw, retry, gate relaxation, or final-test-driven repair.',
            'success': 'Report transfer, compression, inconclusive or negative result; compare actual routing and matched data/capacity; no 100% local accuracy requirement.'}


def prepare(output, *, allow_historical=False, scope_authorization=None):
    if allow_historical and not scope_authorization:
        raise ValueError('Historical exposure requires a recorded explicit scope authorization')
    output.mkdir(parents=True, exist_ok=True)
    if (output / 'seal.json').exists():
        raise ValueError('Already sealed. Verify existing reservation; do not overwrite.')
    ledger = audit_exposure(output)
    train_manifest, transfer = read(TRAIN / 'manifest.json'), read(TRANSFER / 'manifest.json')
    train, validation = train_manifest['cases'], transfer['cases']
    train_groups = {c['group'] for c in train}; validation_groups = {c['group'] for c in validation}
    if len(train_groups) != 48 or len(validation_groups) != 12 or train_groups & validation_groups:
        raise ValueError('Historical development source partitions changed')
    excluded = set(train_manifest['excluded_groups']) | train_groups | validation_groups
    clean = eligible_rows(ledger, excluded)
    historical = eligible_rows(ledger, excluded, allow_historical=True)
    scope = 'study_relative_historical_exposure_disclosed' if allow_historical else 'no_known_historical_exposure'
    plan = protocol(scope)
    if allow_historical:
        plan['scope_authorization'] = scope_authorization
        save_json(output / 'scope_decision.json', {
            'user_choice': scope_authorization,
            'decision': 'Reserve a study-relative fifty-case cohort; disclose historical exposure. Do not run inference.',
            'strict_freshness_claim': False})
    final = None; reason = None
    try:
        final = select_test(historical if allow_historical else clean)
    except ValueError as exc:
        reason = str(exc)
    # Malformed AURORA-bearing records must be reviewed before a strict seal.
    relevant_errors = [e for e in ledger['parse_errors'] if e['aurora_references']]
    if relevant_errors and not allow_historical:
        final = None; reason = 'Unresolved AURORA-bearing parse errors in exposure audit'
    save_json(output / 'study_protocol.json', plan)
    save_json(output / 'splits/train.json', {'role': 'training', 'historically_observed': True, 'cases': train})
    save_json(output / 'splits/validation.json', {'role': 'development_validation', 'historically_observed': True,
              'limitation': 'This cohort already informed representation design; not an untouched generalization estimate.', 'cases': validation})
    preview = None
    try:
        preview = select_test(historical)
        save_json(output / 'historical_test_candidate_preview.json', {'status': 'proposal_only_not_reserved',
                  'requires_explicit_scope_change': not allow_historical,
                  'scope': 'Disjoint from study fitting/development and prior exclusions; historical project exposure remains.', 'cases': preview})
    except ValueError:
        pass
    snapshot = {}
    for g in ('G1', 'G2', 'G3', 'G4'):
        src = LOCAL / 'rules' / g / 'teacher_distilled/policy.json'
        dest = output / 'baseline_snapshot' / g / 'policy.json'; dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest); snapshot[str(src)] = fingerprint(src)
    for name, src in [('local_results.json', LOCAL / 'results.json'), ('transfer_results.json', TRANSFER / 'results.json'),
                      ('transfer_report.md', TRANSFER / 'report.md'), ('transfer_failure_analysis.md', TRANSFER / 'failure_analysis.md')]:
        shutil.copyfile(src, output / 'baseline_snapshot' / name); snapshot[str(src)] = fingerprint(src)
    save_json(output / 'baseline_snapshot/index.json', {'source_hashes': snapshot})
    status = {'version': VERSION, 'ready': final is not None, 'requested_test_size': 50, 'reason': reason,
              'known_development_sources': 60, 'excluded_source_groups': len(excluded),
              'catalog_tasks': len(ledger['tasks']), 'catalog_source_groups': len({t['source_group'] for t in ledger['tasks']}),
              'historically_referenced_tasks': sum(t['status'] != 'no_exposure_found' for t in ledger['tasks']),
              'unexposed_catalog_class_counts': dict(Counter(c['reference'] for c in eligible_rows(ledger, set()))),
              'strict_eligible_class_counts': dict(Counter(c['reference'] for c in clean)),
              'study_relative_eligible_class_counts': dict(Counter(c['reference'] for c in historical)),
              'files_audited': len(ledger['files']), 'parse_errors': len(ledger['parse_errors']),
              'aurora_parse_errors': len(relevant_errors), 'unresolved_alias_records': len(ledger['unresolved_aliases']),
              'historical_preview_size': len(preview or []), 'test_scope': scope, 'model_calls': 0}
    save_json(output / 'status.json', status)
    report(output, status)
    if final is not None:
        save_json(output / 'splits/test.json', {'role': 'reserved_final_test', 'scope': scope, 'cases': final})
        save_json(output / 'test_inputs.json', {'role': 'reserved_unexecuted_inputs',
                  'scope': scope, 'cases': [{'case': c['case'], 'input': public_input(c)} for c in final]})
        save_json(output / 'test_references.json', {'role': 'scoring_only',
                  'cases': [{k: c[k] for k in ('case', 'id', 'reference', 'human_score')} for c in final]})
        (output / 'README.md').write_text(
            '# Reserved M0 fifty-case cohort\n\n'
            'This is a study-relative final test. Historical project exposure is disclosed in '
            '`splits/test.json` and `exposure_ledger.json`; it is not globally untouched.\n\n'
            'Training: 48 cases. Development validation: 12 already-observed cases. '
            'Final reservation: 50 distinct sources, 17 No / 17 Partial / 16 Yes.\n\n'
            'No model calls or final-test predictions were made by M0. '
            '`test_inputs.json` contains only case handles and label-free model inputs. '
            '`test_references.json` is for the future scorer only.\n\n'
            'Verify with `python -m run.calitree_m0 verify --output-dir ' + str(output.relative_to(ROOT)) + '`.\n')
        sealed = [p for p in output.rglob('*') if p.is_file() and p.name != 'seal.json']
        save_json(output / 'seal.json', {'version': VERSION, 'files': {str(p.relative_to(output)): fingerprint(p) for p in sealed},
                  'dataset_sha256': fingerprint(DATA / 'metadata.jsonl'),
                  'runner_sha256': fingerprint(Path(__file__)), 'live_calls': 0})
    return status


def verify(output):
    if not (output / 'seal.json').exists() or not (output / 'splits/test.json').exists():
        raise ValueError('M0 is incomplete: no sealed fifty-case final reservation')
    seal = read(output / 'seal.json')
    for rel, h in seal['files'].items():
        if fingerprint(output / rel) != h:
            raise ValueError('Sealed artifact changed: ' + rel)
    if fingerprint(DATA / 'metadata.jsonl') != seal['dataset_sha256'] or fingerprint(Path(__file__)) != seal['runner_sha256']:
        raise ValueError('Changed dataset or reservation implementation')
    groups = {}; all_cases = []
    for role in ('train', 'validation', 'test'):
        rows = read(output / 'splits' / (role + '.json'))['cases']; all_cases.extend(rows)
        groups[role] = {c['group'] for c in rows}
        if len(rows) != {'train': 48, 'validation': 12, 'test': 50}[role] or len(rows) != len(groups[role]):
            raise ValueError('Repeated source in ' + role)
    if groups['train'] & groups['validation'] or groups['train'] & groups['test'] or groups['validation'] & groups['test']:
        raise ValueError('Source leakage between partitions')
    test = read(output / 'splits/test.json')['cases']
    if len(test) != 50 or Counter(c['reference'] for c in test) != QUOTAS:
        raise ValueError('Changed fifty-case size or near-balanced labels')
    planned = read(output / 'study_protocol.json')
    ledger = read(output / 'exposure_ledger.json')
    if ledger['dataset_sha256'] != seal['dataset_sha256']:
        raise ValueError('Exposure inventory belongs to another dataset')
    tasks = {r['task_uid']: r for r in ledger['tasks']}
    prior_excluded = set(read(TRAIN / 'manifest.json')['excluded_groups'])
    if groups['test'] & prior_excluded:
        raise ValueError('Test overlaps an earlier reserved/excluded source')
    for c in test:
        if c['historical_status'] != tasks[c['task_uid']]['status'] or c['historical_artifact_count'] != len(tasks[c['task_uid']]['events']):
            raise ValueError('Historical exposure disclosure changed')
    if planned['test_scope'] == 'no_known_historical_exposure':
        if any(c['historical_status'] != 'no_exposure_found' for c in test):
            raise ValueError('Historical sources mislabeled as untouched')
    elif planned['test_scope'] == 'study_relative_historical_exposure_disclosed':
        if not planned.get('scope_authorization') or read(output / 'scope_decision.json')['strict_freshness_claim']:
            raise ValueError('Missing historical-test scope authorization')
    else:
        raise ValueError('Unknown final-test scope')
    for p, h in read(output / 'baseline_snapshot/index.json')['source_hashes'].items():
        if fingerprint(p) != h:
            raise ValueError('Original baseline changed')
    actual_rows = {r['item_id']: r for r in map(json.loads, (DATA / 'metadata.jsonl').read_text().splitlines())}
    for c in all_cases:
        original = actual_rows[c['id']]
        if (c['instruction'] != original['instruction'] or c['task_uid'] != original['task_uid']
                or c['human_score'] != original['human_score'] or c['editing_model'] != original['model']):
            raise ValueError('Case metadata differs from original dataset')
        if pixel_hash(c['evidence']['source_image']) != c['group']:
            raise ValueError('Source pixel identity changed')
        if c['editing_model'] != AURORA_MODELS[0] or score_to_label(c['human_score'])[1] != c['reference']:
            raise ValueError('Changed editor or label semantics')
        for k, p in c['evidence'].items():
            if fingerprint(p) != c['image_hashes'][k]:
                raise ValueError('Image changed')
        if set(public_input(c)) != {'instruction', 'evidence'}:
            raise AssertionError('Labels leaked into inference input')
    if read(output / 'test_inputs.json')['cases'] != [{'case': c['case'], 'input': public_input(c)} for c in test]:
        raise ValueError('Reserved model inputs changed')
    if read(output / 'test_references.json')['cases'] != [{k: c[k] for k in ('case', 'id', 'reference', 'human_score')} for c in test]:
        raise ValueError('Scoring references changed')
    if list(output.glob('ledgers/**/jobs/*.json')) or (output / 'predictions.json').exists():
        raise ValueError('M0 reservation was already evaluated')
    result = {'passed': True, 'training_cases': 48, 'validation_cases': 12, 'reserved_test_cases': 50,
              'class_counts': QUOTAS, 'source_overlap': 0, 'verified_images': len(all_cases) * 2,
              'historically_referenced_test_cases': sum(c['historical_status'] != 'no_exposure_found' for c in test),
              'no_prior_reference_found_test_cases': sum(c['historical_status'] == 'no_exposure_found' for c in test),
              'model_calls': 0, 'test_scope': planned['test_scope']}
    save_json(output / 'verification.json', result)
    return result


def report(output, status):
    lines = ['# M0: fifty-case final-test reservation', '',
             'Status: **' + ('RESERVED' if status['ready'] else 'INCOMPLETE — no final reservation sealed') + '**.', '',
             'No model calls are made by M0. The target is exactly 50 source-distinct AURORA-editor cases: 17 No, 17 Partial, 16 Yes. Fifty cannot be split equally into three labels.', '',
             '| Inventory | Count |', '|---|---:|']
    for k in ('catalog_tasks', 'catalog_source_groups', 'historically_referenced_tasks', 'known_development_sources', 'files_audited'):
        lines.append(f'| {k} | {status[k]} |')
    lines += ['', 'Strict eligible labels: `' + json.dumps(status['strict_eligible_class_counts']) + '`.',
              'Study-relative eligible labels: `' + json.dumps(status['study_relative_eligible_class_counts']) + '`.',
              '', 'Audit distinguishes execution-context references and development fixtures from catalog-only presence. Historical references are conservative exclusions; they do not claim that every reference represents a successful API call.',
              'Source exposure propagates across all editors and tasks sharing decoded source pixels. Audit scope is the explicitly listed repository roots, not unseen external records.', '',
              'The existing 48 fitting cases are training material; the last twelve transfer cases are development validation and are already observed. Original policy and result snapshots are preserved.', '',
              'The historical candidate preview is not a final-test reservation. It documents a possible study-relative cohort only; using that scope requires an explicit decision when strict freshness is infeasible.']
    if status['reason']:
        lines += ['', 'Blocking condition: **' + status['reason'] + '**.']
    (output / 'report.md').write_text('\n'.join(lines) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('prepare', 'verify'))
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--allow-historical-test', action='store_true', help='Only after explicit authorization to use a study-relative test cohort with historical exposure disclosed.')
    parser.add_argument('--scope-authorization', help='Exact explicit user decision permitting disclosed historical exposure.')
    args = parser.parse_args()
    result = prepare(args.output_dir.resolve(), allow_historical=args.allow_historical_test,
                     scope_authorization=args.scope_authorization) if args.mode == 'prepare' else verify(args.output_dir.resolve())
    print(json.dumps(result, indent=2))
