"""Save/load a deployment-only hierarchy with exact upstream prompt contracts."""
from hashlib import sha256
import json
from pathlib import Path

from ...decision.artifacts import digest, save_json
from ...decision.bound_evidence_v2 import TEMPLATES, COMPILER_SCHEMA
from ...decision.semantic_interpretation_v5 import PROMPT, FIELDS, VERSION as MEANING_VERSION
from .hierarchy_runtime_v9 import HierarchyExecutor

VERSION = 'frozen-semantic-hierarchy-package-v9'
FILES = ('hierarchy.json', 'compile.txt', 'observe.txt', 'interpret.txt', 'compiler_schema.json', 'contracts.json')


def export(directory, bundle):
    directory = Path(directory); directory.mkdir(parents=True, exist_ok=True)
    HierarchyExecutor(bundle)
    contents = {'hierarchy.json': json.dumps(bundle, indent=2) + '\n',
                'compile.txt': (TEMPLATES / 'compile.txt').read_text(),
                'observe.txt': (TEMPLATES / 'observe.txt').read_text(),
                'interpret.txt': PROMPT,
                'compiler_schema.json': json.dumps(COMPILER_SCHEMA, indent=2) + '\n',
                'contracts.json': json.dumps({'extraction': bundle['extraction'],
                    'interpretation_version': MEANING_VERSION, 'interpretation_fields': FIELDS,
                    'labels': {'-1': 'Unresolved', '0': 'No', '1': 'Partial', '2': 'Yes'},
                    'prediction_input': ['program', 'observation', 'image_pair_ref', 'interpretation'],
                    'human_reference_input': 'prohibited', 'inference_fitting': 'prohibited'}, indent=2) + '\n'}
    for name, text in contents.items():
        p = directory / name
        if p.exists() and p.read_text() != text:
            raise ValueError('Refusing to change an existing frozen inference file: ' + name)
        if not p.exists():
            p.write_text(text)
    manifest = {'version': VERSION, 'bundle_ref': bundle['bundle_ref'],
                'files': {name: sha256((directory / name).read_bytes()).hexdigest() for name in FILES},
                'training_records_included': False, 'model_calls_for_rule_execution': 0}
    manifest['manifest_ref'] = digest(manifest)
    p = directory / 'manifest.json'
    if p.exists() and json.loads(p.read_text()) != manifest:
        raise ValueError('Changed inference package manifest')
    if not p.exists():
        save_json(p, manifest)
    load(directory)
    return manifest


def load(directory):
    directory = Path(directory); manifest = json.loads((directory / 'manifest.json').read_text())
    if (manifest.get('version') != VERSION or set(manifest.get('files', {})) != set(FILES)
            or manifest.get('training_records_included') is not False
            or manifest.get('model_calls_for_rule_execution') != 0
            or digest({k: v for k, v in manifest.items() if k != 'manifest_ref'}) != manifest.get('manifest_ref')):
        raise ValueError('Invalid inference package manifest')
    for name, expected in manifest['files'].items():
        if sha256((directory / name).read_bytes()).hexdigest() != expected:
            raise ValueError('Changed frozen inference contract: ' + name)
    bundle = json.loads((directory / 'hierarchy.json').read_text())
    if bundle['bundle_ref'] != manifest['bundle_ref']:
        raise ValueError('Inference package references another hierarchy')
    return HierarchyExecutor(bundle)

