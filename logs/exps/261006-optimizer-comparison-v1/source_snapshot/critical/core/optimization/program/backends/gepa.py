"""Official GEPA Pareto search of serialized executable decision graphs."""
import json
import os
from pathlib import Path
from queue import Queue, Empty
import subprocess
import tempfile
from threading import Thread

from critical.core.decision.calls import BudgetExhausted, CallFailure
from critical.core.optimization.program.base import LeafOptimizer
from critical.core.optimization.prompt.calitree.optimization.gepa import resolve_gepa_python
from .common import ProgramTrial, encode, native_text_call, LocalConvergence

class GepaProgramOptimizer(LeafOptimizer):
    def __init__(self, compiler, evaluator, *, python=None, max_steps=6, random_seed=20261006):
        self.compiler, self.evaluator = compiler, evaluator
        self.python, self.max_steps, self.random_seed = python, max_steps, random_seed

    def optimize(self, case, reference_label, *, seed=None):
        if seed is None:
            raise ValueError('Comparison optimizer requires an explicit common seed')
        interpreter = resolve_gepa_python(self.python)
        trial = ProgramTrial('gepa', case, reference_label, seed, self.compiler, self.evaluator)
        stop = 'step_limit'
        env = {k:v for k,v in os.environ.items() if k in ('PATH','SYSTEMROOT','TMPDIR','LANG')}
        env['LITELLM_LOCAL_MODEL_COST_MAP'] = 'True'
        with tempfile.TemporaryFile(mode='w+') as errors:
            process = subprocess.Popen([interpreter,'-I','-u',str(Path(__file__).with_name('gepa_worker.py'))],
                           stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=errors, text=True, env=env)
            queue = Queue()
            def read():
                for line in process.stdout:
                    queue.put(line)
                queue.put(None)
            reader = Thread(target=read, daemon=True); reader.start()
            def send(value):
                process.stdin.write(json.dumps(value)+'\n'); process.stdin.flush()
            try:
                send({'genome': encode(seed), 'case_id': case.id, 'instruction': case.instruction,
                      'max_steps': self.max_steps, 'seed': self.random_seed})
                reflection_index = 0
                while True:
                    try:
                        line = queue.get(timeout=60)
                    except Empty as exc:
                        raise RuntimeError('GEPA worker timed out') from exc
                    if line is None:
                        errors.seek(0)
                        raise RuntimeError('GEPA exited without a result: '+errors.read()[-1000:])
                    message = json.loads(line)
                    event = message['event']
                    if event == 'done':
                        trial.result.lineage.append({'method':'gepa','native_search':message})
                        break
                    if event == 'error':
                        raise RuntimeError(message['error'])
                    if event == 'evaluate':
                        feedback = trial.evaluate(message['genome'], message['parent'])
                        if trial.success:
                            raise LocalConvergence()
                        send({'result': feedback})
                    elif event == 'reflect':
                        value = native_text_call(self.compiler.calls, case, reference_label, seed, 'gepa_reflect',
                                  message['messages'], None, slot=f'{case.id}/gepa/{reflection_index}', current_text=message['parent'])
                        reflection_index += 1
                        trial.result.lineage.append({'method':'gepa','reflection':value,'parent_genome':message['parent']})
                        send({'result':value})
                    else:
                        raise RuntimeError('Unknown GEPA worker event')
            except LocalConvergence:
                stop = 'matching_confirmation'
            except BudgetExhausted as exc:
                stop = 'budget: '+str(exc)
            except (RuntimeError, ValueError, KeyError, TypeError) as exc:
                # ProviderStopped must propagate to the comparison runner, never be swallowed here.
                from critical.core.decision.calls import ProviderStopped
                if isinstance(exc, ProviderStopped):
                    raise
                stop = 'failed: '+str(exc)
            finally:
                if process.poll() is None:
                    process.terminate()
                try: process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill(); process.wait()
                process.stdin.close(); reader.join(timeout=1); process.stdout.close()
        return trial.finish(stop)
