"""v155 continuation with correct scoped credentials; identical paid job slots.

This adapter fixes credential discovery only. It cannot clear a stopped ledger,
resample rejected slots, change prompts/models, or increase the approved budget.
"""
import argparse
import json
from pathlib import Path
import shutil

from dotenv import dotenv_values

from critical import config
from critical.core.decision import facet_policy_v150 as facets
from critical.core.decision.artifacts import save_json
from critical.lm_engine.creds import ProviderCreds, load_creds_with_source
from critical.lm_engine.local_qwen_v94 import file_hash
from run.calitree_paid_facet_probe_v155 import (ENDPOINT, MAX_CALLS, MAX_TOKENS, MODELS, ROOT,
                                               read, report, verify)


def resolve_credentials(path=None):
    """A user-specified credential file never silently falls back to an old key."""
    source_path = None
    if path is not None:
        source_path = Path(path).expanduser().resolve()
        if not source_path.is_file():
            raise ValueError('Explicit credential file does not exist')
        if source_path.suffix == '.json':
            data = json.loads(source_path.read_text())
            scoped = (data.get('providers') or {}).get('openai') or {}
            token = str(scoped.get('token') or '').strip()
            base = str(scoped.get('base_url') or ENDPOINT).strip()
        else:
            data = dotenv_values(source_path)
            token = str(data.get('OPENAI_API_KEY') or '').strip()
            base = str(data.get('OPENAI_BASE_URL') or ENDPOINT).strip()
        if not token:
            raise ValueError('Explicit file has no scoped OpenAI key; no fallback')
        creds = ProviderCreds(token.removeprefix('Bearer ').strip(), base, provider='openai')
        source = 'explicit_scoped_file'
    else:
        project = Path('/Users/zzhang/Documents/Projects/Adobe/calitree-mlsys')
        previous_root = config.PROJECT_ROOT
        manual = config.CREDENTIALS_FILE
        # Settings saved in the original checkout remain usable when this
        # worktree has no manual settings. Explicit configured paths win.
        if manual == ROOT/'.interface_credentials.json' and not manual.exists() and (project/'.interface_credentials.json').is_file():
            manual = project/'.interface_credentials.json'
        try:
            config.PROJECT_ROOT = project
            creds, source = load_creds_with_source(credentials_file=manual, provider='openai', engine='gpt')
        finally:
            config.PROJECT_ROOT = previous_root
        source_path = manual if source == 'manual' else project/'.env'
    if creds.provider != 'openai' or creds.endpoints != [ENDPOINT]:
        raise ValueError('Exact official OpenAI endpoint required')
    return creds, {'source': source, 'path': str(source_path), 'endpoint': ENDPOINT}


def collect(out, *, live=False, credential_path=None):
    if not live or not (out/'authorization.json').exists():
        raise ValueError('Existing paid-call/upload authorization and --live required')
    verify(out)
    authorization = read(out/'authorization.json')
    assert authorization['approved'] is True and authorization['upload_approved'] is True
    assert authorization['manifest_sha256'] == file_hash(out/'manifest.json')
    assert authorization['max_requests'] == MAX_CALLS and authorization['max_completion_tokens'] == MAX_TOKENS
    budget_path = out/'ledger/budget.json'
    if budget_path.exists() and read(budget_path)['stopped']:
        raise ValueError('Provider ledger is stopped; verified external recovery is required before continuation')
    from critical.core.decision.calls import DurableCalls, ProviderStopped, BudgetExhausted
    from critical.lm_engine import get_engine, require_live
    from critical.logging.llm_history import LLMHistoryWriter
    require_live(True)
    creds, resolution = resolve_credentials(credential_path)
    save_json(out/'execution_adapter_v157.json', {'parent_manifest_sha256': file_hash(out/'manifest.json'),
        'helper_sha256': file_hash(__file__), 'credential_resolution': resolution,
        'prompts_models_slots_limits_changed': False})
    destination = out/'source_snapshot/run'/Path(__file__).name; destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(__file__, destination)
    history = LLMHistoryWriter(out/'llm-histories.log')
    def factory(arm):
        def create(cap):
            options = {'reasoning_effort': 'low'} if arm == 'sol' else {}
            return get_engine('gpt', creds=creds, model=MODELS[arm]['model'], temperature=MODELS[arm]['temperature'],
                max_tokens=cap, timeout=240, max_http_attempts=1, history=history, **options)
        return create
    calls = DurableCalls(out/'ledger', factory('sol'), identity=MODELS['sol'], max_calls=MAX_CALLS,
        max_completion_tokens=MAX_TOKENS, scope_limits={'search': 2, 'final': 0},
        routes={'luna': {'identity': MODELS['luna'], 'engine_factory': factory('luna')}})
    for job in read(out/'jobs.json'):
        path = out/'responses'/(job['case']+'-'+job['arm']+'.json')
        if path.exists():
            continue
        result = {'case': job['case'], 'arm': job['arm'], 'request_ref': job['request_ref'], 'accepted': False, 'error': None}
        try:
            media = [{'type': 'text', 'text': 'SOURCE image'}, {'type': 'image', 'path': job['evidence']['source_image']},
                     {'type': 'text', 'text': 'EDITED image'}, {'type': 'image', 'path': job['evidence']['edited_image']}]
            value, ref = calls.call('explicit_semantic_facets_v155', {}, job['schema'], template=job['prompt'], media=media,
                slot=job['arm'], case_id=job['case'], max_tokens=job['max_tokens'], route='luna' if job['arm'] == 'luna' else None)
            result.update(value=facets.validate(value), execution_ref=ref, accepted=True)
        except (ProviderStopped, BudgetExhausted) as exc:
            result['error'] = type(exc).__name__+': '+str(exc); save_json(path, result)
            with (out/'run.log').open('a') as log:
                log.write('Stopped: '+result['error']+'\n')
            raise
        except (ValueError, RuntimeError, TypeError, KeyError) as exc:
            result['error'] = type(exc).__name__+': '+str(exc)
        save_json(path, result)
        print({'case': job['case'], 'arm': job['arm'], 'accepted': result['accepted'], 'error': result['error']}, flush=True)
    report(out)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--credential-path', type=Path); p.add_argument('--live', action='store_true', required=True)
    a = p.parse_args(); collect(a.output_dir.resolve(), live=a.live, credential_path=a.credential_path)
