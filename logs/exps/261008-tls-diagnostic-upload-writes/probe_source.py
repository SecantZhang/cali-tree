"""Nonbillable TLS diagnostics: synthetic POSTs without authentication or images.

Targets only api.openai.com; never loads credentials, disables verification,
retries, follows redirects, or changes an experiment ledger.
"""
from concurrent.futures import ThreadPoolExecutor,as_completed
from collections import Counter
import argparse
import json
from hashlib import sha256
from pathlib import Path
import ssl
import subprocess
import tempfile
import time

import certifi
import requests
import httpx
from requests.adapters import HTTPAdapter

URL='https://api.openai.com/v1/chat/completions'


class BoundedBody:
    """Iterable writes with the original Content-Length, not HTTP chunk framing."""
    def __init__(self,data):self.data=data
    def __len__(self):return len(self.data)
    def __iter__(self):
        for offset in range(0,len(self.data),16384):yield self.data[offset:offset+16384]


def context(version):
    ctx=ssl.create_default_context(cafile=certifi.where())
    if version=='1.2':ctx.minimum_version=ctx.maximum_version=ssl.TLSVersion.TLSv1_2
    return ctx


class Adapter(HTTPAdapter):
    def __init__(self,ctx):self.ctx=ctx;super().__init__(max_retries=0)
    def init_poolmanager(self,*args,**kwargs):
        kwargs['ssl_context']=self.ctx
        return super().init_poolmanager(*args,**kwargs)
    def build_connection_pool_key_attributes(self,request,verify,cert=None):
        host,options=super().build_connection_pool_key_attributes(request,verify,cert)
        options['ssl_context']=self.ctx
        return host,options


def payload(size):
    return {'model':'gpt-6-luna','messages':[{'role':'user','content':'x'*size}],
        'temperature':0,'reasoning_effort':'none','max_completion_tokens':1}


def probe(client,version,size,index):
    row={'client':client,'tls_configuration':version,'synthetic_content_bytes':size,'index':index}
    data=payload(size);start=time.monotonic()
    try:
        if client=='curl':
            with tempfile.NamedTemporaryFile(prefix='calitree-synthetic-body-') as body:
                body.write(json.dumps(data).encode());body.flush()
                command=['curl','--silent','--show-error','--retry','0','--connect-timeout','10','--max-time','20',
                    '--http1.1','--output','/dev/null','--write-out','%{json}',
                    '--header','Content-Type: application/json; charset=UTF-8','--data-binary','@'+body.name]
                if version=='1.2':command+=['--tlsv1.2','--tls-max','1.2']
                completed=subprocess.run([*command,URL],capture_output=True,text=True,timeout=25)
            details=json.loads(completed.stdout)
            row.update(curl_exit=completed.returncode,http_version=details.get('http_version'),
                certificate_verify_result=details.get('ssl_verify_result'),http_status=details.get('http_code'))
            if completed.returncode:raise RuntimeError(completed.stderr.strip())
            row['tls_negotiated']=None
        elif client in ('requests','requests-16k'):
            with requests.Session() as session:
                if version!='default':session.mount('https://',Adapter(context(version)))
                body_options={'data':BoundedBody(json.dumps(data).encode())} if client=='requests-16k' else {'json':data}
                with session.post(URL,**body_options,headers={'Content-Type':'application/json; charset=UTF-8'},
                                  timeout=(10,20),allow_redirects=False,stream=True) as response:
                    conn=getattr(response.raw,'_connection',None);sock=getattr(conn,'sock',None)
                    row['tls_negotiated']=sock.version() if sock else None
                    row['http_status']=response.status_code
                    row['server']=response.headers.get('server')
                    row['request_id']=response.headers.get('x-request-id')
                    row['response_bytes']=len(response.content)
        else:
            transport=httpx.HTTPTransport(verify=context(version),retries=0)
            with httpx.Client(transport=transport,timeout=20,follow_redirects=False) as session:
                with session.stream('POST',URL,json=data,headers={'Content-Type':'application/json; charset=UTF-8'}) as response:
                    stream=response.extensions.get('network_stream')
                    sock=stream.get_extra_info('ssl_object') if stream else None
                    row['tls_negotiated']=sock.version() if sock else None
                    row['http_status']=response.status_code
                    row['server']=response.headers.get('server')
                    row['request_id']=response.headers.get('x-request-id')
                    row['response_bytes']=len(response.read())
        row['outcome']='http_response'
    except Exception as exc:
        row.update(outcome='tls_bad_record_mac' if 'BAD_RECORD_MAC' in str(exc) or 'bad record mac' in str(exc).lower() else 'transport_error',
                   error_type=type(exc).__name__,error=str(exc))
    row['seconds']=round(time.monotonic()-start,3)
    return row


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--clients',nargs='+',choices=['requests','httpx','requests-16k','curl'],default=['requests'])
    p.add_argument('--tls',nargs='+',choices=['default','1.2'],default=['default'])
    p.add_argument('--sizes',nargs='+',type=int,default=[1024,1500000])
    p.add_argument('--workers',nargs='+',type=int,default=[1,2])
    p.add_argument('--samples',type=int,default=12)
    a=p.parse_args()
    if not 1<=a.samples<=20 or any(w not in (1,2) for w in a.workers) or any(not 0<=s<=3000000 for s in a.sizes):
        p.error('Bound samples to 20, workers to 2, content to 3 MB')
    attempts=len(a.clients)*len(a.tls)*len(a.sizes)*len(a.workers)*a.samples
    if attempts>128:p.error('At most 128 requests per diagnostic run')
    a.output_dir.mkdir(parents=True,exist_ok=True)
    path=a.output_dir/'manifest.json'
    if path.exists():p.error('Choose a fresh diagnostic directory; probes are not resampled')
    manifest={'version':'tls-synthetic-probe-v1','endpoint':URL,'authentication':False,'model_calls':0,
        'synthetic_data_only':True,'certificate_verification':True,'automatic_retries':0,'redirects':False,
        'attempts':attempts,'clients':a.clients,'tls':a.tls,'sizes':a.sizes,'workers':a.workers,'samples':a.samples,
        'openssl':ssl.OPENSSL_VERSION}
    manifest['source_sha256']=sha256(Path(__file__).read_bytes()).hexdigest()
    (a.output_dir/'probe_source.py').write_bytes(Path(__file__).read_bytes())
    path.write_text(json.dumps(manifest,indent=2)+'\n');rows=[]
    with (a.output_dir/'observations.jsonl').open('a') as observations:
        for client in a.clients:
            for version in a.tls:
                for size in a.sizes:
                    for workers in a.workers:
                        # Tiny and bulk cells alternate worker counts; each call
                        # gets its own client, matching the production lifetime.
                        with ThreadPoolExecutor(max_workers=workers) as pool:
                            tasks=[pool.submit(probe,client,version,size,i) for i in range(a.samples)]
                            for task in as_completed(tasks):
                                row={**task.result(),'workers':workers};rows.append(row)
                                observations.write(json.dumps(row)+'\n');observations.flush()
                        cell=[r for r in rows if (r['client'],r['tls_configuration'],r['synthetic_content_bytes'],r['workers'])==
                              (client,version,size,workers)]
                        print(json.dumps({'client':client,'tls':version,'bytes':size,'workers':workers,
                            'outcomes':dict(Counter(r['outcome'] for r in cell)),
                            'http_statuses':dict(Counter(r.get('http_status') for r in cell))}),flush=True)
    (a.output_dir/'summary.json').write_text(json.dumps({'attempts':len(rows),
        'outcomes':dict(Counter(r['outcome'] for r in rows)),'observations':rows},indent=2)+'\n')


if __name__=='__main__':main()
