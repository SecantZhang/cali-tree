"""Explicit object-region grading hypotheses with conservative abstention.

These are opinions from frozen detectors/encoders and pixel proxies, not
certificates of physical identity. Unknown binding never means goal failure.
"""
from dataclasses import dataclass,asdict
import math

import numpy as np

from ..decision.artifacts import digest


@dataclass(frozen=True)
class RegionProfile:
    binding: str='comparative'
    endpoint: str='substantial'

    def __post_init__(self):
        if self.binding not in ('comparative','strict') or self.endpoint not in ('comparative','substantial'):
            raise ValueError('Unknown physical rubric profile')


PROFILES=tuple(RegionProfile(b,e) for b in ('comparative','strict') for e in ('comparative','substantial'))


def proposal(program,record,semantic,profile=RegionProfile()):
    def result(label,reason,**extra):return {'prediction':label,'criterion':reason,'profile':asdict(profile),**extra}
    if record['program_ref']!=program['program_ref']:raise ValueError('Region/program mismatch')
    m=record['measurements']
    if len(program['requirements'])!=1 or len(record['trace'])!=1 or not m['region_all_plans_bound'] or not m['region_all_requirements_supported']:
        return result(-1,'unsupported_or_incomplete_scope')
    trace=record['trace'][0];plan=trace['plan']
    strict=profile.binding=='strict'
    required={'source_detection_score':.35 if strict else .2,'edited_detection_score':.3 if strict else .2,
              'source_binding_margin':.01 if strict else .005,'counterpart_margin':.01 if strict else .005,
              'counterpart_similarity':.8 if strict else .65}
    if any(m.get(k) is None or m[k]<threshold for k,threshold in required.items()):return result(-1,'uncertain_region_binding')
    large=profile.endpoint=='substantial';endpoint=progress=failure=False;cue=None
    if plan['kind']=='axis':
        before,after,delta=(m.get(k) for k in ('axis_source_margin','axis_edited_margin','axis_goal_delta'))
        if any(v is None for v in (before,after,delta)):return result(-1,'unavailable_reference_geometry')
        endpoint=after>(.04 if large else .015) and delta>.015
        progress=delta>.015
        failure=after<-.02 and delta<=.005
        cue='image_plane_relative_order'
    elif plan['kind']=='proximity':
        if trace['reference_source_box'] is None or trace['reference_edited_box'] is None:return result(-1,'unavailable_reference_geometry')
        a,b=np.asarray(trace['edited_box']),np.asarray(trace['reference_edited_box'])
        gap=np.linalg.norm(np.maximum(0,np.maximum(a[:2]-b[2:],b[:2]-a[2:])))
        extent=(np.linalg.norm(a[2:]-a[:2])+np.linalg.norm(b[2:]-b[:2]))/2
        delta=m.get('proximity_goal_delta')
        if delta is None:return result(-1,'unavailable_proximity')
        text=program['requirements'][0]['source_quote'].lower()
        relative=any(word in text for word in ('closer','nearer','farther','away from','further apart'))
        endpoint=delta>.02 and (relative or gap/max(extent,1e-9)<(.3 if large else .6))
        progress=delta>.01;failure=delta<-.02
        cue='image_plane_proximity'
    elif plan['kind']=='attribute':
        signals=[]
        if plan.get('size_goal') and m.get('size_goal_delta') is not None:
            delta=m['size_goal_delta'];signals.append((delta>(.2 if large else .1),delta>.02,delta<-.02,'requested_extent_change'))
        probes=plan.get('property_probes',[])
        if len(probes)>1:return result(-1,'multiple_property_goals_need_separate_witnesses')
        for p in probes:
            after,delta=m.get('property_edited_margin'),m.get('property_goal_delta')
            if p['family']=='color':
                value,change=m.get('color_edited_fraction'),m.get('color_goal_delta')
                if value is not None and change is not None:
                    signals.append((value>(.7 if large else .5) and change>.1,change>.05,
                                    value<.15 and change<=.02,'localized_requested_color'))
            elif p['family']=='finish':
                source,edited=m.get('finish_source_spots'),m.get('finish_edited_spots')
                if source is not None and edited is not None and after is not None and delta is not None:
                    if 'matte surface' in p['positive']:
                        pixel_end=source>.001 and edited<source*(.5 if large else .7) and after>=0
                        pixel_progress=source>.001 and edited<source*.85
                    else:
                        pixel_end=edited>.001 and edited>source*(2. if large else 1.5) and after>=0
                        pixel_progress=edited>source+.001
                    signals.append((pixel_end or (after>(.02 if large else .01) and delta>.005),
                                    pixel_progress or delta>.005,after<-.01 and delta<=0,'localized_finish_evidence'))
            elif after is not None and delta is not None:
                signals.append((after>(.03 if large else .015) and delta>.01,delta>.005,
                                after<-.02 and delta<=0,'localized_material_contrast'))
        if not signals:return result(-1,'unavailable_property_witness')
        endpoint=all(s[0] for s in signals);progress=any(s[1] for s in signals);failure=all(s[2] for s in signals)
        cue='+'.join(s[3] for s in signals)
    else:return result(-1,'unsupported_physical_goal')
    essential_loss=(semantic.get('meaning_retention_need_same_instance_essential_all',False) and
                    semantic.get('meaning_identity_evidence_replacement_or_loss_all',False) and
                    semantic.get('meaning_identity_materiality_material_shortfall_all',False))
    if essential_loss:return result(0,'essential_original_instance_lost',witness=cue)
    if endpoint:
        material=semantic.get('meaning_identity_materiality_material_shortfall_any',False) or semantic.get('meaning_collateral_materiality_material_unrequested_change_any',False)
        if material:return result(1,'goal_with_material_shortfall',witness=cue)
        accepted_identity=any(semantic.get('meaning_identity_materiality_'+state+'_all',False) for state in ('no_shortfall','immaterial_difference','not_relevant'))
        accepted_collateral=any(semantic.get('meaning_collateral_materiality_'+state+'_all',False) for state in ('none','minor_incidental'))
        if accepted_identity and accepted_collateral:return result(2,'qualified_requested_endpoint',witness=cue)
        return result(-1,'endpoint_with_unresolved_preservation',witness=cue)
    if progress:return result(1,'qualified_goal_directed_progress',witness=cue)
    if failure:return result(0,'qualified_goal_failure',witness=cue)
    return result(-1,'insufficient_directional_evidence',witness=cue)


CONTRACT_REF=digest({'version':'explicit-region-expert-v78','profiles':[asdict(p) for p in PROFILES],
 'criteria':'Qualified goal endpoint; explicit material shortfall; directed progress; known failure; otherwise abstain.',
 'limits':'Region bindings and image-plane/pixel proxies are model opinions; no grade from missing detections or uncertainty.'})
