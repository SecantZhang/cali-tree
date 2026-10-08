"""Bounded structural beam search retaining the original program and all lineage."""
from critical.core.decision.artifacts import program_ref
from critical.core.decision.calls import BudgetExhausted, CallFailure
from critical.core.decision.validation import validate_program, bound_checks

from .base import DecisionProgramOptimizer
from .acceptance import GuardedAcceptance, rank
from .edits import apply_edit
from .evaluation import validate_partitions
from .feedback import training_feedback
from .models import ProgramOptimizationResult


class StructuralOptimizer(DecisionProgramOptimizer):
    def __init__(self, proposer, evaluator, *, acceptance=None, rounds=2, beam_width=2, proposals_per_parent=2):
        if any(type(v) is not int or v < 1 for v in (rounds, beam_width, proposals_per_parent)):
            raise ValueError("Search limits must be positive integers")
        self.proposer, self.evaluator = proposer, evaluator
        self.acceptance = acceptance or GuardedAcceptance()
        self.rounds, self.beam_width, self.proposals_per_parent = rounds, beam_width, proposals_per_parent

    def optimize(self, seed, context):
        validate_program(seed)
        if not context.fit:
            raise ValueError("Search needs training cases")
        validate_partitions(context.fit, context.selection)
        seed_ref = program_ref(seed)
        lineage, reports, programs = [], {}, {seed_ref: seed}
        ns = context.namespace
        fit = self.evaluator.evaluate(seed, context.fit, repeats=1, namespace=ns + "/fit")
        selection = (self.evaluator.evaluate(seed, context.selection, repeats=3, namespace=ns + "/selection")
                     if context.selection else None)
        reports[seed_ref] = {"fit": fit, "selection": selection}
        baseline = selection or fit
        winner, beam, seen = seed_ref, [seed_ref], {seed_ref}
        stop = "round_limit"
        try:
            for round_id in range(self.rounds):
                screened = []
                for parent in beam:
                    slot = f"{ns}/{round_id}/{parent}"
                    try:
                        edits = self.proposer.propose(programs[parent], training_feedback(context.fit, reports[parent]["fit"]),
                                                      slot=slot, limit=self.proposals_per_parent)
                    except (ValueError, KeyError, TypeError, CallFailure) as exc:
                        lineage.append({"parent": parent, "round": round_id, "accepted": False, "reason": str(exc)})
                        continue
                    for index, edit in enumerate(edits[:self.proposals_per_parent]):
                        record = {"parent": parent, "round": round_id, "edit": edit.to_dict(), "accepted": False}
                        lineage.append(record)
                        try:
                            candidate = apply_edit(programs[parent], edit)
                            ref = program_ref(candidate)
                            record.update(program_ref=ref, program=candidate.to_dict())
                            if ref in seen:
                                record["reason"] = "duplicate program"
                                continue
                            seen.add(ref)
                            # Validate bound coverage before any candidate observation.
                            for case in (*context.fit, *context.selection):
                                bound_checks(candidate, case.plan, self.evaluator.executor.max_checks)
                            audit = self.proposer.audit(programs[parent], candidate, edit, slot=f"{slot}/{index}")
                            record["audit"] = audit
                            if not audit["accepted"]:
                                record["reason"] = "semantic audit rejected candidate"
                                continue
                            programs[ref] = candidate
                            candidate_fit = self.evaluator.evaluate(candidate, context.fit, repeats=1, namespace=ns + "/fit")
                            reports[ref] = {"fit": candidate_fit, "selection": None}
                            record["fit"] = candidate_fit
                            screened.append((ref, record))
                        except (ValueError, KeyError, TypeError, CallFailure) as exc:
                            record["reason"] = str(exc)
                if not screened:
                    stop = "no_valid_candidates"
                    break
                screened.sort(key=lambda pair: rank(reports[pair[0]]["fit"]), reverse=True)
                eligible = []
                for ref, record in screened[:self.beam_width]:
                    candidate_selection = (self.evaluator.evaluate(programs[ref], context.selection, repeats=3,
                                           namespace=ns + "/selection") if context.selection else None)
                    reports[ref]["selection"] = candidate_selection
                    record["selection"] = candidate_selection
                    accepted, reason = self.acceptance.assess(baseline, candidate_selection or reports[ref]["fit"])
                    record.update(accepted=accepted, reason=reason)
                    if accepted:
                        eligible.append(ref)
                for _, record in screened[self.beam_width:]:
                    record["reason"] = "not shortlisted on training score"
                choices = list(dict.fromkeys([winner, seed_ref] + eligible))
                choices.sort(key=lambda ref: rank(reports[ref]["selection"] or reports[ref]["fit"]), reverse=True)
                improved = choices[0] != winner
                winner = choices[0]
                beam = choices[:self.beam_width]
                if not improved:
                    stop = "no_supported_improvement"
                    break
        except BudgetExhausted:
            stop = "search_budget_exhausted"
        chosen = reports[winner]
        supported = bool(context.selection and chosen["selection"]["group_count"] >= 3
                         and all(v is not None for v in chosen["selection"]["recall"].values())
                         and winner != seed_ref and len({c.group for c in context.fit}) >= 2)
        return ProgramOptimizationResult(programs[winner], chosen["fit"], chosen["selection"], lineage, stop,
                                         "validated_for_reuse" if supported else "locally_fitted")
