"""Independently replay bindings, inputs and unchanged grading for the v153 probe."""
import argparse
from collections import Counter
import json
from pathlib import Path
import shutil

from critical.core.decision import facet_policy_v150 as facets
from critical.core.decision.artifacts import digest, save_json
from critical.core.decision.bound_evidence_v2 import image_identity
from critical.lm_engine.local_qwen_v94 import file_hash, local_messages
from run.calitree_facet_probe_v150 import CHECKPOINT, FROZEN, PRIOR, ROOT, read
from run.verify_calitree_facet_probe_v151 import classification_metrics, scalar_grade


def audit(probe, out):
    from PIL import Image
    from transformers import AutoProcessor
    if out.exists():
        raise ValueError('Fresh explicit-facet audit required')
    manifest, profile, protocol = read(probe/'manifest.json'), read(probe/'profile.json'), read(probe/'protocol.json')
    jobs, references, terminal = read(probe/'jobs.json'), read(probe/'references.json'), read(probe/'results.json')
    assert terminal['complete'] and terminal['attempts'] == terminal['responses'] == len(jobs) == 48
    assert digest(jobs) == manifest['jobs_ref'] and digest(profile) == manifest['profile_ref']
    assert digest(protocol) == manifest['protocol_ref'] and file_hash(CHECKPOINT) == manifest['checkpoint_sha256']
    assert file_hash(probe/'references.json') == manifest['references_sha256']
    for path, sha in manifest['code_sha256'].items():
        assert file_hash(path) == file_hash(probe/'source_snapshot'/Path(path).relative_to(ROOT)) == sha
    prior = Path(protocol['prior_probe'])
    assert file_hash(prior/'manifest.json') == manifest['prior_manifest_sha256']
    assert references == read(prior/'references.json') and [list(references.values()).count(k) for k in range(3)] == [8, 8, 8]
    old_jobs = {j['case']: j for j in read(prior/'jobs.json') if j['arm'] == 'facets'}
    original = {r['case']: r for r in read(FROZEN/'fitting_replay.json')[:99]}
    raw = {r['case']: r for r in read(FROZEN/'replay_inputs_without_references.json')}
    meta = {r['case']: r for r in read(ROOT/'logs/exps/261021-paired-vision-v63/inputs_without_labels.json')}
    excluded = {meta[j['case']]['source_group'] for j in read(PRIOR/'jobs.json')}
    primary_groups = {r['source_group'] for r in read(ROOT/'logs/exps/261023-verified-semantic-compression-v112-r2/predictions.json')}
    reserved_groups = {r['source_group'] for r in read(ROOT/'logs/exps/261020-validation-reservation-v39/inputs_without_labels.json')}
    for case, reference in references.items():
        assert reference == original[case]['reference']
        assert meta[case]['source_group'] not in excluded|primary_groups|reserved_groups
    checkpoint = read(CHECKPOINT)
    processor = AutoProcessor.from_pretrained(checkpoint['destination'], local_files_only=True, trust_remote_code=False, use_fast=True)
    processor.image_processor.size = {'longest_edge': profile['max_pixels'], 'shortest_edge': 64*32*32}
    values = {}; tokens = 0; reserved = 0; checks = []; peaks = []; counts = {a: Counter() for a in protocol['arms']}
    gap_contradictions = {a: 0 for a in protocol['arms']}
    for job in jobs:
        old = old_jobs[job['case']]
        assert job['arm'] in protocol['arms']
        assert digest({k: v for k, v in job.items() if k != 'request_ref'}) == job['request_ref']
        assert job['profile_ref'] == digest(profile) and job['prompt_ref'] == digest(job['prompt'])
        for key in ('case', 'source_group', 'instruction', 'program_ref', 'evidence', 'image_pair_ref', 'image_hashes'):
            assert job[key] == old[key]
        assert job['instruction'] == raw[job['case']]['program']['instruction'] and job['program_ref'] == raw[job['case']]['program']['program_ref']
        assert job['source_group'] == meta[job['case']]['source_group']
        assert job['prompt'].startswith(old['prompt']) and json.dumps(job['schema']) in job['prompt']
        assert job['schema']['properties'] == facets.schema()['properties']
        assert set(job['schema']['required']) == set(facets.schema()['required'])
        assert job['schema']['type'] == 'object' and job['schema']['additionalProperties'] is False
        hashes, pair = image_identity(job['evidence']); assert hashes == job['image_hashes'] and pair == job['image_pair_ref']
        key = job['case']+'-'+job['arm']; response = read(probe/'responses'/(key+'.json'))
        assert response['request_ref'] == read(probe/'attempts'/(key+'.json'))['request_ref'] == job['request_ref']
        result = response.get('response')
        if result is None:
            reserved += 512; assert not response['accepted']; continue
        assert result['endpointHost'] == 'local-mlx' and result['model'] == profile['model'] and result['engine'] == profile['engine']
        assert 0 <= result['completionTokens'] <= 512 and result['peakMemoryBytes'] <= profile['memory_limit_bytes']
        tokens += result['completionTokens']; peaks.append(result['peakMemoryBytes'])
        media = [{'type': 'text', 'text': 'SOURCE image'}, {'type': 'image', 'path': job['evidence']['source_image']},
                 {'type': 'text', 'text': 'EDITED image'}, {'type': 'image', 'path': job['evidence']['edited_image']}]
        messages, paths = local_messages(job['prompt'], media); images = []
        for path in paths:
            with Image.open(path) as image:
                images.append(image.convert('RGB'))
        rendered = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True, enable_thinking=False)
        prepared = processor(text=[rendered], images=images, return_tensors='pt', padding=True)
        assert digest(rendered) == result['renderedPromptRef']
        assert int(prepared['input_ids'].numel()) == result['promptTokens']
        assert {k: list(v.shape) for k, v in prepared.items()} == result['inputShapes']
        if response['accepted']:
            assert result['finishReason'] == 'stop'
            value = facets.validate(json.loads(result['content'])); assert value == response['value'] == result['parsed']
            assert facets.decide(value) == scalar_grade(value)
            values[(job['case'], job['arm'])] = value
            counts[job['arm']][value['all_material_facets']] += 1
            no_gap = value['material_gap'].strip().lower().rstrip('.') == 'none'
            gap = (value['all_material_facets'] == 'no' or value['operation_fidelity'] == 'unfaithful' or
                   value['source_entity_fidelity'] == 'material_unrequested_change' or value['scope_coverage'] == 'partial')
            gap_contradictions[job['arm']] += int(no_gap and gap)
        checks.append({'case': job['case'], 'arm': job['arm'], 'accepted': response['accepted'],
            'prompt_tokens': result['promptTokens'], 'completion_tokens': result['completionTokens'],
            'follows_requested_order': list(response.get('value', {})) == list(job['schema']['properties'])})
    assert tokens == terminal['emitted_tokens'] and reserved == terminal['reserved_tokens']
    assert tokens+reserved <= 24576
    history = [json.loads(line) for line in (probe/'llm-histories.log').read_text().splitlines() if line.strip()]
    assert len(history) == 48
    rows = []
    for case, reference in references.items():
        old_regular = read(prior/'responses'/(case+'-regular.json'))
        old_facets = read(prior/'responses'/(case+'-facets.json'))
        row = {'case': case, 'reference': reference, 'cached_regular': -1, 'cached_facets': -1}
        if old_regular['accepted'] and old_regular['value']['label'] in ('no', 'partial', 'yes'):
            row['cached_regular'] = ('no', 'partial', 'yes').index(old_regular['value']['label'])
        if old_facets['accepted']:
            pred = scalar_grade(old_facets['value']); row['cached_facets'] = pred if pred is not None else -1
        for arm in protocol['arms']:
            v = values.get((case, arm)); pred = scalar_grade(v) if v else None
            row[arm] = pred if pred is not None else -1
        rows.append(row)
    metrics = {field: classification_metrics(rows, field) for field in ['cached_regular', 'cached_facets', *protocol['arms']]}
    rule = protocol['admission_rule']; admission = {}
    for arm in protocol['arms']:
        m = metrics[arm]
        admission[arm] = (sum((case, arm) in values for case in references) >= rule['accepted_min'] and
            m['correct'] >= rule['correct_min'] and min(r['correct'] for r in m['per_class'].values()) >= rule['each_grade_correct_min'] and
            gap_contradictions[arm] <= rule['literal_gap_contradictions_max'])
    report = {'passed': True, 'complete': True, 'cases': 24, 'processor_replays': len(checks), 'metrics': metrics,
        'completion_state_counts': counts, 'literal_gap_contradictions': gap_contradictions, 'larger_collection_admission': admission,
        'emitted_tokens': tokens, 'peak_memory_bytes': max(peaks, default=0), 'new_paid_calls': 0,
        'reserved_sources_used': 0, 'serving_changed': False,
        'scope': 'Adapted fitting-only prompt diagnostic on previously inspected24 fitting cases. Not source-held or final accuracy.'}
    out.mkdir(parents=True); save_json(out/'verification.json', report); save_json(out/'predictions.json', rows); save_json(out/'checks.json', checks)
    save_json(out/'manifest.json', {'auditor_sha256': file_hash(__file__), 'probe_manifest_sha256': file_hash(probe/'manifest.json'),
        'profile_ref': digest(profile), 'references_sha256': file_hash(probe/'references.json')})
    (out/'run.log').write_text('Explicit-facet observations audited against native responses and CPU tensor replay.\n')
    (out/'llm-histories.log').write_text('No model inference during audit.\n')
    dest = out/'source_snapshot/run'/Path(__file__).name; dest.parent.mkdir(parents=True); shutil.copyfile(__file__, dest)
    print({'passed': True, 'metrics': {k: (v['correct'], v['balanced_accuracy']) for k, v in metrics.items()},
        'literal_gap_contradictions': gap_contradictions, 'larger_collection_admission': admission}, flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--probe', type=Path, required=True)
    p.add_argument('--output-dir', type=Path, required=True); a = p.parse_args()
    audit(a.probe.resolve(), a.output_dir.resolve())
