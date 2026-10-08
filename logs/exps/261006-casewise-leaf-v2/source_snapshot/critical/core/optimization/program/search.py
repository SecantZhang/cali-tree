"""Budgeted local graph repair retaining the seed and valid intermediate programs."""
from copy import deepcopy
from critical.core.decision.artifacts import export_program, program_ref, restore_program
from critical.core.decision.calls import BudgetExhausted, CallFailure
from critical.core.decision.validation import validate_program
from .base import LeafOptimizer
from .models import LeafResult, Transaction
from .edits import apply_transaction
from .evaluation import LocalAcceptance

INVALID = (ValueError, KeyError, TypeError, CallFailure)
class CasewiseOptimizer(LeafOptimizer):
    def __init__(self, compiler, proposer, evaluator, *, rubric, acceptance=None, rounds=2, beam_width=2, proposals_per_parent=2):
        if any(type(v) is not int or v < 1 for v in (rounds, beam_width, proposals_per_parent)):
            raise ValueError('Invalid search bounds')
        self.compiler, self.proposer, self.evaluator, self.rubric = compiler, proposer, evaluator, rubric
        self.acceptance = acceptance or LocalAcceptance()
        self.rounds, self.beam_width, self.proposals_per_parent = rounds, beam_width, proposals_per_parent

    def optimize(self, case, reference_label, *, seed=None):
        if reference_label not in ('yes', 'partial', 'no'):
            raise ValueError('Invalid reference label')
        result = LeafResult(case.id)
        reports, programs, audits, confirmed = {}, {}, {}, set()
        diagnostics = []
        def evaluate(p, namespace, repeats=1):
            return self.evaluator.evaluate(p, case, reference_label, repeats=repeats, namespace=case.id + '/' + namespace)
        def key(ref):
            return self.acceptance.rank(reports[ref], programs[ref])
        def test(p, ref):
            # Audit rejection stays available as structural feedback but cannot become a fitted winner.
            audit = self.compiler.audit(p, slot=f'{case.id}/audit/{ref}')
            audits[ref] = audit
            result.candidates[ref]['audit'] = audit
            report = evaluate(p, 'screen/' + ref)
            reports[ref] = report
            result.candidates[ref]['screen'] = report
            if audit['accepted'] and report['agreement'] == 1 and report['coverage'] == 1:
                confirmation = evaluate(p, 'confirm/' + ref, 3)
                reports[ref] = confirmation
                result.candidates[ref]['confirmation'] = confirmation
                confirmed.add(ref)
                return confirmation['agreement'] == 1 and confirmation['coverage'] == 1
            return False
        try:
            try:
                seed = seed or self.compiler.compile(case.instruction, self.rubric, slot=case.id + '/compile')
                validate_program(seed)
                if seed.instruction != case.instruction:
                    raise ValueError('Seed instruction differs from the case')
            except INVALID as exc:
                result.stop_reason = 'compilation_failed: ' + str(exc)
                return result
            seed_ref = program_ref(seed)
            result.seed = export_program(seed)
            result.selected = result.seed
            programs[seed_ref] = seed
            result.candidates[seed_ref] = export_program(seed)
            try:
                success = test(seed, seed_ref)
            except INVALID as exc:
                diagnostics.append({'stage': 'seed_execution', 'reason': str(exc)})
                success = False
            if success:
                result.status, result.stop_reason = 'confirmed_local', 'seed_matches'
                return result
            beam, seen = [seed_ref], {seed_ref}
            for round_id in range(self.rounds):
                pool = list(beam)
                for parent in beam:
                    feedback = {'report': reports.get(parent), 'audit': audits.get(parent), 'diagnostics': deepcopy(diagnostics)}
                    try:
                        proposals = self.proposer.propose(programs[parent], case, reference_label, feedback,
                                    slot=f'{case.id}/round/{round_id}/{parent}', limit=self.proposals_per_parent)
                    except INVALID as exc:
                        record = {'parent': parent, 'round': round_id, 'stage': 'proposal', 'reason': str(exc)}
                        diagnostics.append(record); result.lineage.append(record)
                        continue
                    for raw in proposals[:self.proposals_per_parent]:
                        record = {'parent': parent, 'round': round_id, 'transaction': raw.to_dict() if isinstance(raw, Transaction) else raw}
                        result.lineage.append(record)
                        try:
                            tx = raw if isinstance(raw, Transaction) else Transaction.from_dict(raw)
                            candidate, mappings = apply_transaction(programs[parent], tx)
                            ref = program_ref(candidate)
                            record.update(program_ref=ref, mappings=mappings)
                            if ref in seen:
                                raise ValueError('Duplicate candidate')
                            seen.add(ref); programs[ref] = candidate
                            result.candidates[ref] = export_program(candidate)
                            success = test(candidate, ref)
                            record['valid'] = True
                            if audits[ref]['accepted']:
                                pool.append(ref)
                            else:
                                diagnostics.append({'stage': 'semantic_audit', 'reason': audits[ref]['reason'], 'program_ref': ref})
                            if success:
                                result.selected = export_program(candidate)
                                result.status, result.stop_reason = 'confirmed_local', 'matching_confirmation'
                                return result
                        except INVALID as exc:
                            record.update(valid=False, reason=str(exc))
                            diagnostics.append({'stage': 'transaction', 'reason': str(exc)})
                # Keep neutral intermediates for deeper repair; seed remains independently retained.
                valid = [r for r in dict.fromkeys(pool) if r in reports]
                valid.sort(key=key, reverse=True)
                beam = valid[:self.beam_width] or [seed_ref]
                if seed_ref not in beam:
                    beam = [seed_ref] + beam[:self.beam_width - 1]
            result.stop_reason = 'round_limit'
        except BudgetExhausted as exc:
            result.stop_reason = str(exc)
            result.status = 'budget_limited'
        finally:
            calls = getattr(self.compiler, 'calls', None)
            if calls is not None:
                result.usage = deepcopy(calls.budget.get('cases', {}).get(str(case.id), {}))
        eligible = [r for r in confirmed if audits.get(r, {}).get('accepted')]
        # Never select a less-supported speculative repair over the original seed.
        if result.seed:
            base = program_ref(seed)
            choices = eligible + ([base] if base in reports else [])
            if choices:
                best = max(choices, key=key)
                if audits.get(best, {}).get('accepted') or best == base:
                    result.selected = export_program(programs[best])
            ref = result.selected['program_ref']
            report = reports.get(ref)
            if result.status != 'budget_limited':
                result.status = ('unresolved' if not report or report['coverage'] < 1 else
                                 'unstable' if report['flip_rate'] > 0 else 'unmatched')
        return result
