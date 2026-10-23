"""Reserve 80 fitting-disjoint sources without inspecting reference labels.

Select 10 sources per task category and two outputs per editing model/category.
Labels remain in the historical catalog and are not copied into the reservation.
Older repository exposure is disclosed; no globally untouched claim is made.
"""
import argparse
from collections import Counter
from pathlib import Path

from critical.core.decision.artifacts import digest, save_json
from critical.database.dl_aurora.loader import AURORA_MODELS, AURORA_TASKS
from run.calitree_aurora_pilot_v29 import ROOT, read, fingerprint, recent_exclusions
from run.calitree_accuracy_headroom_v37 import dataset
from run.calitree_m0 import pixel_hash

VERSION = 'fitting-disjoint-source-reservation-v39'
SOURCE_ROOT = Path('/Users/zzhang/Documents/Projects/Adobe/calitree-mlsys')
CATALOG = ROOT / 'logs/exps/261020-aurora-pilot80-v29/exposure/original/exposure_ledger.json'


def reserve(out):
    if out.exists():
        raise ValueError('Fresh reservation directory required')
    local, recent, _ = dataset()
    fit_sources = {e['source_group'] for e in local + recent}
    excluded, provenance = recent_exclusions(SOURCE_ROOT)
    excluded |= fit_sources
    tasks = read(CATALOG)['tasks']
    entries, seen = [], set(excluded)
    for category in AURORA_TASKS:
        candidates = sorted((t for t in tasks if t['task'] == category and t['source_group'] not in seen),
                            key=lambda t: digest([VERSION, 20261020, t['task_uid']]))
        count = 0
        for t in candidates:
            if t['source_group'] in seen:
                continue
            by_editor = {o['editor']: o for o in t['outputs']}
            if set(by_editor) != set(AURORA_MODELS):
                continue
            editor = AURORA_MODELS[count % len(AURORA_MODELS)]
            selected = by_editor[editor]
            source = SOURCE_ROOT / 'data/aurora/bench' / t['source_path']
            edited = SOURCE_ROOT / 'data/aurora/bench' / selected['edited_path']
            assert pixel_hash(source) == t['source_group']
            assert fingerprint(source) == t['source_sha256'] and fingerprint(edited) == selected['edited_sha256']
            entries.append({'case': f'V{len(entries)+1:03}', 'task_uid': t['task_uid'], 'source_group': t['source_group'],
                            'task': category, 'editor': editor, 'item_id': selected['item_id'],
                            'instruction': selected['instruction'], 'program': None,
                            'evidence': {'source_image': str(source), 'edited_image': str(edited)},
                            'image_hashes': {'source_image': t['source_sha256'], 'edited_image': selected['edited_sha256']},
                            'older_exposure': t['status'] != 'no_exposure_found'})
            seen.add(t['source_group'])
            count += 1
            if count == 10:
                break
        if count != 10:
            raise ValueError('Insufficient fitting-disjoint sources for category ' + category)
    assert len(entries) == len({e['source_group'] for e in entries}) == 80
    assert not fit_sources & {e['source_group'] for e in entries}
    assert all('reference' not in e and 'human_score' not in e for e in entries)
    out.mkdir(parents=True)
    save_json(out / 'inputs_without_labels.json', entries)
    protocol = {'version': VERSION, 'cases': 80, 'distinct_sources': 80, 'per_category': 10,
                'selection': 'Stable source hash, then fixed editor rotation; independent of human labels and model predictions.',
                'target': 'Strictly over 85% overall means at least 69/80; failures count; retain 144/144 original training slots.',
                'evaluation': 'Freeze the complete judge/controller and retrieval policy before retrieving labels or making validation judgments. Report class recall, macro F1 and constant baselines.',
                'source_exclusions': sorted(excluded), 'current_fit_source_count': len(fit_sources),
                'older_exposure': True, 'model_calls_authorized': False, 'new_model_calls': 0,
                'reference_policy': 'No labels copied or used by selection. Access catalog references only after a separate policy freeze and validation authorization.'}
    save_json(out / 'protocol.json', protocol)
    save_json(out / 'verification.json', {'passed': True, 'source_disjoint_from_fitting': True,
              'sources': len(entries), 'by_category': dict(Counter(e['task'] for e in entries)),
              'by_editor': dict(Counter(e['editor'] for e in entries)),
              'labels_used_for_selection': False, 'older_exposure_cases': sum(e['older_exposure'] for e in entries),
              'new_model_calls': 0})
    save_json(out / 'manifest.json', {'protocol_ref': digest(protocol), 'input_ref': digest(entries),
              'code_hashes': {str(Path(__file__).resolve()): fingerprint(__file__)},
              'catalog': str(CATALOG), 'catalog_sha256': fingerprint(CATALOG), 'recent_exclusion_provenance': provenance})
    (out / 'run.log').write_text('Reserved 80 distinct fitting-disjoint source pairs, no labels copied or used in selection.\n')
    (out / 'llm-histories.log').write_text('Zero model calls. Validation is not authorized yet.\n')
    save_json(out / 'reservation_seal.json', {'files': {str(p.relative_to(out)): fingerprint(p) for p in sorted(out.iterdir()) if p.is_file()}})
    print({'reserved': 80, 'distinct_sources': 80, 'current_fitting_sources_excluded': len(fit_sources),
           'total_excluded_sources': len(excluded), 'labels_accessed_for_scoring': False, 'model_calls': 0}, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    reserve(args.output_dir.resolve())
