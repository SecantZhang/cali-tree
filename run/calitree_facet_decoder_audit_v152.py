"""CPU-only reachability and contradiction audit of the frozen v150 records.

Teacher-forced alternative token paths diagnose the grammar; they are not new
model predictions and do not replace a frozen observation or grade.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import shutil

from critical.core.decision import facet_policy_v150 as facets
from critical.core.decision.artifacts import save_json
from critical.lm_engine.local_mlx_v118 import build_tokenizer_data, terminal_ids
from critical.lm_engine.local_qwen_v94 import file_hash

ROOT = Path(__file__).resolve().parents[1]


def audit(probe, out):
    from transformers import AutoTokenizer
    from lmformatenforcer import JsonSchemaParser, TokenEnforcer
    if out.exists():
        raise ValueError('Fresh decoder audit required')
    checkpoint_path = ROOT/'logs/exps/261023-large-mlx-download-v127-r1/identity.json'
    checkpoint = json.loads(checkpoint_path.read_text())
    directory = Path(checkpoint['destination'])
    tokenizer = AutoTokenizer.from_pretrained(directory, local_files_only=True, trust_remote_code=False)
    config = json.loads((directory/'config.json').read_text())
    eos = terminal_ids(tokenizer, config['text_config']['eos_token_id'])
    data = build_tokenizer_data(tokenizer, eos_token_ids=eos)
    jobs = json.loads((probe/'jobs.json').read_text())
    states = {name: Counter() for name in facets.FIELDS}
    paths = []; contradictions = []; responses = []
    for job in jobs:
        if job['arm'] != 'facets':
            continue
        path = probe/'responses'/(job['case']+'-facets.json')
        response = json.loads(path.read_text()); responses.append(path)
        if not response['accepted']:
            continue
        value = facets.validate(response['value'])
        for name, alternatives in facets.FIELDS.items():
            states[name][value[name]] += 1
            match = re.search(r'"'+re.escape(name)+r'"\s*:\s*"', response['response']['content'])
            assert match, 'Exact native value prefix required'
            prefix = response['response']['content'][:match.end()]
            # Every legal value must be reachable after the same frozen earlier
            # fields. Fresh parser, same pinned tokenizer bridge, no GPU/model.
            for alternative in alternatives:
                text = prefix+alternative+'"'
                ids = tokenizer.encode(text, add_special_tokens=False)
                assert tokenizer.decode(ids, clean_up_tokenization_spaces=False) == text
                enforcer = TokenEnforcer(data, JsonSchemaParser(job['schema']))
                history = []; failure = None
                for index, token in enumerate(ids):
                    allowed = enforcer.get_allowed_tokens(history).allowed_tokens
                    if token not in allowed:
                        failure = {'index': index, 'token': token,
                                   'decoded': tokenizer.decode([token]), 'prefix': tokenizer.decode(history)}
                        break
                    history.append(token)
                paths.append({'case': job['case'], 'field': name, 'alternative': alternative,
                              'reachable': failure is None, 'failure': failure})
        no_gap = value['material_gap'].strip().lower().rstrip('.') == 'none'
        if no_gap and (value['all_material_facets'] == 'no' or value['operation_fidelity'] == 'unfaithful' or
                      value['source_entity_fidelity'] == 'material_unrequested_change' or value['scope_coverage'] == 'partial'):
            contradictions.append({'case': job['case'], 'value': value,
                'reason': 'Explicit categorical material gap with literal none in written material_gap'})
    report = {'passed': all(p['reachable'] for p in paths), 'checked_token_paths': len(paths),
        'unreachable_paths': sum(not p['reachable'] for p in paths), 'field_counts': states,
        'explicit_gap_contradictions': len(contradictions),
        'interpretation': 'Reachability excludes a hard grammar ban; it does not establish equal logits or correct visual reasoning. Counterfactual paths are not predictions.',
        'new_neural_calls': 0, 'new_paid_calls': 0, 'serving_changed': False}
    out.mkdir(parents=True)
    save_json(out/'verification.json', report); save_json(out/'token_paths.json', paths)
    save_json(out/'contradictions.json', contradictions)
    save_json(out/'manifest.json', {'probe_manifest_sha256': file_hash(probe/'manifest.json'),
        'auditor_sha256': file_hash(__file__), 'response_sha256': {str(p): file_hash(p) for p in responses},
        'checkpoint_identity_sha256': file_hash(checkpoint_path)})
    (out/'run.log').write_text('CPU-only replay of alternative enum paths and literal gap contradictions.\n')
    (out/'llm-histories.log').write_text('No model inference or API requests.\n')
    dest = out/'source_snapshot/run'/Path(__file__).name; dest.parent.mkdir(parents=True)
    shutil.copyfile(__file__, dest)
    print(report, flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--probe', type=Path, required=True); p.add_argument('--output-dir', type=Path, required=True)
    a = p.parse_args(); audit(a.probe.resolve(), a.output_dir.resolve())
