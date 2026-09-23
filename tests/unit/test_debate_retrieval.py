from vejudge.core.calibration.debate.retrieval import find_similar_human_note
from vejudge.database.dl_human_annotations.loader import HumanAnnotationRecord


def _rec(item_suffix, annotation, project="prj-x"):
    return HumanAnnotationRecord(
        path=f"/fake/{item_suffix}.json",
        annotator="a",
        project=project,
        model="peanut",
        prompt_idx=int(item_suffix),
        cell_key=f"prompt_{item_suffix}__peanut",
        output_slot=1,
        complete=True,
        annotation=annotation,
    )


def _sample(item_id="prj-x::0::peanut"):
    return {"item_id": item_id, "project": "prj-x", "prompt_idx": 0, "model": "peanut"}


def test_finds_matching_note_by_metric_keywords():
    records = [
        _rec("1", {"other_anomalies": "the voiceover was out of sync with the visuals"}),
    ]
    note = find_similar_human_note(sample=_sample(), metric_id="M6", records=records)
    assert note is not None
    assert note.item_id == "prj-x::1::peanut"
    assert "sync" in note.matched_terms or "voiceover" in note.matched_terms


def test_returns_none_when_no_keywords_overlap():
    records = [_rec("1", {"other_anomalies": "unrelated commentary about lighting"})]
    note = find_similar_human_note(sample=_sample(), metric_id="M6", records=records)
    assert note is None


def test_returns_none_when_no_free_text_present():
    records = [_rec("1", {"video_addresses_prompt": "4"})]
    note = find_similar_human_note(sample=_sample(), metric_id="M6", records=records)
    assert note is None


def test_excludes_the_current_item_being_debated():
    # This record IS the item under debate (same project/prompt_idx/model) -- even
    # though its text matches, it must never be used to ground its own debate.
    records = [
        _rec("0", {"other_anomalies": "voiceover freeze and audio cutoff"}),
        _rec("2", {"other_anomalies": "some other audio sync note"}),
    ]
    note = find_similar_human_note(sample=_sample("prj-x::0::peanut"), metric_id="M6", records=records)
    assert note is not None
    assert note.item_id == "prj-x::2::peanut"


def test_scans_any_note_suffixed_field_not_just_other_anomalies():
    records = [_rec("1", {"story_flow_visuals_note": "abrupt cutoffs in the video pacing"})]
    note = find_similar_human_note(sample=_sample(), metric_id="M5", records=records)
    assert note is not None
    assert "abrupt cutoffs in the video pacing" == note.text
