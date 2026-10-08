"""Fixed outcome aggregation. Supporting checks cannot contribute edit progress."""
from .models import STATES


def aggregate(program, plan, observations):
    index = {(o.outcome_id, o.predicate_id): o for o in observations}
    if len(index) != len(observations):
        return None, "duplicate observations"
    outcomes = []
    for outcome in plan.outcomes:
        predicates = [p for p in program.predicates
                      if p.role == "requested" and outcome.operation in p.applies_to]
        statuses = []
        for p in predicates:
            obs = index.get((outcome.id, p.id))
            if obs is None or not obs.valid or obs.status not in STATES or obs.status == "unknown":
                return None, "missing, invalid or unknown requested observation"
            for dep in p.dependencies:
                support = index.get((outcome.id, dep))
                if support is None or not support.valid or support.status != "complete":
                    return None, "supporting evidence does not establish the binding"
            statuses.append(obs.status)
        if not statuses:
            return None, "empty applicable outcome set"
        outcomes.append("complete" if all(s == "complete" for s in statuses) else
                        "absent" if all(s == "absent" for s in statuses) else "partial")
    if not outcomes:
        return None, "empty applicable outcome set"
    label = "yes" if all(s == "complete" for s in outcomes) else "no" if all(s == "absent" for s in outcomes) else "partial"
    return label, "requested-all-some-none-v1"
