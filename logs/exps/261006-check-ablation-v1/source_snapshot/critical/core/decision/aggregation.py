"""Only requested outcomes contribute progress; support absence is useful evidence."""
def aggregate(program, observations):
    index = {o.check_id: o for o in observations}
    if len(index) != len(observations):
        return None, 'duplicate observations'
    states = []
    by_id = {c.id: c for c in program.checks}
    def known(c):
        obs = index.get(c.id)
        return (obs is not None and obs.valid and obs.status in ('complete', 'partial', 'absent')
                and all(known(by_id[d]) for d in c.dependencies))
    for outcome in program.outcomes:
        if outcome.applicability == 'unknown':
            return None, 'unknown applicability'
        if outcome.applicability == 'not_applicable':
            continue
        check = next(c for c in program.checks if c.outcome_id == outcome.id and c.role == 'requested')
        if not known(check):
            return None, 'required observation unknown or invalid'
        states.append(index[check.id].status)
    if not states:
        return None, 'empty applicable outcome set'
    label = 'yes' if all(s == 'complete' for s in states) else 'no' if all(s == 'absent' for s in states) else 'partial'
    return label, program.aggregation
