"""Official TextGrad 0.1.8 backward propagation and TGD over serialized leaf graphs."""
import importlib.metadata
import json
import os
from pathlib import Path

from critical.core.decision.calls import BudgetExhausted, CallFailure
from critical.core.optimization.program.base import LeafOptimizer
from .common import ProgramTrial, encode, decode, native_text_call, CONSTRAINTS


def load_textgrad(log_dir):
    if importlib.metadata.version('textgrad') != '0.1.8':
        raise RuntimeError('This adapter requires textgrad==0.1.8')
    os.environ.setdefault('LITELLM_LOCAL_MODEL_COST_MAP', 'True')
    os.environ['TEXTGRAD_LOG_DIR'] = str(log_dir)
    import textgrad as tg
    from textgrad.autograd.string_based_ops import StringBasedFunction
    from textgrad.engine import EngineLM
    return tg, StringBasedFunction, EngineLM

class TextGradProgramOptimizer(LeafOptimizer):
    def __init__(self, compiler, evaluator, *, max_steps=6, log_dir=None):
        self.compiler, self.evaluator, self.max_steps = compiler, evaluator, max_steps
        self.log_dir = Path(log_dir or compiler.calls.directory / 'textgrad')

    def optimize(self, case, reference_label, *, seed=None):
        if seed is None:
            raise ValueError('Comparison optimizer requires an explicit common seed')
        tg, StringBasedFunction, EngineLM = load_textgrad(self.log_dir)
        trial = ProgramTrial('textgrad', case, reference_label, seed, self.compiler, self.evaluator)
        variable = tg.Variable(encode(seed), requires_grad=True,
              role_description='executable JSON decision graph with requirements, outcomes and checks; all arrays are structurally editable')
        current_parent = encode(seed)
        state = {'step': 0, 'phase': 'backward'}
        calls = self.compiler.calls

        class NativeEngine(EngineLM):
            model_string = 'gpt-6-luna'
            def generate(self, prompt, system_prompt=None, **kwargs):
                return native_text_call(calls, case, reference_label, seed, 'textgrad_' + state['phase'],
                   prompt, system_prompt, slot=f'{case.id}/textgrad/{state["step"]}/{state["phase"]}', current_text=variable.value)
            def __call__(self, prompt, system_prompt=None, **kwargs):
                return self.generate(prompt, system_prompt=system_prompt, **kwargs)

        engine = NativeEngine()
        tgd = tg.TGD(parameters=[variable], engine=engine, constraints=list(CONSTRAINTS))
        stop = 'step_limit'
        try:
            feedback = trial.evaluate(variable.value)
            if trial.success:
                return trial.finish('seed_matches')
            for step in range(self.max_steps):
                state.update(step=step, phase='backward')
                tgd.zero_grad()
                # Official autograd creates the dependency from program variable to its execution feedback.
                fn = StringBasedFunction(lambda graph: json.dumps({**trial.evaluate(graph.value, current_parent),
                     **({'optimizer_error': feedback['optimizer_error']} if 'optimizer_error' in feedback else {})}), function_purpose=
                     'Execute this case-specific decision graph and evaluate label agreement subject to instruction preservation. '
                     'The output includes observations, semantic audit, and a reference label; improve the graph without forcing the answer.')
                loss = fn({'graph': variable})
                try:
                    from textgrad.config import SingletonBackwardEngine
                    singleton = SingletonBackwardEngine()
                    previous_engine = singleton.get_engine()
                    singleton.set_engine(None, override=True)
                    try:
                        loss.backward(engine=engine)
                    finally:
                        singleton.set_engine(previous_engine, override=True)
                    gradients = sorted(g.value for g in variable.gradients)
                    trial.result.lineage.append({'method': 'textgrad', 'step': step, 'textual_gradients': gradients})
                    state['phase'] = 'update'
                    tgd.step()
                    feedback = trial.evaluate(variable.value, current_parent)
                    if trial.success:
                        stop = 'matching_confirmation'
                        break
                    if 'validation_error' not in feedback and feedback.get('audit', {}).get('accepted'):
                        current_parent = variable.value
                except (ValueError, KeyError, TypeError, IndexError, CallFailure) as exc:
                    trial.result.lineage.append({'method': 'textgrad', 'step': step, 'error': str(exc)})
                    feedback = {**feedback, 'optimizer_error': str(exc)}
        except BudgetExhausted as exc:
            stop = 'budget: ' + str(exc)
        except (ValueError, KeyError, TypeError, CallFailure) as exc:
            stop = 'failed: ' + str(exc)
        return trial.finish(stop)
