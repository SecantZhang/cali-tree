"""A bounded visible-evidence string with unchanged local semantic states."""
from . import local_rubric_evidence_v94 as facts


def schema():
    value=facts.schema()
    value['properties']['evidence']={'type':'string','minLength':1,'maxLength':360}
    return value
