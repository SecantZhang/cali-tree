"""Audit the local reconstructed-rubric probe without regenerating observations."""
import argparse
import json
from pathlib import Path
import shutil

from critical.core.decision import facet_policy_v150 as facets
from critical.core.decision.artifacts import digest, save_json
from critical.core.decision.bound_evidence_v2 import image_identity
from critical.lm_engine.local_qwen_v94 import file_hash, local_messages
from run.calitree_facet_probe_v150 import ROOT, CHECKPOINT, FROZEN, PRIOR, read


def classification_metrics(rows, field):
    """Independent metric implementation; the vision runtime needs no learner."""
    details = {}
    for k, name in enumerate(('no', 'partial', 'yes')):
        total = sum(r['reference'] == k for r in rows)
        predicted = sum(r[field] == k for r in rows)
        correct = sum(r['reference'] == k and r[field] == k for r in rows)
        details[name] = {'correct': correct, 'total': total, 'predicted': predicted,
            'recall': correct/total if total else 0., 'precision': correct/predicted if predicted else 0.,
            'f1': 2*correct/(total+predicted) if total+predicted else 0.}
    correct = sum(r['reference'] == r[field] for r in rows)
    return {'correct': correct, 'total': len(rows), 'accuracy': correct/len(rows),
        'balanced_accuracy': sum(d['recall'] for d in details.values())/3,
        'macro_f1': sum(d['f1'] for d in details.values())/3,
        'unresolved': sum(r[field] not in (0, 1, 2) for r in rows), 'per_class': details,
        'confusion_rows_reference_columns_prediction': [[sum(r['reference'] == a and r[field] == b for r in rows)
            for b in range(3)] for a in range(3)]}


def scalar_grade(value, cautious=False):
    content = value['new_requested_content']
    if content == 'none':
        return None if value['all_material_facets'] == 'yes' else 0
    if content != 'some':
        return None
    full = (value['all_material_facets'] == 'yes' and value['operation_fidelity'] == 'faithful' and
        value['source_entity_fidelity'] in ('preserved', 'incidental_change') and
        value['scope_coverage'] in ('full', 'not_applicable'))
    if full:
        return 2
    missing = (value['all_material_facets'] == 'no' or value['operation_fidelity'] == 'unfaithful' or
        value['source_entity_fidelity'] == 'material_unrequested_change' or value['scope_coverage'] == 'partial')
    return 1 if missing or cautious else None


def audit(probe, out, *, require_complete=True):
    from PIL import Image
    from transformers import AutoProcessor
    if out.exists():
        raise ValueError('Fresh facet-probe audit required')
    manifest, profile, protocol = read(probe/'manifest.json'), read(probe/'profile.json'), read(probe/'protocol.json')
    jobs, references = read(probe/'jobs.json'), read(probe/'references.json')
    assert digest(jobs) == manifest['jobs_ref'] and digest(profile) == manifest['profile_ref']
    assert digest(protocol) == manifest['protocol_ref'] and file_hash(CHECKPOINT) == manifest['checkpoint_sha256']
    for path, sha in manifest['code_sha256'].items():
        assert file_hash(path) == file_hash(probe/'source_snapshot'/Path(path).relative_to(ROOT)) == sha
    terminal = read(probe/'results.json')
    if require_complete:
        assert terminal['complete'] and terminal['responses'] == terminal['attempts'] == 48
    original = {r['case']: r for r in read(FROZEN/'fitting_replay.json')[:99]}
    raw = {r['case']: r for r in read(FROZEN/'replay_inputs_without_references.json')}
    meta = {r['case']: r for r in read(ROOT/'logs/exps/261021-paired-vision-v63/inputs_without_labels.json')}
    excluded = {meta[j['case']]['source_group'] for j in read(PRIOR/'jobs.json')}
    primary_groups = {r['source_group'] for r in read(ROOT/'logs/exps/261023-verified-semantic-compression-v112-r2/predictions.json')}
    assert len(references) == 24 and [list(references.values()).count(k) for k in range(3)] == [8, 8, 8]
    assert set(references) <= set(original)
    for case, label in references.items():
        assert label == original[case]['reference'] and meta[case]['source_group'] not in excluded|primary_groups
    checkpoint = read(CHECKPOINT)
    processor = AutoProcessor.from_pretrained(checkpoint['destination'], local_files_only=True, trust_remote_code=False, use_fast=True)
    processor.image_processor.size = {'longest_edge': profile['max_pixels'], 'shortest_edge': 64*32*32}
    values = {}; tokens = 0; reserved = 0; peaks = []; checks = []
    for job in jobs:
        assert digest({k: v for k, v in job.items() if k != 'request_ref'}) == job['request_ref']
        assert digest(job['prompt']) == job['prompt_ref'] and job['profile_ref'] == digest(profile)
        assert job['instruction'] == raw[job['case']]['program']['instruction']
        assert job['program_ref'] == raw[job['case']]['program']['program_ref']
        assert job['source_group'] == meta[job['case']]['source_group']
        hashes, pair = image_identity(job['evidence']); assert hashes == job['image_hashes'] and pair == job['image_pair_ref']
        key = job['case']+'-'+job['arm']; response_file = probe/'responses'/(key+'.json')
        if not response_file.exists():
            continue
        response = read(response_file); assert response['request_ref'] == job['request_ref']
        assert read(probe/'attempts'/(key+'.json'))['request_ref'] == job['request_ref']
        result = response.get('response')
        if result is None:
            reserved += 512; assert not response['accepted']; continue
        assert result['endpointHost'] == 'local-mlx' and result['model'] == profile['model']
        assert result['engine'] == profile['engine'] and 0 <= result['completionTokens'] <= 512
        tokens += result['completionTokens']; peaks.append(result['peakMemoryBytes'])
        assert result['peakMemoryBytes'] <= profile['memory_limit_bytes']
        media = [{'type': 'text', 'text': 'SOURCE image'}, {'type': 'image', 'path': job['evidence']['source_image']},
                 {'type': 'text', 'text': 'EDITED image'}, {'type': 'image', 'path': job['evidence']['edited_image']}]
        messages, paths = local_messages(job['prompt'], media)
        images = []
        for path in paths:
            with Image.open(path) as im:
                images.append(im.convert('RGB'))
        rendered = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True, enable_thinking=False)
        prepared = processor(text=[rendered], images=images, return_tensors='pt', padding=True)
        assert digest(rendered) == result['renderedPromptRef']
        assert int(prepared['input_ids'].numel()) == result['promptTokens']
        assert {k: list(v.shape) for k, v in prepared.items()} == result['inputShapes']
        if response['accepted']:
            assert result['finishReason'] == 'stop'
            value = json.loads(result['content']); assert value == response['value'] == result['parsed']
            if job['arm'] == 'facets':
                facets.validate(value)
                assert facets.decide(value) == scalar_grade(value)
                assert facets.decide(value, cautious=True) == scalar_grade(value, True)
            else:
                assert set(value) == {'label', 'rationale'} and value['label'] in ('no', 'partial', 'yes', 'unresolved')
            values[(job['case'], job['arm'])] = value
        checks.append({'case': job['case'], 'arm': job['arm'], 'accepted': response['accepted'],
                       'prompt_tokens': result['promptTokens'], 'completion_tokens': result['completionTokens']})
    assert tokens == terminal['emitted_tokens'] and reserved == terminal['reserved_tokens']
    assert tokens+reserved <= 24576 and terminal['attempts'] <= 48
    history = [json.loads(line) for line in (probe/'llm-histories.log').read_text().splitlines() if line.strip()]
    assert len(history) == terminal['attempts']
    rows = []
    for case, reference in references.items():
        r = values.get((case, 'regular')); f = values.get((case, 'facets'))
        regular = ('no', 'partial', 'yes').index(r['label']) if r and r['label'] in ('no', 'partial', 'yes') else -1
        strict = scalar_grade(f) if f else None; cautious = scalar_grade(f, True) if f else None
        rows.append({'case': case, 'reference': reference, 'regular': regular,
            'strict': strict if strict is not None else -1, 'cautious': cautious if cautious is not None else -1,
            'strict_regular_fallback': strict if strict is not None else regular,
            'facet_record_accepted': f is not None})
    metrics = {field: classification_metrics(rows, field) for field in ('regular', 'strict', 'cautious', 'strict_regular_fallback')}
    admission = (terminal['complete'] and sum(r['facet_record_accepted'] for r in rows) >= 23 and
        metrics['strict']['correct'] >= 18 and metrics['strict']['correct'] >= metrics['regular']['correct'] and
        metrics['strict']['per_class']['partial']['correct'] >= 5)
    report = {'passed': True, 'complete': terminal['complete'], 'cases': 24, 'metrics': metrics,
        'processor_replays': len(checks), 'emitted_tokens': tokens, 'peak_memory_bytes': max(peaks, default=0),
        'larger_collection_admission': admission,
        'admission_rule': 'Training-only strict readout at least18/24, at least regular control, Partial at least5/8 and at least23 accepted facet records. This is a collection admission rule, not a performance claim.',
        'new_paid_calls': 0, 'reserved_sources_used': 0, 'serving_changed': False,
        'scope': 'Paired diagnostic on protected fitting cases excluding rubric-induction sources. Not the276-case pipeline balanced accuracy. Regular-fallback readout is a derived exploratory diagnostic.'}
    out.mkdir(parents=True); save_json(out/'verification.json', report); save_json(out/'predictions.json', rows)
    save_json(out/'checks.json', checks)
    save_json(out/'manifest.json', {'auditor_sha256': file_hash(__file__), 'probe_manifest_sha256': file_hash(probe/'manifest.json'),
        'profile_ref': digest(profile), 'references_sha256': file_hash(probe/'references.json')})
    (out/'run.log').write_text('Paired local facet diagnostic audited against raw responses, CPU processor replay and source/token budgets.\n')
    (out/'llm-histories.log').write_text('No new neural or API calls during audit.\n')
    dest = out/'source_snapshot/run'/Path(__file__).name; dest.parent.mkdir(parents=True); shutil.copyfile(__file__, dest)
    print({'passed': True, 'metrics': {k: (v['correct'], v['balanced_accuracy']) for k, v in metrics.items()},
           'larger_collection_admission': admission}, flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--probe', type=Path, required=True)
    p.add_argument('--output-dir', type=Path, required=True); p.add_argument('--allow-incomplete', action='store_true')
    a = p.parse_args(); audit(a.probe.resolve(), a.output_dir.resolve(), require_complete=not a.allow_incomplete)
