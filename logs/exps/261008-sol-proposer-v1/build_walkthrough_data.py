"""Saved-data-only payload for the case/round/check walkthrough."""
import base64
from collections import Counter
from io import BytesIO
import json
from pathlib import Path

from PIL import Image

SOURCE=Path(__file__).resolve().parent
DESTINATION=Path('/Users/zzhang/.codex/visualizations/2026/10/06/01a11245-a1f4-7cb0-be00-f8687489a6d0')


def programme(value):
    p=value.get('program',value)
    return {'ref':value.get('program_ref',''), 'nodes':p['nodes']}


def report(value):
    if not value:return None
    result={k:value[k] for k in ('draws','agreement','coverage','label_distribution','confidence_pass','nodes','requirement_consistency','mean_checks','mean_completion_tokens') if k in value}
    result['traces']=[]
    for t in value.get('traces',[]):
        result['traces'].append({'label':t['label'],'resolved':t['resolved'],
            'observations':[{k:o[k] for k in ('check_id','status','evidence','valid','eligible','queried','confidence','failure') if k in o}
                            for o in t['observations']]})
    return result


def thumb(path):
    with Image.open(path) as original:
        im=original.convert('RGB');im.thumbnail((256,256));output=BytesIO();im.save(output,format='JPEG',quality=68)
    return 'data:image/jpeg;base64,'+base64.b64encode(output.getvalue()).decode()


def main():
    m=json.loads((SOURCE/'manifest.json').read_text());results=json.loads((SOURCE/'results.json').read_text())
    d={'experiment':SOURCE.name,'model_roles':{'luna-proposer':'Luna','sol-proposer':'Sol 6.1'},
        'judge':'Luna','policy':m['policy'],'cases':[]}
    for i,c in enumerate(m['cases']):
        row={'id':c['id'],'name':['Jacket','Paper in cup','Frog in toilet'][i], 'instruction':c['instruction'],
            'reference':c['target'],'rubric':c['rubric'],'images':{k:thumb(v) for k,v in c['evidence'].items()},
            'seed':programme(c['seed']),'audit':json.loads((SOURCE/'prepared'/f'{i}.json').read_text())['seed_audit'],'runs':{}}
        for arm in m['arms']:
            s=next(iter(json.loads((SOURCE/'frozen'/arm/f'{i}.json').read_text())['nodes'].values()))['result']
            events=s['lineage'][-1]['events'];stats=s['lineage'][-1]['search_schedule']
            programmes={ref:programme(v) for ref,v in s['candidates'].items()}
            evaluations={ref:{k:report(v.get(k)) for k in ('screen','confirmation','diagnostic')} for ref,v in s['candidates'].items()}
            rounds=[]
            for number in range(stats['rounds_started']):
                parent_event=next(e for e in events if e.get('round')==number and 'parents' in e)
                details=next((e for e in events if e.get('round')==number and 'gradients' in e),{})
                tx=[]
                for h in s['lineage'][:-1]:
                    if h.get('round')==number:
                        tx.append({k:h[k] for k in ('transaction','program_ref','audit','error','duplicate','structural_valid','validation') if k in h})
                gradients={key:[{'text':text[:2400],'excerpt':len(text)>2400} for text in texts]
                           for key,texts in details.get('gradients',{}).items()}
                rounds.append({'number':number+1,'parent':parent_event['parents'][0], 'transactions':tx,
                    'gradients':gradients,'discovery':details.get('visual_discovery'),
                    'gradient_failure':details.get('gradient_failure'),
                    'complete':number<stats['rounds_completed']})
            selected=s['selected']['program_ref'];candidate=s['candidates'][selected]
            counts=Counter()
            for h in s['lineage'][:-1]:
                counts['proposed']+=1
                if h.get('error'):counts['rejected_format_or_call']+=1
                elif h.get('audit',{}).get('accepted'):counts['accepted']+=1
                elif h.get('audit',{}).get('accepted') is False:counts['rejected_review']+=1
            final=results['cases'][c['id']][arm]
            row['runs'][arm]={'programmes':programmes,'evaluations':evaluations,'rounds':rounds,'counts':dict(counts),
                'selected':selected,'selected_audit':candidate.get('audit'),'confirmation':report(candidate.get('confirmation')),
                'stop':s['stop_reason'],'status':final['support_status'],'acceptance':final['acceptance'],
                'final':{k:report(final['final'][k]) for k in ('seed','selected')},'usage':final.get('usage'),
                'confirmation_acceptance':candidate.get('acceptance')}
        d['cases'].append(row)
    text=json.dumps(d,separators=(',',':'),ensure_ascii=False)
    (DESTINATION/'calitree-sol-leaf-walkthrough-data.json').write_text(text)
    print(json.dumps({'bytes':len(text.encode()),'cases':len(d['cases']),'rounds':sum(len(r['rounds']) for c in d['cases'] for r in c['runs'].values())}))


if __name__=='__main__':main()
