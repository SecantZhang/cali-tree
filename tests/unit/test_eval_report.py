from vejudge.core.eval.report import per_dimension_agreement


def _rows():
    rows = []
    for i in range(5):
        rows.append(
            {
                "item_id": f"prj-x::{i}::peanut",
                "project": "prj-x",
                "model": "peanut",
                "use_case": "visual montage",
                "dimension": "video_addresses_prompt",
                "human": float(1 + (i % 5)),
                "judge_raw": float(1 + (i % 5)),
            }
        )
    return rows


def test_per_dimension_agreement_schema():
    per_dim = per_dimension_agreement(_rows())
    pd = per_dim["video_addresses_prompt"]
    assert pd["n"] == 5
    assert pd["spearman"] is not None and pd["spearman"] > 0.99
    assert "use_case" in pd["by_category"] and "model" in pd["by_category"]


def test_per_dimension_agreement_empty_dimension():
    per_dim = per_dimension_agreement([])
    # every dimension in ALIGNMENT is still reported, just with n=0 / None metrics
    pd = per_dim["video_addresses_prompt"]
    assert pd["n"] == 0
    assert pd["spearman"] is None
