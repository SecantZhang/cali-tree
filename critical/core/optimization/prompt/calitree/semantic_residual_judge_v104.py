"""Opt-in weighted semantic review with the same one-call observer interface."""
from .local_semantic_judge_v99 import LocalSemanticJudge


class SemanticResidualJudge(LocalSemanticJudge):
    def judge(self, *args, **kwargs):
        result = super().judge(*args, **kwargs)
        if result['route'].get('reason') == 'semantic_residual_override':
            route = result['route']; weighted = route['semantic_residual']
            result['source'] = 'guarded_weighted_semantic_rubric'
            result['judgment']['rationale'] = ('The source-held weighted task/preservation rubric selects this grade under '+weighted['guard']+
                '. Local comparison: '+route['local_evidence']+'. The correction combines '+str(len(weighted['matching_clauses']))+
                ' matching clauses; these are statistical grade weights, not calibrated correctness probabilities.')
            result['local_observation_ref'] = route['local_observation_ref']
        return result
