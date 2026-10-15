"""Lossless provenance normalization; never changes a visual observation."""
from copy import deepcopy
from .semantic_evidence import validate


def normalize_literal_quotes(value,instruction):
    """Remove one decorative quote pair only if its contents are a literal span.

    Raw provider output remains immutable. No fuzzy matching, word replacement,
    case folding, score access, or changes to any visual evidence are permitted.
    The full original schema validation must pass after the transformation.
    """
    result=deepcopy(value);changes=[]
    for index,aspect in enumerate(result.get('aspects',[])):
        quote=aspect.get('source_quote')
        if not isinstance(quote,str) or quote in instruction:continue
        q=quote.strip()
        if len(q)>=2 and (q[0],q[-1]) in (('"','"'),("'","'"),('“','”'),('‘','’')):
            inner=q[1:-1]
            if inner and inner in instruction:
                aspect['source_quote']=inner;changes.append({'aspect':index,'before':quote,'after':inner})
    validate(result,instruction)
    return result,changes
