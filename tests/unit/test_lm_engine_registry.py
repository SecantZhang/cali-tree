"""get_engine()/available_engines() cover every registered provider family."""

import pytest

from vejudge.lm_engine import (
    ClaudeEngine,
    DeepseekEngine,
    GeminiEngine,
    GptEngine,
    KimiEngine,
    LlamaEngine,
    QwenEngine,
    available_engines,
    get_engine,
)


def test_available_engines_covers_every_provider_family():
    assert available_engines() == sorted(
        ["gemini", "gpt", "qwen", "claude", "deepseek", "llama", "kimi"]
    )


@pytest.mark.parametrize(
    "kind,cls",
    [
        ("gemini", GeminiEngine),
        ("gpt", GptEngine),
        ("qwen", QwenEngine),
        ("claude", ClaudeEngine),
        ("deepseek", DeepseekEngine),
        ("llama", LlamaEngine),
        ("kimi", KimiEngine),
    ],
)
def test_get_engine_constructs_the_right_class(kind, cls):
    assert isinstance(get_engine(kind), cls)


def test_get_engine_is_case_insensitive():
    assert isinstance(get_engine("Claude"), ClaudeEngine)


def test_get_engine_rejects_unknown_kind():
    with pytest.raises(ValueError, match="Unknown engine"):
        get_engine("not-a-real-engine")


@pytest.mark.parametrize(
    "cls,expected_video",
    [
        (ClaudeEngine, False),
        (DeepseekEngine, False),
        (LlamaEngine, False),
        (KimiEngine, False),
    ],
)
def test_new_provider_families_are_text_only(cls, expected_video):
    assert cls.supports_video is expected_video
