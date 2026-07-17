from vejudge.core.eval.rater_agreement import inter_rater_agreement


def test_perfect_agreement_is_zero_spread():
    items = [{"d": [4.0, 4.0, 4.0]}, {"d": [2.0, 2.0]}]
    out = inter_rater_agreement(items)
    assert out["d"].self_mae == 0.0
    assert out["d"].pairwise_mae == 0.0
    assert out["d"].n_items == 2 and out["d"].n_ratings == 5


def test_disagreement_self_and_pairwise_mae():
    # One item, raters 2/4/5 -> mean 3.667.
    out = inter_rater_agreement([{"d": [2.0, 4.0, 5.0]}])
    ra = out["d"]
    # self: mean(|2-3.667|,|4-3.667|,|5-3.667|) = mean(1.667,0.333,1.333) = 1.1111
    assert abs(ra.self_mae - 1.1111) < 1e-3
    # pairwise: mean(|2-4|,|2-5|,|4-5|) = mean(2,3,1) = 2.0
    assert ra.pairwise_mae == 2.0


def test_single_rater_items_are_skipped():
    # A dimension where no item has >= 2 raters yields no entry (no disagreement signal).
    out = inter_rater_agreement([{"d": [3.0]}, {"d": [4.0]}])
    assert "d" not in out


def test_dimension_scoping_and_mixed_coverage():
    items = [{"a": [1.0, 3.0], "b": [5.0]}, {"a": [2.0, 2.0]}]
    out = inter_rater_agreement(items, dimensions=["a", "b"])
    assert "a" in out and out["a"].n_items == 2  # both items have >=2 raters on 'a'
    assert "b" not in out  # only a single rater on 'b'
