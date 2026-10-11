"""Pinned official GEPA, with all execution and model calls delegated to the host."""
import contextlib
from importlib.metadata import version
import json
import sys

def run(request):
    if version('gepa') != '0.1.4':
        raise RuntimeError('Expected gepa==0.1.4')
    import gepa
    from gepa.core.adapter import EvaluationBatch
    from gepa.utils.stop_condition import MaxCandidateProposalsStopper
    wire = sys.stdout
    def rpc(event, **payload):
        wire.write(json.dumps({'event': event, **payload}) + '\n'); wire.flush()
        response = json.loads(sys.stdin.readline())
        if 'error' in response:
            raise RuntimeError(response['error'])
        return response['result']
    state = {'parent': request['genome']}
    class Adapter:
        propose_new_texts = None
        def evaluate(self, batch, candidate, capture_traces=False):
            row = rpc('evaluate', genome=candidate['decision_graph'], parent=state['parent'])
            return EvaluationBatch(outputs=[row], scores=[row['score']], trajectories=[row] if capture_traces else None)
        def make_reflective_dataset(self, candidate, eval_batch, components_to_update):
            state['parent'] = candidate['decision_graph']
            return {key: [{'Inputs': request['instruction'], 'Generated Outputs': row,
                           'Feedback': 'Improve this executable JSON graph while preserving the original instruction and schema.'}
                          for row in eval_batch.trajectories] for key in components_to_update}
    def reflect(messages):
        return rpc('reflect', messages=messages, parent=state['parent'])
    with contextlib.redirect_stdout(sys.stderr):
        result = gepa.optimize(seed_candidate={'decision_graph': request['genome']},
                trainset=[{'id': request['case_id']}], valset=[{'id': request['case_id']}],
                adapter=Adapter(), reflection_lm=reflect, candidate_selection_strategy='pareto',
                skip_perfect_score=False, reflection_minibatch_size=1, use_merge=False,
                stop_callbacks=MaxCandidateProposalsStopper(request['max_steps']),
                seed=request['seed'], display_progress_bar=False, cache_evaluation=False, raise_on_exception=True)
    return {'event': 'done', 'candidates': result.candidates, 'parents': result.parents, 'best_index': result.best_idx}

if __name__ == '__main__':
    try:
        response = run(json.loads(sys.stdin.readline()))
    except Exception as exc:
        response = {'event': 'error', 'error': f'{type(exc).__name__}: {exc}'}
    sys.stdout.write(json.dumps(response) + '\n'); sys.stdout.flush()
