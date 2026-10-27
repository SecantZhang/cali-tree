import pytest

from run.audit_calitree_regular_views_v84 import media_identity


def test_generic_judge_media_identity_includes_source_and_edited_text_markers():
    evidence={'source_image':'before.png','edited_image':'after.png'}
    hashes={'before.png':'a'*64,'after.png':'b'*64}
    assert media_identity(evidence,hashes)==[
        {'type':'text','text':'SOURCE image'},{'type':'image','sha256':'a'*64},
        {'type':'text','text':'EDITED image'},{'type':'image','sha256':'b'*64}]
    assert media_identity(evidence,hashes)!=media_identity({'source_image':'after.png','edited_image':'before.png'},hashes)


def test_unknown_image_is_not_accepted_as_an_unverified_cache_match():
    with pytest.raises(KeyError):media_identity({'source_image':'unknown.png','edited_image':'after.png'},{'after.png':'b'*64})
