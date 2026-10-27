"""Input-bound region comparisons, not certified object identity or 3D facts."""
import re
import math

import numpy as np
from PIL import Image, ImageFilter

from .paired_features_v69 import COLORS, FINISHES, MATERIALS, query_plan, normalized, digest
from ..core.decision.bound_evidence_v2 import validate_program

VERSION='grounded-input-relative-regions-v77'
DETECTOR='IDEA-Research/grounding-dino-tiny'
DETECTOR_REVISION='a2bb814dd30d776dcf7e30523b00659f4f141c71'
AXES={'left':(-1.,0.),'right':(1.,0.),'above':(0.,-1.),'below':(0.,1.)}
BOUNDS={
 'source_detection_score':(.2,.3,.4,.5,.6,.7), 'edited_detection_score':(.2,.3,.4,.5,.6,.7),
 'source_binding_margin':(0.,.01,.02,.05,.1), 'counterpart_margin':(0.,.01,.02,.05,.1),
 'counterpart_similarity':(.5,.7,.8,.85,.9,.95),
 'size_goal_delta':(-.5,-.2,-.05,0.,.05,.2,.5),
 'axis_source_margin':(-.4,-.2,-.05,0.,.05,.2,.4),
 'axis_edited_margin':(-.4,-.2,-.05,0.,.05,.2,.4),
 'axis_goal_delta':(-.4,-.2,-.05,0.,.05,.2,.4),
 'proximity_goal_delta':(-.2,-.05,-.01,0.,.01,.05,.2),
 'property_source_margin':(-.1,-.05,-.02,0.,.02,.05,.1),
 'property_edited_margin':(-.1,-.05,-.02,0.,.02,.05,.1),
 'property_goal_delta':(-.1,-.05,-.02,0.,.02,.05,.1),
 'color_source_fraction':(.1,.25,.5,.75,.9), 'color_edited_fraction':(.1,.25,.5,.75,.9),
 'color_goal_delta':(-.5,-.2,-.05,0.,.05,.2,.5),
 'finish_source_spots':(.001,.005,.01,.02,.05), 'finish_edited_spots':(.001,.005,.01,.02,.05),
 'finish_goal_delta':(-.05,-.01,-.005,0.,.005,.01,.05),
}
SPECS={'region_available':'At least one target-region comparison is available; detector outputs are model hypotheses, not certified identities.',
       'region_all_plans_bound':'Every prepared region plan has a source/edited candidate binding; this does not certify factual identity.',
       'region_all_requirements_supported':'Every requested requirement has a supported, bound region plan; unsupported requirements cannot be silently treated as fulfilled.'}
for metric,thresholds in BOUNDS.items():
    SPECS['region_'+metric+'_available']='A finite input-bound '+metric.replace('_',' ')+' measurement is available.'
    for value in thresholds:
        SPECS['region_'+metric+'_ge_'+str(value)]='The input-bound '+metric.replace('_',' ')+' measurement is at least '+str(value)+'. Neural bindings and image-plane geometry are not factual or 3D guarantees.'


def target_phrase(text,neutral=False):
    text=text.lower().replace('grey','gray').replace('’',"'")
    text=re.sub(r"'s\s+(?:surface\s+finish|finish|colou?r|size|height|width|appearance|position|body\s+size|fat\s+distribution).*$",'',text)
    text=re.sub(r'^\s*(?:the\s+)?(?:colou?r|surface\s+finish|finish|size|height|width|position|appearance)\s+of\s+','',text)
    text=re.split(r'\b(?:that\s+is|which\s+is|behind|in\s+front\s+of|to\s+the\s+(?:left|right)\s+of|above|below)\b',text,maxsplit=1)[0]
    text=re.sub(r'\b(?:the|an?|original|source|existing|originally)\b',' ',text)
    if neutral:
        words=COLORS+FINISHES+MATERIALS+('small','smaller','large','larger','tiny','big','bright','dark','shiny','metal','lime')
        text=re.sub(r'\b(?:'+'|'.join(words)+r')\b',' ',text)
    text=re.sub(r'\s+',' ',text).strip(' .,;:-')
    return text+'.' if text and len(text)<140 else None


def size_goal(text):
    text=text.lower()
    negative=bool(re.search(r'\b(?:smaller|shrink|shorter|narrower)\b|\b(?:reduce|decrease)\b.*\b(?:size|height|width|length)\b',text))
    positive=bool(re.search(r'\b(?:larger|bigger|enlarge|taller|longer|wider)\b|\bincrease\b.*\b(?:size|height|width|length)\b',text))
    if negative==positive:return None
    dimension='height' if re.search(r'\b(?:taller|shorter|height)\b',text) else 'width' if re.search(r'\b(?:wider|narrower|width)\b',text) else 'area'
    return {'sign':-1. if negative else 1.,'dimension':dimension}


def plans(program):
    validate_program(program)
    result=[]
    for requirement in program['requirements']:
        outcomes=[c for c in program['checks'] if c['role']=='outcome' and requirement['id'] in c['requirement_ids']]
        attribute=next((c for c in outcomes if c['kind']=='attribute'),None)
        if attribute:
            specific,neutral=target_phrase(attribute['target']),target_phrase(attribute['target'],True)
            sub={'checks':[{**attribute,'target':neutral or attribute['target']}],
                 'contract':{'authorized_changes':[requirement['source_quote']]},'instruction':requirement['source_quote']}
            probes=query_plan(sub)['probes'];extent=size_goal(requirement['source_quote'])
            if specific and neutral and (probes or extent):
                result.append({'requirement_id':requirement['id'],'kind':'attribute','source_query':specific,
                    'edited_query':neutral,'target_text':'A photo of '+specific,'match':'position',
                    'size_goal':extent,'property_probes':probes})
        for c in outcomes:
            if c['kind']!='spatial_relation':continue
            text=requirement['source_quote'].lower()
            if re.search(r"\b(?:not|never|avoid|don't)\b",text):continue
            text=re.split(r'\b(?:while|without|rather than)\b',text,maxsplit=1)[0]
            generic=bool(re.search(r'\b(?:position|location|image|scene|instruction|request|camera|viewer)\b',c['reference']) or re.match(r'\s*(?:its|their)\b',c['reference'],re.I))
            patterns={'left':r'\bleft(?:\s+side)?\s+of\b','right':r'\bright(?:\s+side)?\s+of\b',
                      'above':r'\babove\b','below':r'\b(?:below|under|beneath)\b'}
            directions=[key for key,p in patterns.items() if re.search(p,text)]
            source,reference=target_phrase(c['target']),target_phrase(c['reference'])
            if not source or not reference or generic:continue
            if len(directions)==1:
                result.append({'requirement_id':requirement['id'],'kind':'axis','axis':directions[0],
                    'source_query':source,'edited_query':source,'reference_query':reference,
                    'target_text':'A photo of '+source,'reference_text':'A photo of '+reference,'match':'appearance'})
            elif re.search(r'\b(?:closer|nearer|next to|near|beside)\b',text):
                result.append({'requirement_id':requirement['id'],'kind':'proximity','sign':1.,
                    'source_query':source,'edited_query':source,'reference_query':reference,
                    'target_text':'A photo of '+source,'reference_text':'A photo of '+reference,'match':'appearance'})
            elif re.search(r'\b(?:farther|further apart|away from)\b',text):
                result.append({'requirement_id':requirement['id'],'kind':'proximity','sign':-1.,
                    'source_query':source,'edited_query':source,'reference_query':reference,
                    'target_text':'A photo of '+source,'reference_text':'A photo of '+reference,'match':'appearance'})
    return list({digest(p):p for p in result}.values())


def relative_box(box,size):
    w,h=size
    a=np.asarray(box,dtype=np.float64)/np.asarray([w,h,w,h])
    if a.shape!=(4,) or np.any(~np.isfinite(a)) or a[2]<=a[0] or a[3]<=a[1]:raise ValueError('Finite nonempty region required')
    return a


def center(box):return (np.asarray(box[:2])+np.asarray(box[2:]))/2


def geometry(source,edited,goal,reference_source=None,reference_edited=None):
    values={}
    if goal['kind']=='attribute' and goal.get('size_goal'):
        def extent(b):
            width,height=b[2]-b[0],b[3]-b[1]
            return height if goal['size_goal']['dimension']=='height' else width if goal['size_goal']['dimension']=='width' else width*height
        values['size_goal_delta']=float(goal['size_goal']['sign']*(extent(edited)/extent(source)-1.))
    if reference_source is not None and reference_edited is not None:
        a=center(source)-center(reference_source);b=center(edited)-center(reference_edited)
        if goal['kind']=='axis':
            before,after=float(a@AXES[goal['axis']]),float(b@AXES[goal['axis']])
            values.update(axis_source_margin=before,axis_edited_margin=after,axis_goal_delta=after-before)
        elif goal['kind']=='proximity':
            values['proximity_goal_delta']=float(goal['sign']*(np.linalg.norm(a)-np.linalg.norm(b)))
    return values


def color_fraction(image,color):
    a=np.asarray(image.convert('RGB').resize((128,128)),dtype=np.float64)/255.
    maximum=a.max(axis=2);minimum=a.min(axis=2);delta=maximum-minimum
    saturation=delta/np.maximum(maximum,1e-9);hue=np.zeros_like(maximum);nz=delta>1e-9
    for i in range(3):
        selected=nz&(a.argmax(axis=2)==i)
        other=((a[:,:,1]-a[:,:,2])/np.maximum(delta,1e-9))%6 if i==0 else ((a[:,:,2]-a[:,:,0])/np.maximum(delta,1e-9)+2) if i==1 else ((a[:,:,0]-a[:,:,1])/np.maximum(delta,1e-9)+4)
        hue[selected]=other[selected]/6
    y,x=np.mgrid[0:128,0:128];mask=((x-63.5)/51.2)**2+((y-63.5)/51.2)**2<=1
    if color=='black':match=maximum<.25
    elif color=='white':match=(maximum>.75)&(saturation<.25)
    elif color=='gray':match=(saturation<.25)&(maximum>=.2)&(maximum<=.85)
    elif color=='brown':match=(hue>=.035)&(hue<=.16)&(saturation>.25)&(maximum<.72)&(maximum>.12)
    elif color=='orange':match=(hue>=.035)&(hue<=.13)&(saturation>.4)&(maximum>=.6)
    else:
        ranges={'red':(-.05,.055),'yellow':(.12,.2),'green':(.2,.49),'blue':(.52,.73),'purple':(.73,.95)}
        if color not in ranges:return None
        lo,hi=ranges[color];match=((hue>=lo)&(hue<=hi) if lo>=0 else (hue<=hi)|(hue>=1+lo))&(saturation>.25)
    return float(np.mean(match[mask]))


def bright_spots(image):
    image=image.convert('RGB').resize((128,128));a=np.asarray(image,dtype=np.float64)/255.
    smooth=np.asarray(image.filter(ImageFilter.GaussianBlur(4)),dtype=np.float64)/255.
    maximum=a.max(axis=2);contrast=maximum-smooth.max(axis=2)
    y,x=np.mgrid[0:128,0:128];mask=((x-63.5)/51.2)**2+((y-63.5)/51.2)**2<=1
    return float(np.mean(((maximum>.75)&(contrast>.08))[mask]))


def predicates(measurements):
    if measurements is None:return dict.fromkeys(SPECS,False)
    output={key:bool(measurements.get(key)) for key in ('region_available','region_all_plans_bound','region_all_requirements_supported')}
    for name,thresholds in BOUNDS.items():
        value=measurements.get(name)
        if value is not None and (type(value) not in (int,float) or not math.isfinite(value)):
            raise ValueError('Region measurements must be finite or unavailable')
        output['region_'+name+'_available']=value is not None
        for threshold in thresholds:output['region_'+name+'_ge_'+str(threshold)]=value is not None and value>=threshold
    return output


CONTRACT_REF=digest({'version':VERSION,'detector':DETECTOR,'detector_revision':DETECTOR_REVISION,'bounds':BOUNDS,
 'geometry':'Only normalized input-relative extent changes, target/reference margins and directed progress; never raw coordinates as predictors.',
 'properties':'Localized frozen-encoder contrasts and fixed central-ellipse color/bright-spot proxies; no property-value identity flags.',
 'availability':'Absent/ambiguous detections are unavailable model evidence, never proof of physical absence.',
 'specs':SPECS})
