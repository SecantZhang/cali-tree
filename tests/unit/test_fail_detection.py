from vejudge.benchmark.human_gap.runner import all_calls_failed


def test_all_failed_detected():
    per_item = {
        "i1": {"M3": {"error": "HTTP 401 auth"}, "M5": {"error": "HTTP 401 auth"}},
        "i2": {"M3": {"error": "HTTP 401 auth"}},
    }
    err = all_calls_failed(per_item)
    assert err is not None and "401" in err


def test_some_succeed_returns_none():
    per_item = {
        "i1": {"M3": {"error": "HTTP 401"}, "M5": {"parsed": {"score_1_to_5": 3}}},
        "i2": {"M3": {"parsed": {"score_1_to_5": 4}}},
    }
    assert all_calls_failed(per_item) is None


def test_skipped_calls_ignored():
    # Only skipped video judges + one good text judge -> not a total failure.
    per_item = {
        "i1": {"M3": {"parsed": {"score_1_to_5": 2}},
               "M5": {"skipped": True}, "M6": {"skipped": True}},
    }
    assert all_calls_failed(per_item) is None


def test_all_skipped_is_not_failure():
    per_item = {"i1": {"M5": {"skipped": True}}}
    assert all_calls_failed(per_item) is None


def test_empty_is_not_failure():
    assert all_calls_failed({}) is None
