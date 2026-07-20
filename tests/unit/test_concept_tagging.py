import json

from vejudge.core.calibration.debate.eval.concept_tagging import tag_questions_to_concepts

_BANK = [
    {"question": "Does the judge over- or under-score by edit category?", "raises_score_when": "no"},
    {"question": "Does the judge ignore the audio?", "raises_score_when": "no"},
    {"question": "Some unmappable question?", "raises_score_when": "yes"},
]


class _Engine:
    def __init__(self, payload):
        self._payload = payload

    def generate(self, prompt, media_inputs=None, schema=None, *, system=None, model=None):
        return {"content": json.dumps(self._payload), "model": "m",
                "promptTokens": 1, "completionTokens": 1, "totalTokens": 2}


def test_maps_each_question_to_a_taxonomy_key_in_order():
    eng = _Engine({"concepts": [
        {"index": 1, "key": "category_imbalance"},
        {"index": 2, "key": "audio_neglect"},
        {"index": 3, "key": None},
    ]})
    tags = tag_questions_to_concepts(bank=_BANK, engine=eng)
    assert tags == ["category_imbalance", "audio_neglect", None]


def test_invalid_or_unknown_keys_become_none():
    eng = _Engine({"concepts": [
        {"index": 1, "key": "not_a_real_concept"},
        {"index": 2, "key": "audio_neglect"},
    ]})
    tags = tag_questions_to_concepts(bank=_BANK, engine=eng)
    assert tags == [None, "audio_neglect", None]  # unknown -> None; missing index -> None


def test_bad_response_falls_back_to_all_none():
    class _Bad:
        def generate(self, *a, **k):
            return {"content": "not json"}

    assert tag_questions_to_concepts(bank=_BANK, engine=_Bad()) == [None, None, None]


def test_empty_bank_is_empty():
    assert tag_questions_to_concepts(bank=[], engine=_Engine({})) == []
