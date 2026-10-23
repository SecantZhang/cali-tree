"""Versioned content cache for upstream evidence, never labels or tree verdicts.

Known instruction/image inputs reuse the same observed/interpreted evidence used
for training. Source IDs and training membership do not enter the cache key or
the coverage selector. A changed input/model/prompt contract cannot reuse a slot.
"""
from copy import deepcopy

from ....decision.artifacts import digest
from ....decision.bound_evidence_v2 import image_identity, TEMPLATES as OBSERVER_TEMPLATES
from ....decision.bound_compiler_v3 import TEMPLATE, REPAIR_TEMPLATE, VERSION as COMPILER_VERSION
from ....decision.semantic_interpretation_v5 import PROMPT, VERSION as INTERPRETER_VERSION
from ....calibration.semantic_hierarchy.portable_features_v8 import project, CONTRACT_REF
from .evidence_covered_judge import EvidenceCoveredJudge

VERSION = 'bound-input-evidence-cache-v1'
UPSTREAM_REF = digest({'compiler': COMPILER_VERSION, 'compile_prompt': TEMPLATE.read_text(), 'repair': REPAIR_TEMPLATE,
                       'observe_prompt': (OBSERVER_TEMPLATES / 'observe.txt').read_text(),
                       'interpretation': INTERPRETER_VERSION, 'interpret_prompt': PROMPT, 'features': CONTRACT_REF})


class BoundEvidenceCache:
    def __init__(self, identity, *, artifact=None):
        if not isinstance(identity, dict) or not identity.get('model'):
            raise ValueError('Explicit upstream model identity required')
        self.identity = deepcopy(identity); self.entries = {}
        if artifact is not None:
            if (set(artifact) != {'version', 'upstream_ref', 'identity', 'entries', 'artifact_ref'}
                    or artifact['version'] != VERSION or artifact['upstream_ref'] != UPSTREAM_REF
                    or artifact['identity'] != identity
                    or artifact['artifact_ref'] != digest({k: v for k, v in artifact.items() if k != 'artifact_ref'})):
                raise ValueError('Changed evidence-cache contract')
            for key, entry in artifact['entries'].items():
                self._validate(entry)
                if key != self._key(entry['instruction'], entry['image_pair_ref']):
                    raise ValueError('Changed evidence-cache input key')
            self.entries = deepcopy(artifact['entries'])

    def _key(self, instruction, pair_ref):
        return digest([UPSTREAM_REF, self.identity, instruction, pair_ref])

    @staticmethod
    def _validate(entry):
        if (set(entry) != {'instruction', 'image_pair_ref', 'program', 'observation', 'interpretation'}
                or entry['program']['instruction'] != entry['instruction']):
            raise ValueError('Cache may contain only bound upstream evidence')
        project(entry['program'], entry['observation'], entry['image_pair_ref'], entry['interpretation'])

    def add(self, instruction, evidence, program, observation, interpretation):
        pair = image_identity(evidence)[1]
        entry = {'instruction': instruction, 'image_pair_ref': pair, 'program': program,
                 'observation': observation, 'interpretation': interpretation}
        self._validate(entry); key = self._key(instruction, pair)
        if key in self.entries and self.entries[key] != entry:
            raise ValueError('Refusing to replace trained evidence with a different draw')
        self.entries[key] = deepcopy(entry)

    def lookup(self, instruction, evidence):
        pair = image_identity(evidence)[1]
        entry = self.entries.get(self._key(instruction, pair))
        if entry is not None:
            self._validate(entry)
        return deepcopy(entry)

    def export(self):
        artifact = {'version': VERSION, 'upstream_ref': UPSTREAM_REF, 'identity': deepcopy(self.identity),
                    'entries': deepcopy(self.entries)}
        artifact['artifact_ref'] = digest(artifact)
        return artifact


class CachedEvidenceCoveredJudge(EvidenceCoveredJudge):
    def __init__(self, calls, gate, evidence_cache, *, identity, **kwargs):
        if evidence_cache.identity != identity or getattr(calls, 'identity', identity) != identity:
            raise ValueError('Inference identity differs from cached extraction identity')
        super().__init__(calls, gate, **kwargs)
        self.evidence_cache = evidence_cache

    def judge(self, instruction, evidence, *, program=None, observation=None, interpretation=None, **kwargs):
        origin = 'provided' if any(v is not None for v in (program, observation, interpretation)) else 'fresh'
        if origin == 'fresh':
            entry = self.evidence_cache.lookup(instruction, evidence)
            if entry is not None:
                program, observation, interpretation = (entry[k] for k in ('program', 'observation', 'interpretation'))
                origin = 'content_cache'
        result = super().judge(instruction, evidence, program=program, observation=observation, interpretation=interpretation, **kwargs)
        return {**result, 'evidence_source': origin}
