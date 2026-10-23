"""Offline review proposals for source-anchored support checks; no live path.

These declarations illustrate the diagnosed compiler failures. They are explicitly
unverified source proposals, not image-grounding results, and cannot be sent to
SourceSupportObserver until source-only review creates a new bound inventory.
No observations, labels, classifiers or final cases are modified.
"""
import argparse
from pathlib import Path

from critical.core.decision.artifacts import digest, save_json
from critical.core.optimization.prompt.calitree.decomposition import source_support as source
from run.calitree_regularized_v13 import ROOT, read, fingerprint, exact

INPUT = ROOT / 'logs/exps/261018-evidence-contract-diagnostic-v16-r1'
DECLARATIONS = {
    'N026': {'identity': ('same_instance', 'the source actor\u2019s visible hands and forearms', ()),
             'preservation': ('presence', 'the water tap in the source scene', ())},
    'N071': {'identity': ('same_instance', 'the player referred to in the source scene', ())},
    'N090': {'identity': ('same_instance', 'the keys in the source scene', ()),
             'preservation': ('presence', 'the keys in the source scene', ())},
    'N095': {'identity': ('same_instance', 'the tiny yellow cylinder in the source scene', ()),
             'preservation': ('properties', 'the source entities other than that cylinder', tuple(source.PROPERTIES))},
    'N119': {'identity': ('counterpart', 'the banana in the source scene', ())},
}


def preview(out):
    manifest = read(INPUT / 'manifest.json'); programs = read(INPUT / 'programs.json')
    assert manifest['programs_ref'] == digest(programs)
    cases = {r['case']: r for r in manifest['cases']}
    inputs = {str((INPUT / name).relative_to(ROOT)): fingerprint(INPUT / name) for name in ('manifest.json', 'programs.json')}
    code = {str(Path(__file__).resolve().relative_to(ROOT)): fingerprint(__file__),
            str(Path(source.__file__).resolve().relative_to(ROOT)): fingerprint(source.__file__)}
    code.update({str(p.relative_to(ROOT)): fingerprint(p) for p in source.TEMPLATES.glob('*.txt')})
    exact(out / 'protocol.json', {'version': source.VERSION, 'purpose': 'Unverified source-check review proposals only',
        'source_hashes': inputs, 'code_hashes': code, 'new_model_calls': 0, 'new_fits': 0, 'reference_changes': False,
        'semantic_equivalence_claim': False, 'live_observation_allowed': False})
    rows = []
    for case, roles in DECLARATIONS.items():
        program = programs[case]; selected = {c['id']: c for c in program['checks'] if c['role'] in ('identity', 'preservation')}
        anchors = {}; bindings = []
        for check_id, check in selected.items():
            mode, selector, properties = roles[check['role']]
            key = 'source_' + check_id
            candidates = ('the source batter', 'the source catcher') if case == 'N071' else (selector,)
            anchors[key] = source.SourceAnchor(selector, 'ambiguous', candidates)
            bindings.append(source.SupportBinding(check_id, mode, key, property_names=properties,
                authorization_quote=program['instruction'] if mode == 'counterpart' else ''))
        inv = source.inventory(cases[case]['evidence']['source_image'], anchors, origin='unverified_source_proposal')
        compiled = source.compile_support(program, inv, bindings); source.validate_bundle(compiled)
        assert compiled['program']['program_ref'] != program['program_ref']
        assert compiled['program']['contract'] == program['contract']
        assert all(c['role'] in ('identity', 'preservation') or c['question'] == next(o['question'] for o in program['checks'] if o['id'] == c['id'])
                   for c in compiled['program']['checks'])
        try:
            source.SourceSupportObserver(None, compiled)
        except ValueError as error:
            assert 'source-only review' in str(error)
        else:
            raise AssertionError('An unverified proposal became observable')
        exact(out / (case + '.json'), compiled)
        new_by_id = {c['id']: c for c in compiled['program']['checks']}
        for change in compiled['changes']:
            old = selected[change['check_id']]
            rows.append({'case': case, 'check': change['check_id'], 'role': old['role'],
                'original_question': old['question'], 'original_applicability': old['applicability_condition'],
                'new_checks': [new_by_id[k] for k in change['rendered_check_ids']],
                'binding_ref': compiled['binding_ref'], 'requires_source_review': True})
    result = {'programs': len(DECLARATIONS), 'original_support_checks': len(rows),
        'rendered_support_checks': sum(len(r['new_checks']) for r in rows), 'changes': rows,
        'new_model_calls': 0, 'new_fits': 0, 'references_changed': False, 'deployed': False,
        'limitations': ['Declarations are proposed intent/source interpretations, not verified grounding.',
                       'Property sets must be reviewed for intended coverage; exact quotes do not prove authorization.',
                       'No accuracy or generalization claim follows from syntactically source-only questions.']}
    exact(out / 'results.json', result)
    lines = ['# Source-anchored support-check review proposals', '',
        'Five existing training programs, zero calls, no reference or policy changes. '
        'Every source anchor is explicitly unverified; the observer refuses these bundles. '
        'Review source grounding and intended property coverage before creating a new executable inventory.', '',
        '| Case | Support role | Original question | New atomic checks |', '|---|---|---|---:|']
    for r in rows:
        lines.append(f"| {r['case']} | {r['role']} | {r['original_question'].replace('|', '/')} | {len(r['new_checks'])} |")
    lines += ['', 'Each case JSON contains the original program, typed source declarations, rendered questions, '
        'change records and new bindings. The original outcome and collateral predicates remain intact. '
        'N095 expands the proposed eight-property preservation set into separate checks rather than dropping '
        'properties or hiding a conjunction in one question. N071 retains both actor candidates rather than '
        'silently choosing the batter or catcher.', '',
        'Replacement uses recognizable-counterpart mode with an exact instruction quote. '
        'Authorized removals, new entities and authorized property changes require explicit waiver declarations; '
        'a waiver removes a required check instead of fabricating a successful observation. '
        'The component tests cover these cases separately.', '',
        'The programs and templates are a structural compiler candidate, not a promoted observer or classifier.']
    (out / 'report.md').write_text('\n'.join(lines) + '\n'); print({k: v for k, v in result.items() if k not in ('changes', 'limitations')})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    preview(parser.parse_args().output_dir.resolve())
