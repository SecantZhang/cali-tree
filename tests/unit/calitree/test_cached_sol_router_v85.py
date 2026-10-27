from critical.core.decision.artifacts import digest
from run.calitree_cached_sol_router_v85 import expert_artifact


def test_expert_identity_and_role_are_bound_by_exported_artifact_hash():
    class Rule:
        def artifact(self,teacher_ref):
            return {'teacher_ref':teacher_ref,'rules':[],'rubric':'Retain the teacher.','artifact_ref':'old_hash'}
    exported=expert_artifact(Rule(),'teacher')
    assert exported['artifact_ref']==digest({k:v for k,v in exported.items() if k!='artifact_ref'})
    assert exported['selected_expert']=='gpt-6.1-sol'
    tampered={k:v for k,v in exported.items() if k!='artifact_ref'};tampered['selected_expert']='other_model'
    assert digest(tampered)!=exported['artifact_ref']
