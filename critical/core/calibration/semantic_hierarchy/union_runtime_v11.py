"""One frozen union policy: no M4 router, case membership, or inference fitting."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

from ...decision.artifacts import digest, save_json
from ...decision.bound_evidence_v2 import VERSION as PHYSICAL_VERSION, TEMPLATES, COMPILER_SCHEMA
from ...decision.semantic_interpretation_v5 import VERSION as MEANING_VERSION, PROMPT
from .portable_features_v8 import CONTRACT_REF, project
from .portable_runtime_v8 import PortableRuleExecutor

VERSION = 'single-union-semantic-judge-v11'
FILES = ('judge.json', 'compile.txt', 'observe.txt', 'interpret.txt', 'compiler_schema.json')


class UnionJudge:
    def __init__(self, artifact):
        if (not isinstance(artifact, dict) or set(artifact) != {'version', 'feature_contract_ref', 'policy', 'upstream', 'artifact_ref'}
                or artifact['version'] != VERSION or artifact['feature_contract_ref'] != CONTRACT_REF
                or digest({k: v for k, v in artifact.items() if k != 'artifact_ref'}) != artifact['artifact_ref']):
            raise ValueError('Invalid single-policy union contract')
        self.executor = PortableRuleExecutor(artifact['policy'])
        self.artifact = deepcopy(artifact)

    def predict_records(self, records):
        return self.executor.predict_records(records)

    def predict_bound(self, program, observation, image_pair_ref, interpretation):
        record = project(program, observation, image_pair_ref, interpretation) if observation is not None else None
        return self.executor.predict_records([record])[0]

    def export(self):
        return deepcopy(self.artifact)


def export(directory, runtime):
    directory = Path(directory); directory.mkdir(parents=True, exist_ok=True)
    PortableRuleExecutor(runtime)
    upstream = {'physical_version': PHYSICAL_VERSION, 'interpretation_version': MEANING_VERSION,
                'judge_model': 'gpt-6.1-sol', 'reasoning_effort': 'high', 'presentation': 'source_first',
                'attempts_per_case_per_stage': 1, 'fresh_case_model_passes': 3,
                'routing_model_passes': 0, 'rule_execution_model_passes': 0,
                'compiler_schema_ref': digest(COMPILER_SCHEMA)}
    artifact = {'version': VERSION, 'feature_contract_ref': CONTRACT_REF, 'policy': deepcopy(runtime), 'upstream': upstream}
    artifact['artifact_ref'] = digest(artifact); UnionJudge(artifact)
    contents = {'judge.json': json.dumps(artifact, indent=2) + '\n',
                'compile.txt': (TEMPLATES / 'compile.txt').read_text(),
                'observe.txt': (TEMPLATES / 'observe.txt').read_text(), 'interpret.txt': PROMPT,
                'compiler_schema.json': json.dumps(COMPILER_SCHEMA, indent=2) + '\n'}
    for name, value in contents.items():
        p = directory / name
        if p.exists() and p.read_text() != value:
            raise ValueError('Refusing to overwrite a different frozen union inference file')
        if not p.exists():
            p.write_text(value)
    manifest = {'version': VERSION, 'judge_ref': artifact['artifact_ref'], 'policy_ref': runtime['artifact_ref'],
                'files': {name: sha256((directory / name).read_bytes()).hexdigest() for name in FILES},
                'inference_policies': 1, 'router_present': False, 'training_records_present': False}
    manifest['manifest_ref'] = digest(manifest)
    p = directory / 'manifest.json'
    if p.exists() and json.loads(p.read_text()) != manifest:
        raise ValueError('A frozen inference manifest changed')
    if not p.exists():
        save_json(p, manifest)
    load(directory)
    return manifest


def load(directory):
    directory = Path(directory); m = json.loads((directory / 'manifest.json').read_text())
    if (m.get('version') != VERSION or set(m.get('files', {})) != set(FILES)
            or m.get('inference_policies') != 1 or m.get('router_present') is not False
            or m.get('training_records_present') is not False
            or digest({k: v for k, v in m.items() if k != 'manifest_ref'}) != m.get('manifest_ref')):
        raise ValueError('Invalid frozen union package')
    for name, expected in m['files'].items():
        if sha256((directory / name).read_bytes()).hexdigest() != expected:
            raise ValueError('Changed union inference file: ' + name)
    judge = UnionJudge(json.loads((directory / 'judge.json').read_text()))
    if judge.artifact['artifact_ref'] != m['judge_ref'] or judge.artifact['policy']['artifact_ref'] != m['policy_ref']:
        raise ValueError('Union package policy identity mismatch')
    return judge
