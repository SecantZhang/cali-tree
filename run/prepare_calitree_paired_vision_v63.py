"""Freeze label-free fitting/development image pairs for local visual extraction."""
import argparse
from pathlib import Path

from critical.core.decision.artifacts import save_json
from run.calitree_intent_policy_v60 import arrays
from run.calitree_fidelity_policy_v56 import evidence_metadata
from run.calitree_continuous_policy_v43 import RESERVED
from run.paired_vision_features_v63 import VERSION, MODEL, REVISION, CONTRACT_REF, SPECS, query_plan
from run.calitree_aurora_pilot_v29 import ROOT, read, fingerprint


def prepare(out):
    if out.exists():
        raise ValueError('Fresh output directory required')
    local, recent, extra, _, _, _, _, _, _ = arrays()
    examples, metadata = local + recent + extra, evidence_metadata()
    reserved = {e['source_group'] for e in read(RESERVED / 'inputs_without_labels.json')}
    assert not reserved & {e['source_group'] for e in examples}
    entries, images = [], {}
    for e in examples:
        evidence = e['evidence'] if e['case'].startswith('S') else metadata[e['case']]['evidence']
        entries.append({'case': e['case'], 'source_group': e['source_group'], 'program': e['program'],
                        'evidence': evidence, 'query_plan': query_plan(e['program'])})
        for p in evidence.values():
            images[p] = fingerprint(p)
    assert len(entries) == 915 and len({e['case'] for e in entries}) == 915
    out.mkdir(parents=True)
    save_json(out / 'inputs_without_labels.json', entries)
    save_json(out / 'protocol.json', {'version': VERSION, 'model': MODEL, 'revision': REVISION,
              'feature_contract_ref': CONTRACT_REF, 'cases': 915, 'source_groups': 182, 'grids': [1, 2, 3],
              'backend': 'mps', 'dtype': 'float32', 'torch_version': '2.9.0', 'transformers_version': '4.57.6',
              'scores': 'Global/patch preservation, target correspondence, goal similarity change and explicit desired-property contrast.',
              'predictors': 'Fixed Boolean thresholds of scalar input-relative scores. No raw image/text vectors, IDs, coordinates or object/color identity flags.',
              'scope': 'Frozen local encoder only on existing fitting/development images. No reference labels supplied to extraction, training or fine-tuning of the encoder.',
              'limits': 'Coarse patches are not certified target segmentation. First compiled outcome target anchors local matching; compound intent also has a global instruction score.',
              'new_paid_model_calls': 0, 'image_uploads': 0, 'reserved_sources_used': 0, 'serving_change': False})
    save_json(out / 'manifest.json', {'inputs_sha256': fingerprint(out / 'inputs_without_labels.json'),
              'protocol_sha256': fingerprint(out / 'protocol.json'), 'image_hashes': images,
              'code_hashes': {str(p): fingerprint(p) for p in (Path(__file__).resolve(), ROOT / 'run/paired_vision_features_v63.py', ROOT / 'run/extract_calitree_paired_vision_v63.py')},
              'reserved_inputs_sha256': fingerprint(RESERVED / 'inputs_without_labels.json')})
    save_json(out / 'feature_specs.json', SPECS)
    (out / 'run.log').write_text('Prepared label-free 915-case local frozen-encoder extraction; reserved sources excluded; zero paid requests or image uploads.\n')
    (out / 'llm-histories.log').write_text('Zero LLM/API requests. Local pretrained-encoder measurements recorded in cases/.\n')
    print({'cases': 915, 'image_paths': len(images), 'unique_image_bytes': len(set(images.values())), 'queries': len({text for e in entries for text in [e['query_plan']['target'], e['query_plan']['goal']]})}, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    prepare(args.output_dir.resolve())
