"""Node backward feedback and label-blind discovery, with infrastructure failures filtered."""
from copy import deepcopy
from dataclasses import asdict
import json
from critical.core.decision.compiler import object_schema, TEXT, media_inputs
from .templates import template
from .textgrad import load_textgrad

class NodeTextGrad:
    def __init__(self, calls):
        self.calls = calls

    def feedback(self, program, case, target, report, *, slot):
        tg, StringBasedFunction, EngineLM = load_textgrad(self.calls.directory / 'textgrad-v3')
        from textgrad.config import SingletonBackwardEngine
        nodes = {n.id: n for n in program.nodes}
        # Reverse actual traversal, union across complete program draws, bounded by four nodes.
        order = list(dict.fromkeys(o['check_id'] for t in report['traces'] for o in t['observations'] if o['queried']))
        gradients = {}
        calls = self.calls
        for node_id in reversed(order):
            node = nodes[node_id]
            traces = [o for t in report['traces'] for o in t['observations'] if o['check_id'] == node_id]
            variable = tg.Variable(json.dumps(asdict(node), sort_keys=True), requires_grad=True,
                                   role_description='one immutable-snapshot executable visual decision node to repair semantically')
            context = {'reference_label': target, 'aggregate': {k: report[k] for k in ('agreement', 'coverage', 'label_distribution')},
                       'node_traces': traces, 'downstream_gradients': gradients}
            fn = StringBasedFunction(lambda node: json.dumps(context),
                function_purpose='Evaluate this visual decision node within the full program; diagnose semantic disagreement or insufficient robustness without forcing answers.')
            loss = fn({'node': variable})

            class Engine(EngineLM):
                model_string = calls.identity.get('model', 'gpt-6-luna')
                def generate(self, prompt, system_prompt=None, **kwargs):
                    value, _ = calls.call('gradient', {'native_prompt': prompt, 'native_system_prompt': system_prompt,
                        'instruction': program.instruction, 'rubric': program.rubric, 'reference_label': target,
                        'node': asdict(node), 'feedback': context}, object_schema({'text': TEXT}),
                        template=template('gradient'), media=media_inputs(case.evidence), slot=f'{slot}/{node_id}', max_tokens=2048)
                    if not isinstance(value.get('text'), str) or not value['text'].strip():
                        raise ValueError('Empty native backward response')
                    return value['text']
                def __call__(self, prompt, system_prompt=None, **kwargs):
                    return self.generate(prompt, system_prompt, **kwargs)

            singleton = SingletonBackwardEngine()
            old = singleton.get_engine()
            singleton.set_engine(None, override=True)
            try:
                loss.backward(engine=Engine())
            finally:
                singleton.set_engine(old, override=True)
            gradients[node_id] = sorted(g.value for g in variable.gradients)
        return gradients

class VisualTextGrad(NodeTextGrad):
    def feedback(self,program,case,target,report,*,slot):
        visual=deepcopy(report)
        for t in visual['traces']:
            t['observations']=[o for o in t['observations'] if o['valid'] and o['event'] not in ('transport_failure','invalid_response','interrupted_attempt')]
            for o in t['observations']:o.pop('attempts',None)
        return super().feedback(program,case,target,visual,slot=slot)

from .discovery import VisualEvidenceDiagnosis

class VisualDiagnosis(VisualEvidenceDiagnosis):
    def discover(self,program,case,report,*,slot):
        visual=deepcopy(report)
        for t in visual['traces']:
            t['observations']=[o for o in t['observations'] if o['valid'] and o['event'] not in ('transport_failure','invalid_response','interrupted_attempt')]
            for o in t['observations']:o.pop('attempts',None)
        return super().discover(program,case,visual,slot=slot)
