"""Prepare/extract label-free object-region evidence from cached local models."""
import argparse
from collections import Counter
import json
from pathlib import Path
import time

import numpy as np
from PIL import Image

from critical.vision import grounded_regions_v77 as regions
from critical.vision.paired_features_v69 import digest,normalized

ROOT=Path(__file__).resolve().parents[1]
VISION=ROOT/'logs/exps/261021-paired-vision-v63'


def read(path):return json.loads(Path(path).read_text())


def save(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n');temporary.replace(path)


def sha(path):
    import hashlib
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(8*1024*1024),b''):h.update(block)
    return h.hexdigest()


def prepare(out):
    if out.exists():raise ValueError('Fresh region experiment directory required')
    entries=[];queries=set();counts=Counter();hashes=read(VISION/'manifest.json')['image_hashes']
    for row in read(VISION/'inputs_without_labels.json'):
        assert not {'reference','human_score','regular'}&set(row)
        plan=regions.plans(row['program'])
        entries.append({k:row[k] for k in ('case','source_group','program','evidence')}|{'region_plans':plan})
        for p in plan:
            counts[p['kind']]+=1
            queries.add((hashes[row['evidence']['source_image']],p['source_query']))
            queries.add((hashes[row['evidence']['edited_image']],p['edited_query']))
            if 'reference_query' in p:
                for path in row['evidence'].values():queries.add((hashes[path],p['reference_query']))
    out.mkdir(parents=True)
    protocol={'version':regions.VERSION,'feature_contract_ref':regions.CONTRACT_REF,'cases':len(entries),
        'eligible_cases':sum(bool(e['region_plans']) for e in entries),'plans_by_kind':dict(counts),'unique_detector_queries':len(queries),
        'detector':regions.DETECTOR,'detector_revision':regions.DETECTOR_REVISION,'threshold':.15,'text_threshold':.2,'max_candidates':6,
        'source_binding':'Frozen crop/text affinity plus0.05 times detector support; no labels. Attribute counterparts emphasize normalized position, spatial counterparts emphasize appearance.',
        'coordinate_policy':'Only input-relative goal geometry reaches grade learners; raw boxes are diagnostic metadata.',
        'missing':'Unavailable/ambiguous candidate evidence never proves physical absence. Unsupported tasks retain existing policy.',
        'new_api_calls':0,'image_uploads':0,'reserved_sources_used':0,'model_downloads':0}
    save(out/'protocol.json',protocol);save(out/'inputs_without_labels.json',entries)
    code=[Path(__file__),Path(regions.__file__)]
    save(out/'manifest.json',{'protocol_ref':digest(protocol),'inputs_ref':digest(entries),'image_hashes':hashes,
                             'code_sha256':{str(p):sha(p) for p in code}})
    for p in code:
        target=out/'source_snapshot'/p.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(p.read_bytes())
    (out/'run.log').write_text('Prepared label-free local grounded-region comparisons. No paid calls or reserved sources.\n')
    (out/'llm-histories.log').write_text('Zero API calls; cached local GroundingDINO/SigLIP2 only.\n')
    print(protocol,flush=True)


def extract(out):
    import torch
    import transformers
    from transformers import AutoProcessor,AutoModelForZeroShotObjectDetection
    from critical.vision.paired_encoder_v69 import PairedVisionEncoder
    protocol,manifest=read(out/'protocol.json'),read(out/'manifest.json')
    assert digest(protocol)==manifest['protocol_ref'] and digest(read(out/'inputs_without_labels.json'))==manifest['inputs_ref']
    for p,h in manifest['code_sha256'].items():assert sha(p)==h,p
    assert protocol['feature_contract_ref']==regions.CONTRACT_REF and torch.backends.mps.is_available()
    detector_identity=read('/tmp/calitree-vision-v63/detector_identity.json');detector_path=Path(detector_identity['snapshot_path'])
    assert detector_path.name==regions.DETECTOR_REVISION
    detector_files={p.name:sha(p) for p in detector_path.iterdir() if p.is_file()}
    encoder_identity=read(VISION/'encoder_identity.json')
    encoder_path=Path(read('/tmp/calitree-vision-v63/model_identity.json')['snapshot_path'])
    identity={'detector':regions.DETECTOR,'detector_revision':regions.DETECTOR_REVISION,'detector_files':detector_files,
              'encoder':encoder_identity,'backend':'mps','dtype':'float32','contract_ref':regions.CONTRACT_REF,
              'code_sha256':manifest['code_sha256']}
    if (out/'identity.json').exists():assert read(out/'identity.json')==identity
    else:save(out/'identity.json',identity)
    reference=digest(identity);torch.set_num_threads(2)
    detector_ref=digest({'model':regions.DETECTOR,'revision':regions.DETECTOR_REVISION,'files':detector_files,
        'backend':'mps','torch':torch.__version__,'transformers':transformers.__version__,
        'threshold':protocol['threshold'],'text_threshold':protocol['text_threshold'],
        'max_candidates':protocol['max_candidates'],'nms_iou':.8,'filter':'min2px-area0.0001-to0.95-v1'})
    encoder_ref=digest(encoder_identity)
    detector=AutoModelForZeroShotObjectDetection.from_pretrained(str(detector_path),local_files_only=True,use_safetensors=True).to('mps').eval()
    detector.config.disable_custom_kernels=True
    processor=AutoProcessor.from_pretrained(str(detector_path),local_files_only=True)
    encoder=PairedVisionEncoder(encoder_path,encoder_identity)
    cache=ROOT/'logs/cache/grounded-regions-v77';verified=set();started=time.monotonic();inferences=0
    def verify_image(path):
        h=manifest['image_hashes'][path]
        if path not in verified:
            assert sha(path)==h,path;verified.add(path)
        return h
    def detection(path,query):
        nonlocal inferences
        h=verify_image(path);key=digest([detector_ref,h,query]);file=cache/'detections'/(key+'.json')
        if file.exists():return read(file)
        with Image.open(path) as source:image=source.convert('RGB')
        batch=processor(images=image,text=query,return_tensors='pt');batch={k:v.to('mps') for k,v in batch.items()}
        outputs=detector(**batch)
        found=processor.post_process_grounded_object_detection(outputs,batch['input_ids'],threshold=protocol['threshold'],
                    text_threshold=protocol['text_threshold'],target_sizes=[(image.height,image.width)])[0]
        boxes=found['boxes'].cpu().tolist();scores=found['scores'].cpu().tolist()
        ordered=sorted(range(len(scores)),key=lambda i:(-scores[i],boxes[i]))
        kept=[]
        for i in ordered:
            box=np.asarray(boxes[i]);box[[0,2]]=np.clip(box[[0,2]],0,image.width);box[[1,3]]=np.clip(box[[1,3]],0,image.height)
            if box[2]-box[0]<2 or box[3]-box[1]<2:continue
            area=(box[2]-box[0])*(box[3]-box[1])/(image.width*image.height)
            if not .0001<=area<=.95:continue
            duplicate=False
            for j in kept:
                other=np.asarray(j['box']);intersection=np.prod(np.maximum(0,np.minimum(box[2:],other[2:])-np.maximum(box[:2],other[:2])))
                union=np.prod(box[2:]-box[:2])+np.prod(other[2:]-other[:2])-intersection
                if intersection/max(union,1e-9)>.8:duplicate=True;break
            if not duplicate:kept.append({'box':box.tolist(),'score':float(scores[i]),'phrase':found['text_labels'][i]})
            if len(kept)==protocol['max_candidates']:break
        result={'image_sha256':h,'query':query,'size':[image.width,image.height],'candidates':kept}
        save(file,result);inferences+=1
        return result
    def cropped(path,candidate):
        with Image.open(path) as image:
            w,h=image.size;x0,y0,x1,y1=candidate['box']
            return image.convert('RGB').crop((max(0,int(x0)),max(0,int(y0)),min(w,int(np.ceil(x1))),min(h,int(np.ceil(y1)))))
    def vectors(path,record):
        if not record['candidates']:return None
        key=digest([encoder_ref,record['image_sha256'],[c['box'] for c in record['candidates']],'floor-ceil-bbox-rgb-v1'])
        file=cache/'crop_vectors'/(key+'.npy')
        if file.exists():return np.load(file,allow_pickle=False)
        crops=[cropped(path,c) for c in record['candidates']]
        pixels=encoder.processor.image_processor(images=crops,return_tensors='pt')['pixel_values'].to('mps')
        v=normalized(encoder.model.get_image_features(pixel_values=pixels).cpu().float().numpy()).astype(np.float32)
        file.parent.mkdir(parents=True,exist_ok=True);temporary=file.with_suffix('.tmp')
        with temporary.open('wb') as handle:np.save(handle,v,allow_pickle=False)
        temporary.replace(file);return v
    def choose_source(record,v,text,excluded=None):
        if v is None:return None
        affinity=v@encoder._text(text);ranking=affinity+.05*np.asarray([c['score'] for c in record['candidates']])
        if excluded is not None:
            for i,c in enumerate(record['candidates']):
                b=regions.relative_box(c['box'],record['size']);inter=np.prod(np.maximum(0,np.minimum(b[2:],excluded[2:])-np.maximum(b[:2],excluded[:2])))
                if inter/max(np.prod(b[2:]-b[:2])+np.prod(excluded[2:]-excluded[:2])-inter,1e-9)>.5:ranking[i]=-10
        order=np.argsort(ranking)[::-1]
        if ranking[order[0]]<-1:return None
        index=int(order[0]);margin=float(ranking[order[0]]-ranking[order[1]]) if len(order)>1 else 1.
        return index,margin
    def choose_edit(record,v,source_box,source_vector,mode,excluded=None):
        if v is None:return None
        similarity=v@source_vector
        positions=np.asarray([regions.center(regions.relative_box(c['box'],record['size'])) for c in record['candidates']])
        ranking=similarity if mode=='appearance' else -.0-np.linalg.norm(positions-regions.center(source_box),axis=1)+.2*similarity
        ranking=ranking+.02*np.asarray([c['score'] for c in record['candidates']])
        if excluded is not None:
            for i,c in enumerate(record['candidates']):
                b=regions.relative_box(c['box'],record['size']);inter=np.prod(np.maximum(0,np.minimum(b[2:],excluded[2:])-np.maximum(b[:2],excluded[:2])))
                if inter/max(np.prod(b[2:]-b[:2])+np.prod(excluded[2:]-excluded[:2])-inter,1e-9)>.5:ranking[i]=-10
        order=np.argsort(ranking)[::-1]
        if ranking[order[0]]<-1:return None
        return int(order[0]),float(ranking[order[0]]-ranking[order[1]]) if len(order)>1 else 1.
    entries=read(out/'inputs_without_labels.json');completed=0
    with torch.inference_mode():
        for entry in entries:
            if (out/'stop.flag').exists():
                save(out/'progress.json',{'completed_cases':completed,'total_cases':len(entries),'status':'stopped_by_flag'});return
            file=out/'cases'/(entry['case']+'.json')
            if file.exists():
                assert read(file)['identity_ref']==reference;completed+=1;continue
            values={name:[] for name in regions.BOUNDS};traces=[]
            paths=entry['evidence']
            for plan in entry['region_plans']:
                source=detection(paths['source_image'],plan['source_query']);edited=detection(paths['edited_image'],plan['edited_query'])
                a,b=vectors(paths['source_image'],source),vectors(paths['edited_image'],edited)
                left=choose_source(source,a,plan['target_text'])
                if left is None:continue
                li,gap=left;sb=regions.relative_box(source['candidates'][li]['box'],source['size'])
                right=choose_edit(edited,b,sb,a[li],plan['match'])
                if right is None:continue
                ri,match_gap=right;eb=regions.relative_box(edited['candidates'][ri]['box'],edited['size'])
                measured={'source_detection_score':source['candidates'][li]['score'],'edited_detection_score':edited['candidates'][ri]['score'],
                    'source_binding_margin':gap,'counterpart_margin':match_gap,'counterpart_similarity':float(a[li]@b[ri])}
                reference_source=reference_edited=None
                source_ref_gap=edited_ref_gap=None
                if 'reference_query' in plan:
                    rs=detection(paths['source_image'],plan['reference_query']);re=detection(paths['edited_image'],plan['reference_query'])
                    rv,tv=vectors(paths['source_image'],rs),vectors(paths['edited_image'],re)
                    ref=choose_source(rs,rv,plan['reference_text'],sb)
                    if ref is not None:
                        si,source_ref_gap=ref;reference_source=regions.relative_box(rs['candidates'][si]['box'],rs['size'])
                        ref_edit=choose_edit(re,tv,reference_source,rv[si],'appearance',eb)
                        if ref_edit is not None:
                            rj,edited_ref_gap=ref_edit;reference_edited=regions.relative_box(re['candidates'][rj]['box'],re['size'])
                            measured['source_detection_score']=min(measured['source_detection_score'],rs['candidates'][si]['score'])
                            measured['edited_detection_score']=min(measured['edited_detection_score'],re['candidates'][rj]['score'])
                            measured['source_binding_margin']=min(measured['source_binding_margin'],source_ref_gap)
                            measured['counterpart_margin']=min(measured['counterpart_margin'],edited_ref_gap)
                            measured['counterpart_similarity']=min(measured['counterpart_similarity'],float(rv[si]@tv[rj]))
                    if reference_source is None or reference_edited is None:continue
                measured.update(regions.geometry(sb,eb,plan,reference_source,reference_edited))
                source_crop=edited_crop=None
                for probe in plan.get('property_probes',[]):
                    positive=encoder._text(probe['positive']);negative=np.stack([encoder._text(t) for t in probe['negative']])
                    before=float(a[li]@positive-np.max(negative@a[li]));after=float(b[ri]@positive-np.max(negative@b[ri]))
                    for key,v in [('property_source_margin',before),('property_edited_margin',after),('property_goal_delta',after-before)]:
                        measured[key]=min(measured.get(key,v),v)
                    if source_crop is None:source_crop=cropped(paths['source_image'],source['candidates'][li]);edited_crop=cropped(paths['edited_image'],edited['candidates'][ri])
                    if probe['family']=='color':
                        color=probe['positive'].split('A photo of a ',1)[-1].split()[0]
                        before,after=regions.color_fraction(source_crop,color),regions.color_fraction(edited_crop,color)
                        if before is not None and after is not None:measured.update(color_source_fraction=before,color_edited_fraction=after,color_goal_delta=after-before)
                    if probe['family']=='finish':
                        before,after=regions.bright_spots(source_crop),regions.bright_spots(edited_crop)
                        sign=-1. if 'matte surface' in probe['positive'] else 1.
                        measured.update(finish_source_spots=before,finish_edited_spots=after,finish_goal_delta=sign*(after-before))
                for key,value in measured.items():values[key].append(float(value))
                traces.append({'plan':plan,'source_box':sb.tolist(),'edited_box':eb.tolist(),'measurements':measured,
                               'reference_source_box':reference_source.tolist() if reference_source is not None else None,
                               'reference_edited_box':reference_edited.tolist() if reference_edited is not None else None})
            supported={t['plan']['requirement_id'] for t in traces}
            measured={key:float(min(v)) if v else None for key,v in values.items()}
            measured.update(region_available=bool(traces),region_all_plans_bound=bool(traces) and len(traces)==len(entry['region_plans']),
                            region_all_requirements_supported=supported=={r['id'] for r in entry['program']['requirements']})
            pair=digest(['bound-physical-evidence-v2','source_first',verify_image(paths['source_image']),verify_image(paths['edited_image'])])
            save(file,{'case':entry['case'],'version':regions.VERSION,'identity_ref':reference,'program_ref':entry['program']['program_ref'],
                       'image_pair_ref':pair,'measurements':measured,'features':regions.predicates(measured),'trace':traces})
            completed+=1
            if completed%10==0:
                progress={'completed_cases':completed,'total_cases':len(entries),'new_detector_inferences':inferences,'elapsed_seconds':round(time.monotonic()-started,1)}
                save(out/'progress.json',progress);print(progress,flush=True)
    result={'cases':completed,'bound_cases':sum(read(out/'cases'/(e['case']+'.json'))['measurements']['region_available'] for e in entries),
            'new_detector_inferences':inferences,'elapsed_seconds':time.monotonic()-started,'new_api_calls':0,'image_uploads':0,'reserved_sources_used':0}
    save(out/'results.json',result);(out/'run.log').write_text('Completed label-free local region extraction: '+json.dumps(result)+'\n');print(result,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True)
    modes=p.add_mutually_exclusive_group(required=True);modes.add_argument('--prepare',action='store_true');modes.add_argument('--extract',action='store_true')
    a=p.parse_args();prepare(a.output_dir.resolve()) if a.prepare else extract(a.output_dir.resolve())
