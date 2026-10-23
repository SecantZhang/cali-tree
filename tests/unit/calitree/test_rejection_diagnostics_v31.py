from run.diagnose_calitree_rejections_v31 import bank_stats,warnings


def row(case,reference,vote,experts,shortlist=(),error=None):
    return {'case':case,'reference':reference,'regular':reference,'ungated_split1':vote,'extraction_error':error,
            'routes':{'v27_split1':{'covered':False,'reason':'test','semantic_candidates':{'expert_refs':list(shortlist)}}},
            'votes':{'1':{'expert_votes':{str(i):{'prediction':v}for i,v in enumerate(experts)}}}}


def test_oracle_headroom_is_not_confused_with_all_expert_errors_or_missing_evidence():
    rows=[row('routing',0,2,[0,2,2],['0']),row('allwrong',0,1,[1,2]),
          row('correct',1,1,[1,0]),row('missing',0,-1,[-1,-1],error='CallFailure')]
    stats=bank_stats(rows,1)
    assert stats['rejected']==4 and stats['valid_rejected']['cases']==3 and stats['extraction_failures']==1
    assert stats['wrong_vote_cases']==2 and stats['wrong_vote_with_correct_expert']==1
    assert stats['wrong_vote_with_correct_shortlisted_expert']==1 and stats['all_experts_wrong']==1
    assert stats['valid_rejected']['any_expert_correct']==2


def test_compound_warning_does_not_require_every_requirement_to_fail():
    a={'progress':'none','endpoint_gap':'core_endpoint_missing','identity_materiality':'no_shortfall',
       'collateral_materiality':'none','evidence_consistency':'coherent'}
    b={**a,'progress':'requested_endpoint','endpoint_gap':'none'}
    result=warnings({'interpretation':{'requirements':{'r1':a,'r2':b}}})
    assert result['any_goal_failure'] and result['multiple_requirements']
    assert not result['any_material_shortfall'] and not result['any_evidence_uncertainty']
