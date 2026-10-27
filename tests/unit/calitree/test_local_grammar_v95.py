import pytest

from critical.lm_engine.local_qwen_grammar_v95 import LocalQwenGrammarEngine


def test_schema_binding_is_per_request_and_never_uses_remote_fallback(monkeypatch, tmp_path):
    engine = LocalQwenGrammarEngine(tmp_path, {'revision': 'fixture'})
    def forbidden(*args, **kwargs):
        raise AssertionError('No remote fallback')
    monkeypatch.setattr(LocalQwenGrammarEngine, 'creds', property(forbidden))
    schemas = []
    def complete(messages, paths, schema):
        schemas.append(schema)
        return '{"state":"uncertain"}', 20, 7
    monkeypatch.setattr(engine, '_complete_schema', complete)
    first = {'type': 'object', 'properties': {'state': {'type': 'string'}}, 'required': ['state'], 'additionalProperties': False}
    second = {'type': 'object', 'properties': {'other': {'type': 'string'}}, 'required': ['other'], 'additionalProperties': False}
    assert engine.generate('Observe.', schema=first)['parsed'] == {'state': 'uncertain'}
    engine.generate('Observe another.', schema=second)
    assert schemas == [first, second]
    with pytest.raises(ValueError, match='Closed object'):
        engine.generate('Observe.', schema={'type': 'object'})
