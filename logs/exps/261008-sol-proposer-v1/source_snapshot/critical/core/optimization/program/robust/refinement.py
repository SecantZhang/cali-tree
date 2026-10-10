"""Instruction-grounded evidence additions and nested structural repairs."""
from critical.core.decision.compiler import object_schema, array, TEXT, media_inputs
from critical.core.decision.robust.refinement import template, validate_refinement
from .edits import apply_transaction, TX_SCHEMA
from .proposer import StructuralProposer

EVIDENCE_MAPPING_SCHEMA = object_schema({key: TEXT for key in ('node_id', 'requirement_id', 'source_phrase')})
REFINEMENT_TX_SCHEMA = object_schema({**TX_SCHEMA['properties'], 'evidence_mapping': array(EVIDENCE_MAPPING_SCHEMA)})
REFINEMENT_PROPOSAL_SCHEMA = object_schema({'transactions': array(REFINEMENT_TX_SCHEMA)})


def apply_evidence_transaction(parent, transaction):
    child = apply_transaction(parent, transaction)
    validate_refinement(child, parent)
    mappings = transaction.get('evidence_mapping')
    if not isinstance(mappings, list):
        raise ValueError('Evidence repairs need explicit node-to-requirement provenance')
    requirements, nodes = {r.id: r for r in parent.requirements}, {n.id: n for n in child.nodes}
    seen = set()
    for entry in mappings:
        if set(entry) != {'node_id', 'requirement_id', 'source_phrase'} or any(
                not isinstance(v, str) for v in entry.values()):
            raise ValueError('Invalid evidence provenance mapping')
        nid = entry['node_id']
        req = requirements.get(entry['requirement_id'])
        if nid in seen or nid not in nodes or nodes[nid].role != 'support' or req is None or not entry['source_phrase'].strip() or entry['source_phrase'] not in req.source_phrase:
            raise ValueError('Evidence mapping must quote a covered original requirement')
        seen.add(nid)
    originals = {n.id: n for n in parent.nodes}
    changed = {n.id for n in child.nodes if n.role == 'support' and originals.get(n.id) != n}
    if not changed <= seen:
        raise ValueError('Every added or revised support needs original instruction provenance')
    return child


class EvidenceRefinementProposer(StructuralProposer):
    def propose(self, program, case, reference_label, feedback, *, slot, limit=2):
        value, _ = self.calls.call('propose', {'instruction': program.instruction, 'rubric': program.rubric,
            'program': program.to_dict(), 'reference_label': reference_label, 'feedback': feedback, 'limit': limit},
            REFINEMENT_PROPOSAL_SCHEMA, template=template('propose'), media=media_inputs(case.evidence), slot=slot, max_tokens=2048)
        rows = value.get('transactions')
        if not isinstance(rows, list) or len(rows) > limit:
            raise ValueError('Proposal count exceeded or malformed')
        return rows


def create_evidence_refinement_optimizer(calls, original, *, reviewers=None, checkpoint=None,
                                         policy=None, selection='greedy', random_seed=20261008,
                                         seed_audit=None, round_batches=(1,2), stop_on_confirmation=False,
                                         repair_failed_candidate=False):
    """Configure a local repair pipeline; reviewers must share its durable scope."""
    from critical.core.decision.robust.refinement import EvidenceRefinementCompiler, EvidenceRefinementChecker
    from critical.core.decision.robust.executor import RobustExecutor
    from .discovery import VisualEvidenceDiagnosis, VisualReviewer
    from .metrics import RobustEvaluator
    from .proposer import NodeTextGrad
    from .search import RobustLeafOptimizer

    if reviewers is None:
        reviewers = (VisualReviewer('primary', calls.identity.get('family', calls.identity['model']), calls),)
    reviewers = tuple(reviewers)
    if any(r.calls.budget is not calls.budget or getattr(r.calls, 'case_id', None) != getattr(calls, 'case_id', None)
           for r in reviewers):
        raise ValueError('All reviewers must share the primary durable ledger and case scope')
    return RobustLeafOptimizer(EvidenceRefinementCompiler(calls, original), EvidenceRefinementProposer(calls),
        RobustEvaluator(RobustExecutor(EvidenceRefinementChecker(calls), checkpoint=checkpoint), policy),
        NodeTextGrad(calls), rubric=original.rubric, selection=selection, mode='tree', random_seed=random_seed,
        seed_audit=seed_audit, diagnosis=VisualEvidenceDiagnosis(reviewers), apply_edit=apply_evidence_transaction,
        round_batches=round_batches,stop_on_confirmation=stop_on_confirmation,repair_failed_candidate=repair_failed_candidate)
