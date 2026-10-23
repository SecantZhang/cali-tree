"""Offline rehearsal of all 48 routed slots with recorded bound evidence.

Credential loading and engine construction are both mocked. No network access,
real API calls or authorization file in the prepared experiment is created.
"""
import argparse
import json
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from critical.core.decision import semantic_interpretation_v5 as meaning
from critical.core.calibration import shared_regions_v27 as shared
from critical.core.decision.artifacts import save_json
from run import calitree_observer_diagnostic_v51r1 as diagnostic
from run.calitree_continuous_policy_v43 import EXPANSION
from run.calitree_guarded_forward_v32 import SOURCE
from run.calitree_aurora_pilot_v29 import ROOT, read, fingerprint


def audit(prepared, out):
    if out.exists():
        raise ValueError('Fresh audit directory required')
    diagnostic.verify(prepared)
    observations, interpretations = {}, {}
    for e in read(prepared / 'inputs_without_labels.json'):
        case = e['case']
        if case.startswith('N'):
            c = read(SOURCE / 'extraction/cases' / (case + '.json'))
            observation = c['observation']['observation']
            interpretation = read(SOURCE / 'interpretations' / (case + '.json'))['interpretation']
        else:
            root = EXPANSION / 'cases' if case.startswith('T') else ROOT / 'logs/exps/261020-aurora-pilot80-v29-run1/collection/cases'
            c = read(root / (case + '.json'))
            observation, interpretation = c['observation'], c['interpretation']
        assert shared.evidence.project(e['program'], observation, e['pair_ref'], interpretation) == e['cached_features']
        observations[(e['program']['program_ref'], e['pair_ref'])] = observation
        payload = meaning.make_input(e['program'], observation, e['pair_ref'])
        interpretations[payload['evidence_ref']] = interpretation
    simulated = []
    def get_engine(name, **kwargs):
        class ReplayEngine:
            def generate(self, prompt, *, media_inputs, schema, strict_schema):
                payload = json.loads(prompt.split('\nINPUT_JSON: ', 1)[1])
                if 'program' in payload:
                    assert kwargs['max_tokens'] == 16384
                    value = observations[(payload['program']['program_ref'], payload['image_pair_ref'])]
                    assert len([m for m in media_inputs if m['type'] == 'image']) == 2
                else:
                    assert kwargs['model'] == 'gpt-6-luna' and kwargs['max_tokens'] == 8192 and media_inputs == []
                    value = interpretations[payload['evidence_ref']]
                simulated.append({'model': kwargs['model'], 'max_tokens': kwargs['max_tokens']})
                return {'parsed': value, 'promptTokens': 1000, 'completionTokens': 100, 'finishReason': 'stop'}
        return ReplayEngine()
    with TemporaryDirectory(prefix='calitree-observer-replay-') as temp:
        fixture = Path(temp) / 'fixture'
        shutil.copytree(prepared, fixture)
        save_json(fixture / 'authorization.json', {'test_only': True, 'network_disabled_by_mock': True})
        with patch('critical.lm_engine.load_creds', return_value=SimpleNamespace(endpoints=['https://api.openai.com/v1'])), \
             patch('critical.lm_engine.get_engine', side_effect=get_engine), \
             patch('critical.lm_engine.require_live', return_value=None):
            diagnostic.collect(fixture, live=True)
        budget, results = read(fixture / 'ledger/budget.json'), read(fixture / 'results.json')
        assert budget['calls'] == len(simulated) == 48
        assert budget['completion_tokens_or_reserved'] == 4800
        assert budget['input_tokens'] == 48000
        assert all(v['search'] == 4 and v['final'] == 0 for v in budget['cases'].values())
        assert results['correct'] == {arm: 6 for arm in ('cached', 'luna', 'sol', 'safe_luna', 'safe_sol')}
        assert results['failures'] == {'luna': 0, 'sol': 0}
        assert sum(r['model'] == 'gpt-6.1-sol' for r in simulated) == 12
        assert sum(r['model'] == 'gpt-6-luna' for r in simulated) == 36
        assert not (prepared / 'authorization.json').exists() and not (prepared / 'ledger').exists()
        out.mkdir(parents=True)
        save_json(out / 'verification.json', {'passed': True, 'new_model_calls': 0, 'simulated_slots': 48,
                  'simulated_sol_observations': 12, 'simulated_luna_observations': 12, 'simulated_luna_interpretations': 24,
                  'cached_prediction_parity': results['correct'], 'real_authorization_created': False})
        save_json(out / 'mock_budget.json', {'simulated': True, **budget})
    save_json(out / 'manifest.json', {'auditor_sha256': fingerprint(__file__), 'prepared_manifest_sha256': fingerprint(prepared / 'manifest.json')})
    (out / 'run.log').write_text('Replayed all 48 paired-observer slots using cached physical evidence, mocked credential access and mocked engines. Both arms reproduce cached predictions. No actual API calls or paid authorization created.\n')
    (out / 'llm-histories.log').write_text('Zero real model calls; 48 in-process mocked responses, explicitly recorded in mock_budget.json.\n')
    print(read(out / 'verification.json'), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepared-dir', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    audit(args.prepared_dir.resolve(), args.output_dir.resolve())
