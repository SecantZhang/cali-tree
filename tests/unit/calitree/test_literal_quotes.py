from copy import deepcopy
import pytest
from critical.core.decision.literal_quotes import normalize_literal_quotes
from tests.unit.calitree.test_semantic_evidence import observation


def test_remove_only_decorative_quotes_with_literal_proof():
    value=observation();value['aspects'][0]['source_quote']='"Change it"';original=deepcopy(value)
    fixed,changes=normalize_literal_quotes(value,'Change it')
    assert value==original and len(changes)==1
    assert fixed['aspects'][0]['source_quote']=='Change it'
    restored=deepcopy(fixed);restored['aspects'][0]['source_quote']='"Change it"'
    assert restored==original


@pytest.mark.parametrize('quote',['"change it"','"Replace it"','Change that'])
def test_no_case_folding_or_fuzzy_repair(quote):
    value=observation();value['aspects'][0]['source_quote']=quote
    with pytest.raises(ValueError):normalize_literal_quotes(value,'Change it')
