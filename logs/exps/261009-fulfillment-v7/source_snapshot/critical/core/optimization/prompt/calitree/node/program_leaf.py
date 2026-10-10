"""Independent local leaves; no parent construction or cross-case fitting."""
from hashlib import sha256
from pathlib import Path
from critical.core.decision.artifacts import restore_program, program_ref
VERSION = 'calitree-casewise-leaves-v2'
ROBUST_VERSION = 'calitree-casewise-leaves-v3'
ADAPTIVE_VERSION = 'calitree-casewise-leaves-v4'
COUNTING_VERSION = 'calitree-casewise-leaves-v5'
ENDPOINT_VERSION = 'calitree-casewise-leaves-v6'
FULFILLMENT_VERSION = 'calitree-casewise-leaves-v7'

def artifact_runtime(bundle):
    if bundle.get('version') == FULFILLMENT_VERSION:
        from critical.core.decision.fulfillment import restore_program as restore_fulfillment
        return restore_fulfillment, lambda p: p.ref
    if bundle.get('version') == ENDPOINT_VERSION:
        from critical.core.decision.counting_v6 import restore_program as restore_endpoints
        return restore_endpoints, lambda p: p.ref
    if bundle.get('version') == COUNTING_VERSION:
        from critical.core.decision.counting import restore_program as restore_counting
        return restore_counting, lambda p: p.ref
    if bundle.get('version') == ADAPTIVE_VERSION:
        from critical.core.decision.robust.v4_models import restore_program as restore_v4
        return restore_v4, lambda p: p.ref
    if bundle.get('version') == ROBUST_VERSION:
        from critical.core.decision.robust.models import restore_program as restore_robust
        return restore_robust, lambda p: p.ref
    return restore_program, program_ref


def evidence_hashes(evidence):
    return {k: sha256(Path(evidence[k]).read_bytes()).hexdigest() for k in ('source_image', 'edited_image')}

class ProgramLeafController:
    def __init__(self, optimizer_factory):
        self.optimizer_factory = optimizer_factory
    def build(self, cases, reference_labels, *, seeds=None):
        if not cases or len({c.id for c in cases}) != len(cases) or set(reference_labels) != {c.id for c in cases}:
            raise ValueError('Need unique cases and exactly one reference label per case')
        bundle = {'version': VERSION, 'nodes': {}, 'programs': {}}
        for case in cases:
            optimizer = self.optimizer_factory(case)
            result = optimizer.optimize(case, reference_labels[case.id], seed=(seeds or {}).get(case.id))
            executor = optimizer.evaluator.executor
            robust = getattr(optimizer, 'mode', None) in ('flat', 'tree')
            version = getattr(optimizer, 'artifact_version', ROBUST_VERSION if robust else VERSION)
            if bundle['nodes'] and bundle['version'] != version:
                raise ValueError('Cannot mix executable artifact versions in one bundle')
            bundle['version'] = version
            node = {'id': 'leaf:' + case.id, 'case_id': case.id, 'fit_scope': [case.id],
                    'instruction': case.instruction, 'evidence_hashes': evidence_hashes(case.evidence),
                    'executor_identity': executor.checker.identity, 'max_checks': executor.max_checks,
                    'support_status': 'local_unverified', 'result': result.to_dict(),
                    'program_ref': result.selected['program_ref'] if result.selected else None}
            for artifact in (result.seed, result.selected):
                if artifact:
                    bundle['programs'][artifact['program_ref']] = artifact
            bundle['nodes'][node['id']] = node
        return validate_program_leaves(bundle)

def validate_program_leaves(bundle):
    if bundle.get('version') not in (VERSION, ROBUST_VERSION, ADAPTIVE_VERSION, COUNTING_VERSION, ENDPOINT_VERSION, FULFILLMENT_VERSION) or not bundle.get('nodes'):
        raise ValueError('Unsupported or empty leaf bundle')
    restore, identify = artifact_runtime(bundle)
    for ref, artifact in bundle['programs'].items():
        if identify(restore(artifact)) != ref:
            raise ValueError('Program reference mismatch')
    for key, node in bundle['nodes'].items():
        if node['id'] != key or node['fit_scope'] != [node['case_id']]:
            raise ValueError('Invalid local scope')
        if node['program_ref'] is not None:
            p = restore(bundle['programs'][node['program_ref']])
            if p.instruction != node['instruction'] or node['result']['selected']['program_ref'] != node['program_ref']:
                raise ValueError('Leaf binding mismatch')
    return bundle

def judge_program_leaf(bundle, node_id, evidence, executor, *, repeat='inference/0'):
    validate_program_leaves(bundle)
    node = bundle['nodes'][node_id]
    if node['program_ref'] is None:
        raise ValueError('Leaf has no executable program')
    if node['executor_identity'] != executor.checker.identity or node['max_checks'] != executor.max_checks:
        raise ValueError('Saved execution contract differs')
    if evidence_hashes(evidence) != node['evidence_hashes']:
        raise ValueError('A local leaf cannot silently substitute a different case')
    restore, _ = artifact_runtime(bundle)
    return executor.execute(restore(bundle['programs'][node['program_ref']]), evidence, repeat=repeat)
