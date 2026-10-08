"""DSG-style three-stage decomposition and original-rubric score readout.

Method: Cho et al., ICLR 2024, https://arxiv.org/abs/2310.18235.
Independent adaptation for source/edited pairs, unknowns and CaliTree labels.
"""
from copy import deepcopy
from pathlib import Path
import re

from .ablation import validate_shape
from .artifacts import digest, export_program
from .calls import CallFailure
from .compiler import object_schema, array, enum, TEXT, media_inputs
from .models import STATES

VERSION='dsg-score-fidelity-v1'
TEMPLATES=Path(__file__).parents[1]/'prompts/templates/dsg_fidelity_v1'
NODE=object_schema({'id':TEXT,'kind':enum(('entity','attribute','relation','global')),
    'terms':array(TEXT),'proposition':TEXT,'source_quote':TEXT,'role':enum(('support','requested')),'outcome_ids':array(TEXT)})
TUPLES=object_schema({'representable':{'type':'boolean'},'reason':TEXT,'nodes':array(NODE)})
QUESTIONS=object_schema({'questions':array(object_schema({'id':TEXT,'question':TEXT}))})
DEPENDENCIES=object_schema({'dependencies':array(object_schema({'id':TEXT,'parents':array(TEXT)})),'warnings':array(TEXT)})
AUDIT=object_schema({'accepted':{'type':'boolean'},'issues':array(TEXT)})
ANSWER=object_schema({'answer':enum(('yes','no','unknown')),'evidence':TEXT})
OUTCOME=object_schema({'status':enum(STATES),'evidence':TEXT})


def template(name):return (TEMPLATES/(name+'.txt')).read_text()


def validate_tuples(value, original):
    validate_shape(value,TUPLES)
    if not value['representable']:raise ValueError('Cannot represent within four tuples: '+value['reason'])
    nodes=value['nodes'];ids=[n['id'] for n in nodes]
    if not 1<=len(nodes)<=4 or len(ids)!=len(set(ids)) or any(not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,31}',i) for i in ids):
        raise ValueError('Expected one to four unique tuple IDs')
    outcomes={o.id for o in original.outcomes};covered=set();semantics=set()
    for node in nodes:
        if len(node['terms'])!={'entity':1,'global':1,'attribute':2,'relation':3}[node['kind']]:raise ValueError('Wrong tuple arity')
        semantic=(node['kind'],tuple(s.casefold().strip() for s in node['terms']))
        if semantic in semantics:raise ValueError('Duplicate semantic tuple')
        semantics.add(semantic)
        if node['source_quote'] not in original.instruction:raise ValueError('Unsupported instruction provenance')
        if len(set(node['outcome_ids']))!=len(node['outcome_ids']) or not set(node['outcome_ids'])<=outcomes:raise ValueError('Unknown or duplicate outcome mapping')
        if node['role']=='requested':
            if not node['outcome_ids']:raise ValueError('Requested tuple needs outcome mapping')
            covered.update(node['outcome_ids'])
    if covered!=outcomes:raise ValueError('Missing original outcome coverage')


def build_graph(original, tuples, questions, dependencies):
    validate_tuples(tuples,original);validate_shape(questions,QUESTIONS);validate_shape(dependencies,DEPENDENCIES)
    ids={n['id'] for n in tuples['nodes']}
    q={n['id']:n['question'] for n in questions['questions']};p={n['id']:n['parents'] for n in dependencies['dependencies']}
    if set(q)!=ids or len(q)!=len(questions['questions']) or set(p)!=ids or len(p)!=len(dependencies['dependencies']):
        raise ValueError('Questions and dependencies must cover every tuple exactly once')
    if len(set(s.casefold().strip() for s in q.values()))!=len(q):raise ValueError('Duplicate questions')
    for key,parents in p.items():
        if len(set(parents))!=len(parents) or not set(parents)<=ids or key in parents:raise ValueError('Broken graph references')
    seen=set();pending=set();ordered=[]
    def visit(key):
        if key in pending:raise ValueError('Cyclic dependencies')
        if key not in seen:
            pending.add(key)
            for parent in p[key]:visit(parent)
            pending.remove(key);seen.add(key);ordered.append(key)
    for node in tuples['nodes']:visit(node['id'])
    by_id={n['id']:n for n in tuples['nodes']}
    needed=set()
    def mark(key):
        if key not in needed:
            needed.add(key)
            for parent in p[key]:mark(parent)
    for node in tuples['nodes']:
        if node['role']=='requested':mark(node['id'])
    if needed!=ids:raise ValueError('Orphan supporting tuple')
    return {'version':VERSION,'original':export_program(original),
        'nodes':[{**deepcopy(by_id[key]),'question':q[key],'parents':p[key]} for key in ordered],
        'warnings':dependencies['warnings']}


def prepare(calls, original):
    """Text-only generation; model audit is diagnostic and never a score-based gate."""
    record={'status':'unresolved','graph':None,'audit':None}
    try:
        context={'original':original.to_dict(),'max_tuples':4}
        tuples,ref=calls.call('dsg_tuples',context,TUPLES,template=template('tuples'),slot='tuples',max_tokens=2048)
        record.update(tuples=tuples,tuples_ref=ref);validate_tuples(tuples,original)
        questions,ref=calls.call('dsg_questions',{'original':original.to_dict(),'tuples':tuples},QUESTIONS,
            template=template('questions'),slot='questions',max_tokens=2048)
        record.update(questions=questions,questions_ref=ref)
        dependencies,ref=calls.call('dsg_dependencies',{'original':original.to_dict(),'tuples':tuples},DEPENDENCIES,
            template=template('dependencies'),slot='dependencies',max_tokens=2048)
        record.update(dependencies=dependencies,dependencies_ref=ref)
        graph=build_graph(original,tuples,questions,dependencies)
        record.update(graph=graph,graph_ref=digest(graph),status='ready')
    except (CallFailure,ValueError,KeyError,TypeError) as exc:record['error']=str(exc)
    if record['status']=='ready':
        try:
            value,ref=calls.call('dsg_audit',{'graph':record['graph']},AUDIT,template=template('audit'),slot='audit',max_tokens=2048)
            validate_shape(value,AUDIT);record['audit']={**value,'execution_ref':ref}
        except (CallFailure,ValueError,KeyError,TypeError) as exc:record['audit_error']=str(exc)
    return record


def score_observations(graph, observations):
    by_id={r['id']:r for r in observations}
    values=[by_id[n['id']]['answer'] for n in graph['nodes']]
    requested=[by_id[n['id']]['answer'] for n in graph['nodes'] if n['role']=='requested']
    return {'dsg_score':None if 'unknown' in values else sum(s=='yes' for s in values)/len(values),
            'requested_fraction':None if 'unknown' in requested else sum(s=='yes' for s in requested)/len(requested)}


def readout_label(graph, observations, outcomes):
    by_id={r['id']:r for r in observations};states=[]
    for outcome in graph['original']['program']['outcomes']:
        if outcome['applicability']=='not_applicable':continue
        if outcome['applicability']!='applicable':return None
        if any(by_id[n['id']]['answer']=='unknown' for n in graph['nodes'] if n['role']=='requested' and outcome['id'] in n['outcome_ids']):return None
        status=outcomes[outcome['id']]['status']
        if status=='unknown':return None
        states.append(status)
    if not states:return None
    return 'yes' if all(s=='complete' for s in states) else 'no' if all(s=='absent' for s in states) else 'partial'


def execute(calls,graph,evidence,repeat):
    row={'graph_ref':digest(graph),'repeat':repeat,'observations':[],'outcomes':{},'label':None,'errors':[],'execution_refs':[]}
    observed={}
    for node in graph['nodes']:
        parents=[observed[key]['answer'] for key in node['parents']]
        obs={'id':node['id'],'answer':'unknown','evidence':'No valid observation','queried':False,'execution_ref':None}
        if 'no' in parents:obs.update(answer='no',evidence='False prerequisite: dependent question scored zero',masked='negative_parent')
        elif 'unknown' in parents:obs.update(masked='unknown_parent',evidence='Required prerequisite unresolved')
        else:
            obs['queried']=True
            try:
                value,ref=calls.call('dsg_vqa',{'instruction':graph['original']['program']['instruction'],'tuple':node},ANSWER,
                    template=template('vqa'),media=media_inputs(evidence),slot=f'{repeat}/{node["id"]}',final=True,max_tokens=1024)
                row['execution_refs'].append(ref);validate_shape(value,ANSWER);obs.update(value,execution_ref=ref)
            except (CallFailure,ValueError,KeyError,TypeError) as exc:row['errors'].append(str(exc))
        observed[node['id']]=obs;row['observations'].append(obs)
    row.update(score_observations(graph,row['observations']))
    schema=object_schema({'outcomes':object_schema({o['id']:OUTCOME for o in graph['original']['program']['outcomes']})})
    try:
        value,ref=calls.call('dsg_readout',{'graph':graph,'observations':row['observations']},schema,
            template=template('readout'),slot=str(repeat),final=True,max_tokens=1024)
        row['execution_refs'].append(ref);validate_shape(value,schema);row['outcomes']=value['outcomes']
    except (CallFailure,ValueError,KeyError,TypeError) as exc:row['errors'].append(str(exc))
    for outcome in graph['original']['program']['outcomes']:
        row['outcomes'].setdefault(outcome['id'],{'status':'unknown','evidence':'No valid readout'})
    row['label']=readout_label(graph,row['observations'],row['outcomes']);return row
