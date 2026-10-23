"""Replay every frozen forward policy through the real inference wrapper.

Uses cached original evidence and a stub flat judge for every possible label.
Reference labels are not inference inputs. No new extraction or model clients.
"""
import argparse
from collections import Counter
from pathlib import Path

from critical.core.decision.artifacts import save_json
from critical.core.decision.calls import CallFailure
from critical.core.optimization.prompt.calitree.bound_evidence_cache import BoundEvidenceCache
from critical.core.optimization.prompt.calitree.evidence_covered_judge import BoundEvidencePipeline
from critical.core.optimization.prompt.calitree.regular_aware_judge_v35 import RegularAwareJudge
from critical.core.optimization.prompt.calitree.task_coverage import LABELS, TEMPLATES, SCHEMA
from run.analyze_calitree_guarded_forward_v35 import policies, route, predict
from run.calitree_guarded_forward_v32 import SOURCE
from run.calitree_aurora_pilot_v29 import IDENTITY, read, fingerprint


class FlatStub:
    identity = IDENTITY

    def __init__(self, label):
        self.label, self.requests = label, []

    def call(self, stage, payload, schema, **kwargs):
        assert stage == 'flat_judge', 'Unexpected extra extraction or per-expert model call'
        assert set(payload) == {'instruction'} and schema == SCHEMA
        assert kwargs['template'] == (TEMPLATES / 'regular.txt').read_text()
        assert kwargs['max_tokens'] == 2048 and kwargs['slot'] == 'once'
        self.requests.append({'stage': stage, 'payload': payload, **kwargs})
        return {'label': self.label, 'rationale': 'Mock regular judgment for wrapper equivalence.'}, 'mock-flat'


class FailedEvidence:
    def compile(self, *args, **kwargs):
        raise CallFailure('Retained failed upstream evidence; no retry')

    def extract(self, *args, **kwargs):
        raise CallFailure('Retained failed upstream evidence; no retry')


def audit(forward, output):
    if output.exists():
        raise ValueError('A fresh audit directory is required')
    gates = policies(forward)
    examples = read(forward / 'inputs.json')
    cache = BoundEvidenceCache(IDENTITY)
    for e in examples:
        if e['features'] is None:
            continue
        raw = read(SOURCE / f"extraction/cases/{e['case']}.json")
        interpreted = read(SOURCE / f"interpretations/{e['case']}.json")
        cache.add(e['instruction'], e['evidence'], e['program'],
                  raw['observation']['observation'], interpreted['interpretation'])
    counts = Counter()
    records = []
    for bank, gate in gates.items():
        for e in examples:
            for regular in (-1, 0, 1, 2):
                label = LABELS[regular] if regular >= 0 else 'unresolved'
                calls = FlatStub(label)
                extractor = BoundEvidencePipeline(calls) if e['features'] is not None else FailedEvidence()
                wrapper = RegularAwareJudge(calls, gate, evidence_cache=cache, identity=IDENTITY, extractor=extractor)
                result = wrapper.judge(e['instruction'], e['evidence'], case_id=e['case'])
                expected = route(gate, e, regular)
                prediction = predict(expected, regular)
                expected_label = LABELS[prediction] if prediction >= 0 else 'unresolved'
                assert result['judgment']['label'] == expected_label
                # Missing evidence uses a differently worded wrapper error, but
                # still the identical deferral and unchanged regular response.
                assert result['route']['covered'] == expected['covered']
                if e['features'] is not None:
                    assert result['route'] == expected and result['evidence_source'] == 'content_cache'
                    assert result['extraction_error'] is None
                    counts['cache_hits'] += 1
                else:
                    assert result['extraction_error'] == 'CallFailure'
                    counts['retained_upstream_failures'] += 1
                assert len(calls.requests) == 1
                images = [m['path'] for m in calls.requests[0]['media'] if m['type'] == 'image']
                assert images == [e['evidence']['source_image'], e['evidence']['edited_image']]
                assert result['regular_judgment']['label'] == label
                assert result['regular_execution_ref'] == 'mock-flat'
                assert result['execution_ref'] == (None if expected['covered'] else 'mock-flat')
                counts['scenario_replays'] += 1
                counts['stub_regular_calls'] += 1
                records.append({'bank': bank, 'case': e['case'], 'regular': regular, 'prediction': prediction,
                                'covered': expected['covered'], 'source': result['source']})
    output.mkdir(parents=True)
    report = {'passed': True, 'counts': dict(counts), 'reference_labels_used_for_inference': False, 'new_model_calls': 0,
              'new_extraction_calls': 0, 'identity': IDENTITY,
              'forward_freeze_sha256': fingerprint(forward / 'supplemental_v35/freeze.json'),
              'wrapper_sha256': fingerprint(Path(__file__).resolve().parents[1] / 'critical/core/optimization/prompt/calitree/regular_aware_judge_v35.py')}
    save_json(output / 'verification.json', report)
    save_json(output / 'predictions.json', records)
    (output / 'run.log').write_text('Frozen policies and original bound evidence replayed through the optional real wrapper.\n')
    (output / 'llm-histories.log').write_text('Zero real model calls. FlatStub used for 432 hypothetical regular judgments.\n')
    save_json(output / 'completion_seal.json', {'files': {str(p.relative_to(output)): fingerprint(p) for p in sorted(output.iterdir()) if p.is_file()},
              'auditor_sha256': fingerprint(__file__)})
    print(report, flush=True)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--forward-dir', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    audit(args.forward_dir.resolve(), args.output_dir.resolve())
