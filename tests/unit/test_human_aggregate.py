from vejudge.database.dl_human_annotations.aggregate import aggregate_annotations
from vejudge.database.dl_human_annotations.loader import HumanAnnotationRecord


def _rec(annotator, slot, scores, complete=True, ranking=None):
    ann = dict(scores)
    ann["_complete"] = complete
    if ranking is not None:
        ann["overall_ranking"] = ranking
    return HumanAnnotationRecord(
        path="x",
        annotator=annotator,
        project="prj-x",
        model="peanut",
        prompt_idx=0,
        cell_key="prompt_0__peanut",
        output_slot=slot,
        complete=complete,
        annotation=ann,
    )


def test_mean_over_annotators_drops_empty():
    recs = [
        _rec("a", 1, {"video_addresses_prompt": "5", "story_flow_visuals": "4"}),
        _rec("b", 1, {"video_addresses_prompt": "3", "story_flow_visuals": ""}),
    ]
    out = aggregate_annotations(recs, use_case_lookup={"prj-x": "visual montage"})
    rec = out["prj-x::0::peanut"]
    assert rec.n_annotators == 2
    assert rec.scores["video_addresses_prompt"] == 4.0  # (5+3)/2
    assert rec.scores["story_flow_visuals"] == 4.0  # empty dropped -> only the 4
    assert rec.score_counts["story_flow_visuals"] == 1
    assert rec.use_case == "visual montage"


def test_dimension_with_no_scores_is_none():
    recs = [_rec("a", 1, {"video_addresses_prompt": ""})]
    out = aggregate_annotations(recs)
    rec = out["prj-x::0::peanut"]
    assert rec.scores["video_addresses_prompt"] is None
    assert rec.score_counts["video_addresses_prompt"] == 0


def test_raw_scores_preserve_each_rater_alongside_the_mean():
    recs = [
        _rec("a", 1, {"video_addresses_prompt": "5"}),
        _rec("b", 1, {"video_addresses_prompt": "3"}),
        _rec("c", 1, {"video_addresses_prompt": "4"}),
    ]
    rec = aggregate_annotations(recs)["prj-x::0::peanut"]
    # Mean/count unchanged…
    assert rec.scores["video_addresses_prompt"] == 4.0
    assert rec.score_counts["video_addresses_prompt"] == 3
    # …and the individual raters are now kept (order preserved).
    assert rec.raw_scores["video_addresses_prompt"] == [5.0, 3.0, 4.0]
    # A dimension with no numeric scores gets no raw_scores entry.
    assert "story_flow_visuals" not in rec.raw_scores


def test_pairwise_derivation():
    recs = [_rec("a", 1, {"video_addresses_prompt": "5"}, ranking="1")]
    out = aggregate_annotations(recs)
    pw = out["prj-x::0::peanut"].pairwise
    assert len(pw) == 1
    assert pw[0]["this_preferred"] is True
    assert pw[0]["preferred_slot"] == 1
