"""Audit bound semantic descriptions against pixels with a frozen encoder.

Only input-relative scalar comparisons leave this module. A caption affinity is
a second model view, never a truth certificate or a grade by itself.
"""
import re

import numpy as np

from critical.core.decision.bound_evidence_v2 import validate_program,validate_observation
from .paired_features_v69 import normalized,digest

VERSION='bound-caption-visual-audit-v79'
ROLES=('outcome','intermediate','identity','collateral')
METRICS=('goal_source','goal_edited','goal_delta','goal_patch_source','goal_patch_edited','goal_patch_delta',
         'source_description_fit','edited_description_fit','edited_description_change_margin',
         'source_description_change_margin','description_change_alignment','description_pair_similarity')
NAMES=tuple(f'caption_{r}_{m}_{s}' for r in ROLES for m in METRICS for s in ('min','mean'))
DESCRIPTIONS={n:n.replace('_',' ')+': frozen image/text comparison of this input; not factual confidence.' for n in NAMES}
CONTRACT_REF=digest({'version':VERSION,'roles':ROLES,'metrics':METRICS,'aggregates':['min','mean'],
 'scope':'Bound questions and source/edited visible descriptions only. No grades, rationales, interpretation labels or references in text queries.',
 'recipe':'Full image and best14-view question affinity; own/cross caption agreement and normalized paired change alignment. Matching duplicate questions counted once.',
 'limit':'Questions may be relational or negated; encoder affinity is a fallible independent audit cue, not proof of endpoint or identity.'})


def goal_caption(question):
    # A fixed, label-free redescription. No task-specific rewriting or inferred
    # answer is inserted. The grammatical remainder may still be imperfect.
    value=question.strip().rstrip('? .')
    value=re.sub(r'^(?:Is|Are|Has|Have|Does|Do|Did)\s+','',value,flags=re.I)
    value=re.sub(r'\s+(?:compared (?:with|to)|relative to)\s+(?:its|their|the|her|his)\s+(?:original|source)\b.*$','',value,flags=re.I)
    value=re.sub(r'\s*,?\s*(?:as requested by the instruction|as requested|in the edited (?:image|scene))\b','',value,flags=re.I)
    return 'An image showing '+value+'.'


def plan(program,observation,pair_ref):
    validate_program(program)
    if observation is None:return []
    validate_observation(program,observation,pair_ref)
    rows=[];seen=set()
    for check in program['checks']:
        role=check['role']
        if role.startswith('collateral_'):role='collateral'
        if role not in ROLES:continue
        bound=observation['checks'][check['id']]
        key=(role,check['question'],bound['source_evidence'],bound['edited_evidence'])
        if key in seen:continue
        seen.add(key)
        rows.append({'check_id':check['id'],'check_ref':check['check_ref'],'role':role,'expected_state':check['expected_state'],
            'goal':goal_caption(check['question']),
            'source_description':'An image. '+bound['source_evidence'].strip(),
            'edited_description':'An image. '+bound['edited_evidence'].strip()})
    return rows


def measure(source,edited,rows,text_vector):
    a,b=normalized(source),normalized(edited)
    if a.shape!=b.shape or a.shape!=(14,768):raise ValueError('Paired frozen14-view image vectors required')
    collected={r:{m:[] for m in METRICS} for r in ROLES};trace=[]
    difference=b[0]-a[0]
    for row in rows:
        q,s,e=(normalized(text_vector(row[n])) for n in ('goal','source_description','edited_description'))
        goal_source,goal_edited=float(a[0]@q),float(b[0]@q)
        patch_source,patch_edited=float(np.max(a@q)),float(np.max(b@q))
        td=e-s;denom=np.linalg.norm(td)*np.linalg.norm(difference)
        values={'goal_source':goal_source,'goal_edited':goal_edited,'goal_delta':goal_edited-goal_source,
            'goal_patch_source':patch_source,'goal_patch_edited':patch_edited,'goal_patch_delta':patch_edited-patch_source,
            'source_description_fit':float(a[0]@s),'edited_description_fit':float(b[0]@e),
            'edited_description_change_margin':float(b[0]@td),'source_description_change_margin':float(-a[0]@td),
            'description_change_alignment':float(difference@td/denom) if denom>1e-8 else 0.,'description_pair_similarity':float(s@e)}
        for name,value in values.items():collected[row['role']][name].append(value)
        trace.append({'check_id':row['check_id'],'check_ref':row['check_ref'],'role':row['role'],'measurements':values})
    output={}
    for role in ROLES:
        for name,values in collected[role].items():
            output[f'caption_{role}_{name}_min']=float(min(values)) if values else None
            output[f'caption_{role}_{name}_mean']=float(np.mean(values)) if values else None
    return output,trace
