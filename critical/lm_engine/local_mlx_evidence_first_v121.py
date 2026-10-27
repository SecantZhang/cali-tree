"""Evidence-first schema/profile over the unchanged pinned local MLX model."""
import os

from .local_mlx_v118 import LocalMLXEngine
from ..core.decision import local_rubric_evidence_v94 as facts


def schema():
    old=facts.schema()
    return {**old,'properties':{'evidence':{'type':'string','minLength':1,'maxLength':360},**{k:old['properties'][k] for k in facts.FIELDS}},
            'required':['evidence',*facts.FIELDS]}


class EvidenceFirstEngine(LocalMLXEngine):
    name='local_mlx_evidence_first_v121'

    def generate(self,prompt,media_inputs=None,output_schema=None,**kwargs):
        if os.environ.get('LMFE_STRICT_JSON_FIELD_ORDER','').lower() not in('1','true'):
            raise ValueError('Evidence-first decoding requires explicit native field-order enforcement')
        if output_schema!=schema():raise ValueError('Frozen evidence-first schema required')
        return super().generate(prompt,media_inputs,output_schema,**kwargs)
