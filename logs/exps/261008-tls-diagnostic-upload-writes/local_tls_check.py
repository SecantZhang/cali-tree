"""Large loopback uploads using a generated, explicitly trusted TLS certificate."""
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
from pathlib import Path
import ssl
import subprocess
import tempfile
from threading import Thread

import requests

OUTPUT=Path(__file__).resolve().parent


def main():
    data=json.dumps({'synthetic':'x'*1500000}).encode();expected=sha256(data).hexdigest()
    with tempfile.TemporaryDirectory(prefix='calitree-local-tls-') as temporary:
        root=Path(temporary);cert=root/'certificate.pem';key=root/'key.pem';config=root/'openssl.conf'
        config.write_text('[req]\ndistinguished_name=dn\nprompt=no\nx509_extensions=v3\n[dn]\nCN=localhost\n[v3]\nsubjectAltName=DNS:localhost,IP:127.0.0.1\n')
        subprocess.run(['openssl','req','-x509','-nodes','-newkey','rsa:2048','-keyout',str(key),
            '-out',str(cert),'-days','1','-config',str(config)],check=True,capture_output=True)
        class Handler(BaseHTTPRequestHandler):
            protocol_version='HTTP/1.1'
            def do_POST(self):
                received=self.rfile.read(int(self.headers['Content-Length']))
                answer=json.dumps({'hash_match':sha256(received).hexdigest()==expected,
                    'tls':self.connection.version(),'cipher':self.connection.cipher()[0]}).encode()
                self.send_response(200);self.send_header('Content-Length',str(len(answer)));self.end_headers();self.wfile.write(answer)
            def log_message(self,*args):pass
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);ctx.load_cert_chain(cert,key)
        server.socket=ctx.wrap_socket(server.socket,server_side=True)
        thread=Thread(target=server.serve_forever,daemon=True);thread.start();rows=[]
        try:
            for workers in (1,2):
                def call(i):
                    try:
                        r=requests.post(f'https://127.0.0.1:{server.server_port}/',data=data,
                            verify=str(cert),timeout=10,allow_redirects=False)
                        return {'workers':workers,'index':i,'outcome':'http_response',**r.json()}
                    except Exception as exc:return {'workers':workers,'index':i,'outcome':'transport_error','error':str(exc)}
                with ThreadPoolExecutor(max_workers=workers) as pool:rows.extend(pool.map(call,range(16)))
        finally:server.shutdown();server.server_close();thread.join()
    result={'synthetic_only':True,'certificate_verification':True,'openssl':ssl.OPENSSL_VERSION,
        'body_bytes':len(data),'attempts':len(rows),'successful_intact_uploads':sum(r.get('hash_match',False) for r in rows),'observations':rows}
    (OUTPUT/'local_tls_result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='observations'}))


if __name__=='__main__':main()
