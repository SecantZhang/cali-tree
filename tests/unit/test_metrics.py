import pytest

from vejudge.core.eval import metrics as M


def test_spearman_perfect_monotonic():
    x = [1, 2, 3, 4, 5]
    y = [2, 4, 6, 8, 10]
    r = M.spearman(x, y)
    assert r is not None and abs(r - 1.0) < 1e-9


def test_spearman_too_few_returns_none():
    assert M.spearman([1, 2], [2, 4]) is None


def test_mae():
    assert M.mae([1, 2, 3], [1, 2, 5]) == pytest.approx(2 / 3)


def test_qwk_perfect_agreement():
    x = [1, 2, 3, 4, 5]
    k = M.quadratic_weighted_kappa(x, x)
    assert k is not None and abs(k - 1.0) < 1e-9


def test_by_category_splits():
    rows = [
        {"c": "a", "h": 1, "j": 1},
        {"c": "a", "h": 2, "j": 2},
        {"c": "a", "h": 3, "j": 3},
        {"c": "b", "h": 1, "j": 3},
        {"c": "b", "h": 2, "j": 2},
        {"c": "b", "h": 3, "j": 1},
    ]
    out = M.by_category(rows, category_key="c", metric_fn=M.spearman, x_key="h", y_key="j")
    assert out["a"] is not None and out["a"] > 0
    assert out["b"] is not None and out["b"] < 0
