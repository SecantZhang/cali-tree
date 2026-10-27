"""Outcome-primary rubric reconstructed from protected fitting contrasts.

Unrequested preservation defects remain observations, not automatic grade caps.
This is a different judging policy from the immutable fidelity-capped v150 tree.
"""
from . import facet_policy_v150 as facets
from .artifacts import digest

VERSION = 'explicit-outcome-primary-v160'
RUBRIC = '''Use visible newly realized instruction outcomes as the grade basis.
1. No newly realized requested content, with no contradictory full-outcome claim: No.
2. Some newly realized requested content and every material requested facet established across the required scope: Yes.
3. Some newly realized requested content with an established incomplete requested outcome: Partial.
4. Unknown progress, unknown completion, or contradictory complete/partial scope: defer.
Operation fidelity and source entity changes remain explicit advisory observations. They are not universal grade caps for instruction fulfillment. A context-specific learned guard may use them; it must be verified separately.
'''


def decide(value):
    v = facets.validate(value)
    content, complete = v['new_requested_content'], v['all_material_facets']
    if content == 'none':
        return None if complete == 'yes' else 0
    if content != 'some':
        return None
    if complete == 'yes':
        return 2 if v['scope_coverage'] in ('full', 'not_applicable') else None
    if complete == 'no':
        return 1
    return None


CONTRACT_REF = digest({'version': VERSION, 'observation_schema': facets.schema(), 'rubric': RUBRIC})
