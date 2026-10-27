"""A fixed semantic concept vocabulary for reading existing judge explanations.

Entailment here is a language-model opinion about a textual claim. It does not
verify the images, establish human-grade correctness, or resolve missing facts.
"""
import re

import numpy as np

from .artifacts import digest
from .bound_evidence_v2 import validate_program,validate_observation

VERSION='local-nli-rubric-concepts-v81'
MODEL='cross-encoder/nli-deberta-v3-small'
REVISION='fa2804872c3b4bd748f38c0185cc85775361e735'
HYPOTHESES={
 'complete_endpoint':'The requested change was fully completed.',
 'partial_endpoint':'The requested change was only partially completed.',
 'no_goal_progress':'No visible progress was made toward the requested change.',
 'useful_progress':'There is visible progress toward the requested change.',
 'wrong_target':'The wrong object was edited.',
 'target_retained':'The identity of the original target was preserved.',
 'target_replaced':'The original target was replaced or lost.',
 'authorized_difference':'The appearance differences are allowed by the requested transformation.',
 'material_collateral':'Unrelated objects or the background changed materially.',
 'minor_collateral':'Other differences are minor and incidental.',
 'uncertain_endpoint':'Whether the requested endpoint was reached is uncertain.',
 'action_without_outcome':'The requested action is suggested, but its visible physical outcome is absent.',
 'unchanged_configuration':'The original physical configuration is unchanged.',
 'some_required_targets':'The edit affected some, but not all, required targets.',
 'insufficient_visibility':'The requested target is not visible enough to judge.',
 'severe_artifacts':'The edited image has severe visual artifacts.'}
LABELS=('contradiction','entailment','neutral')
CONTEXTS=('regular','observation')
NAMES=tuple(f'nli_{context}_{concept}_{label}' for context in CONTEXTS for concept in HYPOTHESES for label in LABELS)
DESCRIPTIONS={f'nli_{context}_{concept}_{label}':f'The local NLI reader assigns {label} support to this {context} text claim: {statement} This is not image-truth confidence.'
 for context in CONTEXTS for concept,statement in HYPOTHESES.items() for label in LABELS}
CONTRACT_REF=digest({'version':VERSION,'model':MODEL,'revision':REVISION,'hypotheses':HYPOTHESES,'contexts':CONTEXTS,
 'labels':LABELS,'max_tokens':384,'truncation':'longest_first','premise':'Instruction plus existing regular rationale, or distinct bound source/edited visible descriptions. No reference grade, interpreter state, case/source/editor identity.',
 'limit':'NLI concerns language claims and can share extraction errors. Never substitute entailment support for a physical grading warrant.'})


def plans(program,observation,pair_ref,judgment):
    validate_program(program);contexts={}
    instruction='Requested edit: '+program['instruction']+'\n'
    if judgment is not None:
        rationale=judgment.get('rationale')
        if not isinstance(rationale,str) or not rationale.strip():raise ValueError('Valid regular rationale required')
        # Explicit grade tokens add no new meaning beyond the separate judge
        # label. Keep their explanation, including uncertainty and negation.
        rationale=re.sub(r'^\s*(?:yes|no|partial(?:ly)?)(?:\s*[:;,.-]\s*|\s*\n)','',rationale,flags=re.I)
        contexts['regular']=instruction+'Visible-change explanation: '+rationale.strip()
    if observation is not None:
        validate_observation(program,observation,pair_ref)
        sources=[];edits=[]
        for check in program['checks']:
            row=observation['checks'][check['id']]
            for dest,key in ((sources,'source_evidence'),(edits,'edited_evidence')):
                value=row[key].strip()
                if value and value not in dest:dest.append(value)
        # Fixed symmetric text budgets; no check state or grading words added.
        source=' '.join(' '.join(sources).split()[:125]);edited=' '.join(' '.join(edits).split()[:125])
        contexts['observation']=instruction+'Source image: '+source+'\nEdited image: '+edited
    return [{'context':context,'concept':concept,'premise':premise,'hypothesis':hypothesis}
            for context,premise in contexts.items() for concept,hypothesis in HYPOTHESES.items()]


def features(rows):
    output={n:None for n in NAMES}
    for row in rows:
        if row['context'] not in CONTEXTS or row['concept'] not in HYPOTHESES:raise ValueError('Unknown semantic concept')
        support=np.asarray(row['support'],dtype=float)
        if support.shape!=(3,) or not np.all(np.isfinite(support)) or np.any(support<0) or abs(support.sum()-1)>1e-5:raise ValueError('Normalized finite three-way language supports required')
        for label,value in zip(LABELS,support):
            name=f"nli_{row['context']}_{row['concept']}_{label}"
            if output[name] is not None:raise ValueError('Duplicate semantic concept')
            output[name]=float(value)
    return output
