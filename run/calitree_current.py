"""Describe or execute the selected CaliTree pipeline over cached request stages.

This entry point never initializes a provider, encoder or local observer. Fresh
inference integrations use the public CaliTreeJudge with explicit interfaces.
"""
import argparse
import hashlib
import json
from pathlib import Path

from critical.core.optimization.prompt.calitree import CaliTreeJudge
from critical.core.optimization.prompt.calitree.current import selected_pipeline
from critical.core.decision.artifacts import save_json

REQUIRED = {'instruction', 'evidence', 'program', 'observation', 'interpretation',
            'regular_judgment', 'vision_record'}
ALLOWED = REQUIRED | {'case_id', 'expert_record', 'local_record'}


def cached_predictions(requests, judge):
    if not isinstance(requests, list) or not requests:
        raise ValueError('A nonempty list of cached requests is required')
    for request in requests:
        if not isinstance(request, dict) or not REQUIRED <= set(request) or not set(request) <= ALLOWED:
            raise ValueError('Explicit cached stages required; references and unknown fields are not inputs')
    return [judge.judge(**request) for request in requests]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--selection', type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--describe', action='store_true')
    mode.add_argument('--input', type=Path, help='JSON list of cached request stages; explicit null preserves a failed stage')
    parser.add_argument('--output-dir', type=Path)
    args = parser.parse_args(argv)
    if args.input is None:
        selected, _ = selected_pipeline(args.selection)
        print(json.dumps(selected, indent=2))
        return
    if args.output_dir is None or args.output_dir.exists():
        parser.error('--input requires a fresh --output-dir')
    requests = json.loads(args.input.read_text(encoding='utf-8'))
    judge = CaliTreeJudge(selection=args.selection)
    results = cached_predictions(requests, judge)
    args.output_dir.mkdir(parents=True)
    save_json(args.output_dir/'predictions.json', results)
    save_json(args.output_dir/'config.json', {'pipeline_version': judge.selected_version,
        'policy_ref': judge.policy.artifact['artifact_ref'], 'requests': len(requests),
        'input_sha256': hashlib.sha256(args.input.read_bytes()).hexdigest(),
        'new_model_calls': 0})
    selected, _ = selected_pipeline(args.selection)
    save_json(args.output_dir/'selection.json', selected)
    (args.output_dir/'run.log').write_text('Selected v112 pipeline executed cached request stages.\n')
    (args.output_dir/'llm-histories.log').write_text('Zero model/encoder/observer calls. All stages supplied explicitly.\n')
    print(json.dumps({'pipeline_version': judge.selected_version, 'requests': len(results),
                      'output_dir': str(args.output_dir.resolve())}))


if __name__ == '__main__':
    main()
