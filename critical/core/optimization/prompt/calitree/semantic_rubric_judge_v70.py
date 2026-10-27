"""Execute reconstructed rubric rules over the existing bound LLM evidence."""
from .visual_semantic_judge_v69 import VisualSemanticJudge
from ....calibration.semantic_rubric_v70 import DESCRIPTIONS


class SemanticRubricJudge(VisualSemanticJudge):
    def judge(self, *args, **kwargs):
        result = super().judge(*args, **kwargs)
        route = result['route']
        if route.get('rubric_rule'):
            rule = route['rubric_rule']
            descriptions = [(DESCRIPTIONS[t['feature']] if t['value'] else 'Not established: ' + DESCRIPTIONS[t['feature']])
                            for t in rule['conditions']]
            result['judgment']['rationale'] = ('Semantic rubric rule ' + str(rule['rule_index'] + 1) +
                                              ' applies to the bound extracted evidence: ' + ' AND '.join(descriptions))
            result['source'] = 'semantic_rubric'
        return result
