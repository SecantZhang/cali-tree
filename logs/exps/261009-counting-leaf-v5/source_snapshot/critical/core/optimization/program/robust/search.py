"""Local structural optimization with durable replay and separate evidence tiers."""
from copy import deepcopy
from dataclasses import asdict
import random
from critical.core.decision.calls import BudgetExhausted, CallFailure
from critical.core.decision.robust.models import export_program
from critical.core.optimization.program.base import LeafOptimizer
from critical.core.optimization.program.models import LeafResult, AppliedProgramEdit
from .edits import apply_transaction
from .frontier import ParetoArchive
from .metrics import RobustPolicy

class RobustLeafOptimizer(LeafOptimizer):
    def __init__(self, compiler, proposer, evaluator, gradient, *, rubric, selection='pareto', mode='tree',
                 random_seed=20261007, seed_audit=None, diagnosis=None, apply_edit=apply_transaction,
                 candidate_eligibility=None, round_batches=(1,2), stop_on_confirmation=False,
                 repair_failed_candidate=False):
        if selection not in ('greedy', 'pareto') or mode not in ('flat', 'tree'):
            raise ValueError('Invalid optimizer arm')
        self.compiler, self.proposer, self.evaluator, self.gradient = compiler, proposer, evaluator, gradient
        self.rubric, self.selection, self.mode, self.random_seed = rubric, selection, mode, random_seed
        self.seed_audit = seed_audit
        self.diagnosis, self.apply_edit = diagnosis, apply_edit
        self.candidate_eligibility = candidate_eligibility
        if not isinstance(round_batches,(tuple,list)) or not round_batches or any(type(n) is not int or n<1 for n in round_batches):
            raise ValueError('Search requires a nonempty positive-integer round schedule')
        if type(stop_on_confirmation) is not bool or type(repair_failed_candidate) is not bool:
            raise ValueError('Search stopping and follow-up settings must be boolean')
        self.round_batches=tuple(round_batches)
        self.stop_on_confirmation,self.repair_failed_candidate=stop_on_confirmation,repair_failed_candidate
        self.policy = evaluator.policy

    def optimize(self, case, reference_label, *, seed=None, budget=None):
        if reference_label not in ('yes', 'partial', 'no'):
            raise ValueError('Invalid reference label')
        if budget is not None:
            # The caller passes the enforced durable scope, never a cosmetic soft limit.
            if getattr(self.compiler, 'calls', None) is not budget:
                raise ValueError('budget must be the same durable call scope used by all components')
        result = LeafResult(case.id)
        programs, screens, confirmations, audits, diagnostic_reports = {}, {}, {}, {}, {}
        screen_front, confirm_front = ParetoArchive(1), ParetoArchive(self.policy.repeats)
        rng, diagnostics = random.Random(self.random_seed), []
        events = []
        seed_ref = None
        stop = 'round_limit'
        repair_parent=None
        rounds_completed=0

        def rank(ref, reports):
            return self.policy.rank(reports[ref])

        def eligible(ref):
            return self.candidate_eligibility is None or self.candidate_eligibility(programs[ref],seed)

        def screen(program):
            ref = program.ref
            programs[ref] = program
            result.candidates[ref] = export_program(program)
            audit = (self.seed_audit if ref == seed_ref and self.seed_audit is not None else
                     self.compiler.audit(program, slot=f'audit/{ref}'))
            audits[ref] = audit
            result.candidates[ref]['audit'] = audit
            if not audit['accepted']:
                diagnostics.append({'program_ref': ref, 'semantic_rejection': audit['reason']})
                return
            report = self.evaluator.evaluate(program, case, reference_label, repeats=1, namespace=f'screen/{ref}')
            screens[ref] = report
            result.candidates[ref]['screen'] = report
            screen_front.update({ref: report})

        def confirm(ref, namespace):
            nonlocal repair_parent
            report = self.evaluator.evaluate(programs[ref], case, reference_label, repeats=self.policy.repeats, namespace=namespace)
            confirmations[ref] = report
            result.candidates[ref]['confirmation'] = report
            result.candidates[ref]['acceptance'] = self.policy.assess(report, audits[ref])
            confirm_front.update({ref: report})
            if self.repair_failed_candidate and not result.candidates[ref]['acceptance']['qualified']:
                repair_parent=ref
                diagnostics.append({'program_ref':ref,'confirmation_rejection':
                    deepcopy(result.candidates[ref]['acceptance']),'next_action':'repair this failed candidate; no atomic expected state is implied'})
            elif self.repair_failed_candidate:
                repair_parent=None

        def confirmed_success():
            return any(eligible(ref) and self.policy.assess(report,audits[ref])['qualified']
                       for ref,report in confirmations.items())

        try:
            if seed is None:
                seed = self.compiler.compile(case.instruction, self.rubric, slot='compile').view(self.mode)
            if seed.instruction != case.instruction or seed.rubric != self.rubric or seed.mode != self.mode:
                raise ValueError('Seed differs from frozen local binding/configuration')
            seed_ref = seed.ref
            result.seed = result.selected = export_program(seed)
            screen(seed)
            if seed_ref in screens and eligible(seed_ref):
                confirm(seed_ref, 'confirm/seed/' + seed_ref)
            for round_index, batches in enumerate(self.round_batches):
                if self.stop_on_confirmation and confirmed_success():
                    stop='confirmation_qualified'
                    break
                if self.repair_failed_candidate and repair_parent is not None:
                    parents=[repair_parent]*batches
                elif not screens:
                    # A rejected seed still supplies structural diagnostics; it earns no score.
                    parents = [seed_ref] * batches
                elif self.selection == 'pareto':
                    parents = screen_front.sample(rng, batches)
                else:
                    incumbent = min(screens, key=lambda ref: (tuple(-v for v in rank(ref, screens)), ref))
                    parents = [incumbent] * batches
                events.append({'round': round_index, 'parents': parents})
                if self.repair_failed_candidate and repair_parent is not None:
                    events[-1]['parent_reason']='failed_confirmation_follow_up'
                new = []
                for batch, parent_ref in enumerate(parents):
                    parent = programs[parent_ref]
                    namespace = f'round/{round_index}/batch/{batch}'
                    try:
                        report = confirmations.get(parent_ref, screens.get(parent_ref))
                        # Audit-rejected programs may supply visual diagnostics, never
                        # selection scores, frontier points or acceptance evidence.
                        if report is None and self.diagnosis is not None:
                            if parent_ref not in diagnostic_reports:
                                diagnostic_reports[parent_ref] = self.evaluator.evaluate(parent, case, reference_label,
                                    repeats=1, namespace=f'diagnostic/{parent_ref}')
                                result.candidates[parent_ref]['diagnostic'] = diagnostic_reports[parent_ref]
                            report = diagnostic_reports[parent_ref]
                        discovery = (self.diagnosis.discover(parent, case, report, slot=namespace + '/discovery')
                                     if self.diagnosis is not None else None)
                        event = {'round': round_index, 'batch': batch, 'parent': parent_ref, 'gradients': {},
                                 'rejected_diagnostics': deepcopy(diagnostics)}
                        if discovery is not None:
                            event['visual_discovery'] = discovery
                        events.append(event)
                        if parent_ref in diagnostic_reports and parent_ref not in screens:
                            event['report_kind'] = 'diagnostic_only'
                        try:
                            gradients = self.gradient.feedback(parent, case, reference_label, report, slot=namespace + '/gradient') if report else {}
                        except (CallFailure, ValueError, TypeError, KeyError) as exc:
                            if self.diagnosis is None:
                                raise
                            gradients = {}
                            event['gradient_failure'] = {'failure': type(exc).__name__, 'error': str(exc)}
                            diagnostics.append({'stage': 'gradient', **event['gradient_failure']})
                        event['gradients'] = gradients
                        feedback = {'textual_gradients': gradients, 'report': report,
                                    'rejected_diagnostics': deepcopy(diagnostics)}
                        if discovery is not None:
                            feedback['visual_discovery'] = discovery
                        proposals = self.proposer.propose(parent, case, reference_label, feedback, slot=namespace + '/proposal', limit=2)
                    except (CallFailure, ValueError, TypeError, KeyError) as exc:
                        diagnostics.append({'stage': 'feedback/proposal', 'error': str(exc)})
                        continue
                    for index, tx in enumerate(proposals):
                        item = {'parent': parent_ref, 'round': round_index, 'batch': batch, 'index': index, 'transaction': tx}
                        result.lineage.append(item)
                        try:
                            applied = self.apply_edit(parent, tx)
                            if isinstance(applied,AppliedProgramEdit):
                                child=applied.program
                                item['construction']=applied.details
                            else:
                                child=applied
                            item.update(program_ref=child.ref, structural_valid=True)
                            if child.ref in programs:
                                item['duplicate'] = True
                                if self.repair_failed_candidate:
                                    diagnostics.append({'program_ref':child.ref,'duplicate':True,
                                        'error':'Already evaluated or unchanged program; propose a faithful semantic repair, not a repeat of the same candidate'})
                                continue
                            screen(child)
                            item['audit'] = audits[child.ref]
                            if child.ref in screens:
                                new.append(child.ref)
                        except (CallFailure, ValueError, TypeError, KeyError) as exc:
                            item.update(error=str(exc), accepted=False)
                            if hasattr(exc,'to_dict'):item['validation']=exc.to_dict()
                            diagnostics.append(deepcopy(item))
                available = [r for r in new if r not in confirmations and eligible(r)]
                if available:
                    chosen = min(available, key=lambda ref: (tuple(-v for v in rank(ref, screens)), ref))
                    confirm(chosen, f'confirm/round/{round_index}/{chosen}')
                rounds_completed+=1
            if self.stop_on_confirmation and confirmed_success():
                stop='confirmation_qualified'
        except BudgetExhausted as exc:
            stop = 'budget_exhausted: ' + str(exc)
        except (CallFailure, ValueError, TypeError, KeyError) as exc:
            stop = 'unresolved: ' + str(exc)
        qualifying = [ref for ref, report in confirmations.items() if eligible(ref) and self.policy.assess(report, audits[ref])['qualified']]
        pool, reports = (qualifying or [ref for ref in confirmations if eligible(ref)]), confirmations
        if not pool:
            pool, reports = [ref for ref in screens if eligible(ref)], screens
        selected = min(pool, key=lambda ref: (tuple(-v for v in rank(ref, reports)), ref)) if pool else seed_ref
        if selected:
            result.selected = export_program(programs.get(selected, seed))
        result.status = ('confirmed_local' if qualifying else 'budget_exhausted' if stop.startswith('budget') else
                         'unresolved' if selected not in reports or reports[selected]['coverage'] < 1 else
                         'label_matched_but_unstable' if reports[selected]['agreement'] >= self.policy.agreement else
                         'stable_but_mismatched' if reports[selected]['label_consistency'] == 1 else 'unstable_and_mismatched')
        if self.candidate_eligibility is not None and seed_ref is not None and not pool:
            result.status='structural_failure'
            if not stop.startswith('budget') and not self.stop_on_confirmation:stop='no_eligible_nested_candidate'
        result.stop_reason = stop
        calls = getattr(self.compiler, 'calls', None)
        if calls is not None:
            result.usage = deepcopy(calls.budget.get('cases', {}).get(getattr(calls, 'case_id', case.id), {}))
        result.lineage.append({'events': events, 'diagnostics': diagnostics,
            'screen_frontier': screen_front.history, 'confirmation_frontier': confirm_front.history,
            'seed_retained': seed_ref, 'selection': selected, 'policy': asdict(self.policy)})
        if self.candidate_eligibility is not None:
            result.lineage[-1]['selection_eligible']=bool(selected and eligible(selected))
            if not pool:result.lineage[-1]['selection_failure']='no_eligible_nested_candidate'
        if self.round_batches!=(1,2) or self.stop_on_confirmation or self.repair_failed_candidate:
            result.lineage[-1]['search_schedule']={'round_batches':list(self.round_batches),
                'rounds_started':sum('parents' in e for e in events),'rounds_completed':rounds_completed,
                'stop_on_confirmation':self.stop_on_confirmation,'repair_failed_candidate':self.repair_failed_candidate}
        return result
