"""Typed source-only support checks for experimental bound-evidence programs.

This is a compiler/observer component, not a grading policy. It requires explicit
source anchors and authorization declarations; it never infers them from labels
or from successful edited outcomes. Source declarations remain fallible evidence.
Frozen programs and observations are not mutated or silently reused.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, replace
from hashlib import sha256
from pathlib import Path

from critical.core.decision import bound_evidence_v2 as physical
from critical.core.decision.artifacts import digest
from critical.core.decision.compiler import media_inputs

VERSION = 'source-anchored-support-v17'
TEMPLATES = Path(__file__).resolve().parents[4] / 'prompts/templates/source_support_v17'
PROPERTIES = {'color': 'attribute', 'texture': 'attribute', 'material': 'attribute',
              'shape': 'attribute', 'size': 'attribute', 'location': 'spatial_relation',
              'orientation': 'orientation', 'configuration': 'spatial_relation'}
MODES = ('same_instance', 'counterpart', 'presence', 'property', 'properties', 'waive')
WAIVERS = ('authorized_removal', 'new_entity', 'authorized_property_change')


@dataclass(frozen=True)
class SourceAnchor:
    selector: str
    status: str
    candidates: tuple[str, ...] = ()

    def __post_init__(self):
        if (not isinstance(self.selector, str) or not self.selector.strip()
                or self.status not in ('identified', 'ambiguous', 'not_found')
                or not isinstance(self.candidates, tuple)
                or any(not isinstance(s, str) or not s.strip() for s in self.candidates)
                or len(set(self.candidates)) != len(self.candidates)
                or self.status == 'identified' and len(self.candidates) != 1
                or self.status == 'ambiguous' and not self.candidates
                or self.status == 'not_found' and self.candidates):
            raise ValueError('Invalid source-only anchor')


@dataclass(frozen=True)
class SupportBinding:
    check_id: str
    mode: str
    anchor_id: str | None = None
    property_name: str | None = None
    authorization_quote: str = ''
    waiver_reason: str | None = None
    property_names: tuple[str, ...] = ()

    def __post_init__(self):
        if not isinstance(self.check_id, str) or not self.check_id or self.mode not in MODES:
            raise ValueError('Invalid support-check binding')
        if not isinstance(self.authorization_quote, str):
            raise ValueError('Authorization must be an instruction quote')
        if (not isinstance(self.property_names, tuple) or len(set(self.property_names)) != len(self.property_names)
                or any(p not in PROPERTIES for p in self.property_names)
                or self.mode == 'properties' and (not self.property_names or self.property_name is not None)
                or self.mode != 'properties' and self.property_names):
            raise ValueError('A property set needs explicit distinct atomic properties')
        if self.mode == 'waive':
            if self.anchor_id is not None or self.property_name is not None or self.waiver_reason not in WAIVERS or not self.authorization_quote.strip():
                raise ValueError('A waiver needs an explicit reason and quoted authorization')
        elif (not isinstance(self.anchor_id, str) or not self.anchor_id or self.waiver_reason is not None
              or self.mode == 'property' and self.property_name not in PROPERTIES
              or self.mode not in ('property', 'properties') and self.property_name is not None
              or self.mode == 'counterpart' and not self.authorization_quote.strip()):
            raise ValueError('An anchored support check needs a compatible mode/property/authorization')


def _binding_dict(binding):
    return {**asdict(binding), 'property_names': sorted(binding.property_names)}


def _binding_from_dict(value):
    if not isinstance(value, dict) or not isinstance(value.get('property_names'), list):
        raise ValueError('Invalid persisted atomic property set')
    return SupportBinding(**{**value, 'property_names': tuple(value['property_names'])})


def inventory(source_image, anchors, *, origin):
    """Bind source declarations to source pixels; no edited input is accepted."""
    if origin not in ('manual_source_review', 'source_only_model', 'unverified_source_proposal'):
        raise ValueError('Declare the source inventory provenance')
    if not isinstance(anchors, dict) or not anchors or any(not isinstance(k, str) or not k for k in anchors):
        raise ValueError('Named source anchors required')
    if any(not isinstance(v, SourceAnchor) for v in anchors.values()):
        raise ValueError('Use typed source anchors')
    if origin == 'unverified_source_proposal' and any(a.status == 'identified' for a in anchors.values()):
        raise ValueError('Unverified source proposals cannot certify identification')
    result = {'version': VERSION, 'view': 'source_only', 'source_image_sha256': sha256(Path(source_image).read_bytes()).hexdigest(),
        'origin': origin, 'anchors': {k: {**asdict(v), 'candidates': sorted(v.candidates)} for k, v in sorted(anchors.items())}}
    result['inventory_ref'] = digest(result)
    return result


def validate_inventory(value):
    if (not isinstance(value, dict) or set(value) != {'version', 'view', 'source_image_sha256', 'origin', 'anchors', 'inventory_ref'}
            or value['version'] != VERSION or value['view'] != 'source_only'
            or value['origin'] not in ('manual_source_review', 'source_only_model', 'unverified_source_proposal')
            or not isinstance(value['source_image_sha256'], str) or len(value['source_image_sha256']) != 64
            or any(c not in '0123456789abcdef' for c in value['source_image_sha256'])
            or not isinstance(value['anchors'], dict) or not value['anchors']
            or digest({k: v for k, v in value.items() if k != 'inventory_ref'}) != value['inventory_ref']):
        raise ValueError('Invalid source inventory binding')
    for key, row in value['anchors'].items():
        if not isinstance(key, str) or not key or not isinstance(row, dict) or set(row) != {'selector', 'status', 'candidates'} or not isinstance(row['candidates'], list):
            raise ValueError('Invalid source anchor fields')
        anchor = SourceAnchor(row['selector'], row['status'], tuple(row['candidates']))
        if value['origin'] == 'unverified_source_proposal' and anchor.status == 'identified':
            raise ValueError('Unverified source proposal claims identification')
    return value


def _draft(program):
    draft = {k: deepcopy(program[k]) for k in ('contract', 'requirements', 'checks')}
    for r in draft['requirements']:
        r.pop('check_ids')
    for c in draft['checks']:
        c.pop('check_ref')
    return draft


def _render(check, binding, anchor):
    result = deepcopy(check)
    selector = anchor['selector']
    if binding.mode in ('same_instance', 'counterpart'):
        filename = 'identity_instance.txt' if binding.mode == 'same_instance' else 'identity_counterpart.txt'
        kind, absence = 'identity', 'never'
    elif binding.mode == 'presence':
        filename, kind, absence = 'presence.txt', 'presence', 'false'
    else:
        filename, kind, absence = 'property.txt', PROPERTIES[binding.property_name], 'never'
    result.update(question=(TEMPLATES / filename).read_text().strip().format(selector=selector, property_name=binding.property_name),
        target='Source-selected entity or region: ' + selector, reference='The same source anchor: ' + selector,
        applicability_condition='The source referent is present and identifiable in SOURCE; edit completion is not an applicability condition.',
        kind=kind, expected_state='true', dependencies=[], absence_when=absence, absence_source_anchor='required')
    return result


def compile_support(program, source_inventory, bindings, *, source_dependencies=None):
    """Rewrite every support check from typed declarations; leave other checks intact.

    Counterpart/waiver quotes are exact provenance links, not a semantic proof of
    authorization. The caller must obtain the declaration from instruction analysis
    or review. Missing declarations and dangling waiver dependencies fail loudly.
    """
    physical.validate_program(program); validate_inventory(source_inventory)
    bindings = tuple(bindings)
    if any(not isinstance(b, SupportBinding) for b in bindings) or len({b.check_id for b in bindings}) != len(bindings):
        raise ValueError('Distinct typed support bindings required')
    protected = {c['id']: c for c in program['checks'] if c['role'] in ('identity', 'preservation')}
    if {b.check_id for b in bindings} != set(protected):
        raise ValueError('Exactly every identity/preservation check needs a declaration')
    source_dependencies = {} if source_dependencies is None else source_dependencies
    check_ids = {c['id'] for c in program['checks']}
    if not isinstance(source_dependencies, dict) or not set(source_dependencies) <= check_ids:
        raise ValueError('Source dependencies must name existing checks')
    for ids in source_dependencies.values():
        if (not isinstance(ids, (list, tuple)) or any(not isinstance(k, str) for k in ids)
                or len(set(ids)) != len(ids) or not set(ids) <= set(source_inventory['anchors'])):
            raise ValueError('Source dependencies must name distinct declared anchors')
    draft = _draft(program); by_id = {c['id']: [c] for c in draft['checks']}; omitted = set(); changes = []; rendered_bindings = []
    for binding in bindings:
        check = by_id[binding.check_id][0]
        if binding.authorization_quote and binding.authorization_quote not in program['instruction']:
            raise ValueError('Authorization is not quoted from this instruction')
        if binding.mode == 'waive':
            if check['role'] == 'identity' and binding.waiver_reason == 'authorized_property_change':
                raise ValueError('A property change does not waive identity correspondence')
            omitted.add(check['id'])
            by_id[check['id']] = []
            changes.append({'check_id': check['id'], 'action': 'omitted', 'declaration': _binding_dict(binding),
                            'original_check_ref': protected[check['id']]['check_ref']})
            continue
        if binding.anchor_id not in source_inventory['anchors']:
            raise ValueError('Unknown source anchor')
        allowed = ('same_instance', 'counterpart') if check['role'] == 'identity' else ('presence', 'property', 'properties')
        if binding.mode not in allowed:
            raise ValueError('Binding mode changes the original support role')
        atomic = [binding] if binding.mode != 'properties' else [replace(binding,
            check_id='sp_' + digest([check['id'], name])[:16], mode='property', property_name=name, property_names=())
            for name in sorted(binding.property_names)]
        rendered = []
        for item in atomic:
            raw = {**check, 'id': item.check_id}
            rendered.append(_render(raw, item, source_inventory['anchors'][binding.anchor_id]))
            rendered_bindings.append(_binding_dict(item))
        by_id[check['id']] = rendered
        changes.append({'check_id': check['id'], 'action': 'expanded' if binding.mode == 'properties' else 'rendered',
            'rendered_check_ids': [c['id'] for c in rendered], 'declaration': _binding_dict(binding),
            'original_check_ref': protected[check['id']]['check_ref'], 'removed_dependencies': list(check['dependencies'])})
    for c in draft['checks']:
        for rendered in by_id[c['id']]:
            if set(rendered['dependencies']) & omitted:
                raise ValueError('A waived check has a surviving dependent; regenerate that intent explicitly')
            rendered['dependencies'] = list(dict.fromkeys(new['id'] for dep in rendered['dependencies'] for new in by_id[dep]))
    if set(source_dependencies) & omitted:
        raise ValueError('A waived check cannot retain source dependencies')
    draft['checks'] = [new for c in draft['checks'] for new in by_id[c['id']]]
    compiled = physical.bind_program(program['instruction'], draft)
    result = {'version': VERSION, 'source_inventory': deepcopy(source_inventory), 'original_program': deepcopy(program),
        'program': compiled, 'bindings': [_binding_dict(b) for b in sorted(bindings, key=lambda b: b.check_id)],
        'rendered_bindings': sorted(rendered_bindings, key=lambda b: b['check_id']),
        'source_dependencies': {k: sorted(v) for k, v in sorted(source_dependencies.items())},
        'changes': sorted(changes, key=lambda c: c['check_id']),
        'template_refs': {p.name: sha256(p.read_bytes()).hexdigest() for p in sorted(TEMPLATES.glob('*.txt'))}}
    result['binding_ref'] = digest(result)
    return result


def validate_bundle(bundle):
    fields = {'version', 'source_inventory', 'original_program', 'program', 'bindings', 'rendered_bindings', 'source_dependencies', 'changes', 'template_refs', 'binding_ref'}
    if not isinstance(bundle, dict) or set(bundle) != fields or bundle['version'] != VERSION:
        raise ValueError('Invalid source-support bundle fields')
    if digest({k: v for k, v in bundle.items() if k != 'binding_ref'}) != bundle['binding_ref']:
        raise ValueError('Source-support bundle changed')
    try:
        declarations = [_binding_from_dict(b) for b in bundle['bindings']]
    except (TypeError, ValueError) as error:
        raise ValueError('Invalid persisted support declaration') from error
    expected = compile_support(bundle['original_program'], bundle['source_inventory'], declarations,
                               source_dependencies=bundle['source_dependencies'])
    if expected != bundle:
        raise ValueError('Rendered source-support contract or templates changed')
    return bundle


def _source_map(bundle):
    result = {b['check_id']: {b['anchor_id']} for b in bundle['rendered_bindings']}
    expanded = {r['check_id']: r.get('rendered_check_ids', []) for r in bundle['changes']}
    for check_id, anchors in bundle['source_dependencies'].items():
        for new_id in expanded.get(check_id, [check_id]):
            result.setdefault(new_id, set()).update(anchors)
    return {k: sorted(v) for k, v in sorted(result.items()) if v}


def normalize_observation(bundle, raw, pair_ref):
    """Retain raw facts and expose conservative normalization separately."""
    validate_bundle(bundle); program = bundle['program']
    physical.validate_observation(program, raw, pair_ref)
    result = deepcopy(raw); decisions = []
    protected = {b['check_id'] for b in bundle['rendered_bindings']}
    for check_id, anchor_ids in _source_map(bundle).items():
        anchors = [bundle['source_inventory']['anchors'][k] for k in anchor_ids]
        row = result['checks'][check_id]
        reasons = []
        unresolved = {a['status'] for a in anchors if a['status'] != 'identified'}
        if unresolved:
            row['source_anchor'] = 'ambiguous' if 'ambiguous' in unresolved else 'not_found'
            row['applicability'] = 'unknown'
            reasons.extend('source_inventory_' + status for status in sorted(unresolved))
        elif row['source_anchor'] != 'identified':
            row['applicability'] = 'unknown'
            reasons.append('observer_source_anchor_unconfirmed')
        if check_id in protected and row['state'] == 'false' and row['edited_coverage'] != 'adequate':
            reasons.append('negative_support_claim_has_inadequate_coverage')
        if reasons:
            asserted = raw['checks'][check_id]['state']
            row['state'] = 'unknown'
            decisions.append({'check_id': check_id, 'asserted_state': asserted, 'effective_state': 'unknown', 'reasons': reasons})
    physical.validate_observation(program, result, pair_ref)
    return result, decisions


class SourceSupportObserver(physical.BoundVisualObserver):
    def __init__(self, calls, bundle):
        super().__init__(calls)
        self.bundle = deepcopy(validate_bundle(bundle))
        if self.bundle['source_inventory']['origin'] == 'unverified_source_proposal':
            raise ValueError('Source anchors require source-only review before observation')

    def observe(self, program, evidence, *, case_id=None, max_tokens=16384):
        bundle = validate_bundle(self.bundle)
        if program != bundle['program']:
            raise ValueError('Observer program differs from its source-support bundle')
        hashes, pair = physical.image_identity(evidence)
        if hashes['source_image'] != bundle['source_inventory']['source_image_sha256']:
            raise ValueError('Source inventory belongs to different source pixels')
        payload = {'program': program, 'image_pair_ref': pair, 'source_inventory': bundle['source_inventory'],
                   'source_bindings': bundle['rendered_bindings'], 'source_dependencies': _source_map(bundle),
                   'source_binding_ref': bundle['binding_ref']}
        template = (physical.TEMPLATES / 'observe.txt').read_text() + '\n' + (TEMPLATES / 'observe.txt').read_text()
        raw, ref = self.calls.call('source_support_observation_v17', payload, physical.observation_schema(program, pair),
            template=template, media=media_inputs(evidence), slot='once', max_tokens=max_tokens, case_id=case_id)
        normalized, changes = normalize_observation(bundle, raw, pair)
        return {'observation': normalized, 'raw_observation': deepcopy(raw), 'normalization': changes,
                'image_hashes': hashes, 'execution_ref': ref, 'version': VERSION, 'source_binding_ref': bundle['binding_ref'],
                'observation_ref': digest([bundle['binding_ref'], pair, normalized])}
