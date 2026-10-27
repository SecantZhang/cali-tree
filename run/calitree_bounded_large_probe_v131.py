"""Freeze a separate bounded-evidence profile; never repair prior responses."""
import argparse
from pathlib import Path
import shutil

from critical.core.decision.bounded_local_schema_v131 import schema
from critical.core.decision.artifacts import digest,save_json
from critical.lm_engine.local_qwen_v94 import file_hash
from run import calitree_large_observer_probe_v129 as probe


def prepare(out):
    probe.prepare(out)
    profile=probe.read(out/'identity.json');jobs=probe.read(out/'jobs.json');protocol=probe.read(out/'protocol.json');manifest=probe.read(out/'manifest.json')
    profile.update(schema_ref=digest(schema()),evidence_max_chars=360)
    for job in jobs:
        job.pop('request_ref');job.update(identity_ref=digest(profile),schema=schema());job['request_ref']=digest(job)
    protocol.update(version='large-bounded-local-observer-v131',view='Same32B model, original seven categorical states/prompt/image budget and greedy decoder. Only the evidence string schema is narrowed to1-360 characters.',
        predecessor='The unbounded v129 profile and every failed/truncated result remain separate. These are fresh requests under a new schema, not output repair or retries of earlier slots.')
    files=[Path(__file__),probe.ROOT/'critical/core/decision/bounded_local_schema_v131.py']
    for source in files:
        dest=out/'source_snapshot'/source.relative_to(probe.ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,dest)
    manifest['code_sha256'].update({str(p):file_hash(p) for p in files});manifest.update(identity_ref=digest(profile),jobs_ref=digest(jobs),protocol_ref=digest(protocol))
    save_json(out/'identity.json',profile);save_json(out/'jobs.json',jobs);save_json(out/'protocol.json',protocol);save_json(out/'manifest.json',manifest)
    (out/'run.log').write_text('Prepared separate12-case bounded-evidence32B schema. All prior outputs remain unchanged; no inference yet.\n')
    print({'cases':12,'evidence_max_chars':360,'identity_ref':digest(profile),'max_local_tokens':6144},flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--prepare',action='store_true');p.add_argument('--collect',action='store_true');a=p.parse_args()
    if a.prepare==a.collect:p.error('Choose prepare or collect')
    (prepare if a.prepare else probe.collect)(a.output_dir.resolve())
