"""Re-encode real image pairs through the reusable, label-free inference API."""
import argparse
import json
from pathlib import Path
import sys
import time


def main(args):
    # Append project-only dependencies after the isolated vision environment's
    # pinned NumPy/Pillow/Torch stack; do not mutate either environment.
    sys.path.append(str(args.project_dependencies.resolve()))
    from critical.vision.paired_encoder_v69 import PairedVisionEncoder
    from critical.vision.paired_features_v69 import predicates
    from critical.core.calibration.visual_semantic_policy_v69 import VisualSemanticPolicy
    from critical.core.optimization.prompt.calitree.visual_semantic_judge_v69 import VisualSemanticJudge
    from critical.core.decision.artifacts import save_json
    started = time.monotonic()
    read = lambda p: json.loads(Path(p).read_text())
    artifact = read(args.policy)
    runtime = VisualSemanticPolicy(artifact)
    encoder = PairedVisionEncoder(args.model_dir, artifact['encoder_spec'])
    judge = VisualSemanticJudge(None, runtime, encoder)
    entries = read(args.inputs)
    assert len(entries) == 915 and all(not {'reference', 'human_score'} & set(e) for e in entries)
    out = args.output_dir.resolve()
    if out.exists():
        raise ValueError('Fresh inference replay directory required')
    out.mkdir(parents=True)
    rows, changes = [], []
    for index, entry in enumerate(entries, 1):
        visual = encoder.compute(entry['program'], entry['evidence'])
        features = predicates(visual['measurements'])
        if features != entry['expected_visual_flags']:
            changes.append({'case': entry['case'], 'changed_flags': [name for name in features if features[name] != entry['expected_visual_flags'][name]]})
        result = judge.judge(entry['program']['instruction'], entry['evidence'], program=entry['program'],
            observation=entry['observation'], interpretation=entry['interpretation'], regular_judgment=entry['judgment'], vision_record=visual)
        save_json(out / 'vision_cases' / (entry['case'] + '.json'), visual)
        rows.append({'case': entry['case'], 'judgment': result['judgment'], 'route': result['route'], 'source': result['source']})
        if index % 50 == 0:
            print({'cases': index, 'total': len(entries), 'changed_visual_flag_cases': len(changes), 'elapsed_seconds': round(time.monotonic() - started, 1)}, flush=True)
    save_json(out / 'predictions.json', rows)
    report = {'cases': len(entries), 'changed_visual_flag_cases': len(changes), 'changes': changes,
              'elapsed_seconds': round(time.monotonic() - started, 1), 'new_paid_model_calls': 0,
              'labels_supplied': False, 'case_identifiers_used_for_predictions': False}
    save_json(out / 'verification.json', report)
    (out / 'run.log').write_text('Recomputed every image pair through generic PairedVisionEncoder and bound VisualSemanticJudge, using cached regular/bound inputs only.\n' + str(report) + '\n')
    (out / 'llm-histories.log').write_text('Zero model API calls; frozen local encoder inference only.\n')
    print(report, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--policy', type=Path, required=True)
    parser.add_argument('--inputs', type=Path, required=True)
    parser.add_argument('--model-dir', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--project-dependencies', type=Path, required=True)
    main(parser.parse_args())
