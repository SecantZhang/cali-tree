"""Prepare a label-free spatial projection reusing the frozen v63 image cache."""
import argparse
from pathlib import Path

from critical.core.decision.artifacts import save_json, digest
from run.calitree_aurora_pilot_v29 import ROOT, read, fingerprint
from run.spatial_vision_features_v65 import probes, CONTRACT_REF, VERSION

PARENT = ROOT / 'logs/exps/261021-paired-vision-v63'


def prepare(out):
    if out.exists():
        raise ValueError('Fresh output directory required')
    inputs = read(PARENT / 'inputs_without_labels.json')
    entries = [{'case': e['case'], 'evidence': e['evidence'], 'probes': probes(e['program'])} for e in inputs]
    assert len(entries) == 915
    out.mkdir(parents=True)
    save_json(out / 'inputs_without_labels.json', entries)
    save_json(out / 'protocol.json', {'version': VERSION, 'contract_ref': CONTRACT_REF,
              'parent': str(PARENT), 'parent_encoder_ref': digest(read(PARENT / 'encoder_identity.json')),
              'features': 'Instruction-oriented target/reference displacement and proximity margins; no absolute coordinates or entity IDs as predictors.',
              'scope': 'Additional local text encoding only, existing image encodings reused; no labels, uploads, paid calls or reserved sources.',
              'limits': 'Coarse3x3 query localization; no certified boxes, depth or camera-motion correction.', 'new_paid_model_calls': 0})
    save_json(out / 'manifest.json', {'inputs_sha256': fingerprint(out / 'inputs_without_labels.json'),
              'parent_manifest_sha256': fingerprint(PARENT / 'manifest.json'),
              'parent_inputs_sha256': fingerprint(PARENT / 'inputs_without_labels.json'),
              'code_hashes': {str(p): fingerprint(p) for p in (Path(__file__).resolve(), ROOT / 'run/spatial_vision_features_v65.py', ROOT / 'run/extract_calitree_spatial_v65.py')}})
    (out / 'run.log').write_text('Prepared915-case label-free relative geometry; frozen image features reused.\n')
    (out / 'llm-histories.log').write_text('Zero API/model service calls.\n')
    print({'cases': 915, 'spatial_probe_cases': sum(bool(e['probes']) for e in entries)}, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    prepare(args.output_dir.resolve())
