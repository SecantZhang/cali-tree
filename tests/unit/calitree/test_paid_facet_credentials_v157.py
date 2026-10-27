import json

import pytest

from critical import config
from run import calitree_paid_facet_credentials_v157 as runner


def test_explicit_refreshed_file_cannot_fall_back_to_old_credentials(tmp_path):
    missing = tmp_path/'missing.env'
    with pytest.raises(ValueError, match='does not exist'):
        runner.resolve_credentials(missing)
    missing.write_text('SOME_OTHER_SETTING=fixture\n')
    with pytest.raises(ValueError, match='no scoped OpenAI key'):
        runner.resolve_credentials(missing)
    missing.write_text('OPENAI_API_KEY=public-new-fixture\n')
    creds, source = runner.resolve_credentials(missing)
    assert creds.token == 'public-new-fixture' and creds.endpoints == [runner.ENDPOINT]
    assert source['source'] == 'explicit_scoped_file' and source['path'] == str(missing)


def test_scoped_settings_are_read_as_json_and_nonofficial_endpoints_rejected(tmp_path):
    settings = tmp_path/'credentials.json'
    settings.write_text(json.dumps({'providers': {'openai': {'token': 'public-fixture', 'base_url': runner.ENDPOINT}}}))
    creds, _ = runner.resolve_credentials(settings)
    assert creds.token == 'public-fixture' and creds.provider == 'openai'
    settings.write_text(json.dumps({'providers': {'openai': {'token': 'public-fixture', 'base_url': 'https://example.test/v1'}}}))
    with pytest.raises(ValueError, match='Exact official'):
        runner.resolve_credentials(settings)


def test_default_loader_keeps_manual_settings_and_restores_global_root_on_failure(tmp_path, monkeypatch):
    manual = tmp_path/'scoped-settings.json'; manual.write_text('{}')
    before = config.PROJECT_ROOT
    monkeypatch.setattr(config, 'CREDENTIALS_FILE', manual)
    def rejected(**kwargs):
        assert kwargs['credentials_file'] == manual
        assert kwargs['credentials_file'].name != '.env'
        raise RuntimeError('fixture credential failure')
    monkeypatch.setattr(runner, 'load_creds_with_source', rejected)
    with pytest.raises(RuntimeError, match='fixture credential failure'):
        runner.resolve_credentials()
    assert config.PROJECT_ROOT == before and config.CREDENTIALS_FILE == manual


def test_stopped_budget_cannot_trigger_credential_lookup_or_automatic_reset(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, 'verify', lambda _: {'passed': True})
    monkeypatch.setattr(runner, 'resolve_credentials', lambda _: pytest.fail('Stopped run must not contact provider'))
    (tmp_path/'manifest.json').write_text('{}')
    authorization = {'approved': True, 'upload_approved': True, 'manifest_sha256': runner.file_hash(tmp_path/'manifest.json'),
        'max_requests': runner.MAX_CALLS, 'max_completion_tokens': runner.MAX_TOKENS}
    (tmp_path/'authorization.json').write_text(json.dumps(authorization))
    ledger = tmp_path/'ledger'; ledger.mkdir()
    state = {'stopped': 'Provider rejected the request', 'calls': 2}
    (ledger/'budget.json').write_text(json.dumps(state))
    with pytest.raises(ValueError, match='verified external recovery'):
        runner.collect(tmp_path, live=True)
    assert json.loads((ledger/'budget.json').read_text()) == state
