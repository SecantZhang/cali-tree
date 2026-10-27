from copy import deepcopy

from critical.core.decision import facet_policy_v150 as facets
from run.calitree_paid_facet_probe_v155 import MODELS, CAPS
from run.verify_calitree_paid_facet_v158 import execution_ref, media_identity


def test_native_slot_identity_binds_ordered_images_and_model_route():
    job = {'case': 'fixture', 'arm': 'luna', 'identity': MODELS['luna'], 'schema': facets.schema(),
           'prompt': 'generic rubric', 'max_tokens': CAPS['luna'],
           'image_hashes': {'source_image': 'source-hash', 'edited_image': 'edit-hash'}}
    swapped = deepcopy(job)
    swapped['image_hashes'] = {'source_image': 'edit-hash', 'edited_image': 'source-hash'}
    assert execution_ref(job) != execution_ref(swapped)
    sol = {**job, 'arm': 'sol', 'identity': MODELS['sol'], 'max_tokens': CAPS['sol']}
    assert execution_ref(sol) != execution_ref(job)
    assert media_identity(job)[1]['sha256'] == 'source-hash' and media_identity(job)[3]['sha256'] == 'edit-hash'


def test_reference_grades_never_enter_the_executable_request_key():
    job = {'case': 'fixture', 'arm': 'luna', 'identity': MODELS['luna'], 'schema': facets.schema(),
           'prompt': 'generic rubric', 'max_tokens': CAPS['luna'],
           'image_hashes': {'source_image': 'source-hash', 'edited_image': 'edit-hash'}}
    assert execution_ref(job) == execution_ref({**job, 'reference': 0}) == execution_ref({**job, 'reference': 2})
