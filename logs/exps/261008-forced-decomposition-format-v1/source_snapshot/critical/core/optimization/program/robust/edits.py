"""Atomic typed transactions preserve an immutable canonical requirement ledger."""
from copy import deepcopy
from critical.core.decision.compiler import object_schema, array, enum, TEXT, OUTCOME_SCHEMA
from critical.core.decision.robust.compiler import NODE_SCHEMA
from critical.core.decision.robust.models import RobustProgram

OPERATORS = ('add', 'remove', 'split', 'binding', 'applicability', 'checker_revision', 'routing', 'reorder', 'subtree_replace')
EDIT_SCHEMA = object_schema({'operator': enum(OPERATORS), 'remove_nodes': array(TEXT), 'nodes': array(NODE_SCHEMA),
                            'remove_outcomes': array(TEXT), 'outcomes': array(OUTCOME_SCHEMA), 'node_order': array(TEXT)})
MAPPING_SCHEMA = object_schema({'old_outcome': TEXT, 'replacements': array(TEXT)})
TX_SCHEMA = object_schema({'reason': TEXT, 'edits': array(EDIT_SCHEMA), 'outcome_mapping': array(MAPPING_SCHEMA)})
PROPOSAL_SCHEMA = object_schema({'transactions': array(TX_SCHEMA)})

def apply_transaction(parent, transaction):
    row = deepcopy(parent.to_dict())
    edits = transaction['edits']
    if not 1 <= len(edits) <= 4 or not isinstance(transaction['reason'], str) or not transaction['reason'].strip():
        raise ValueError('Need one to four edits and a diagnostic reason')
    for edit in edits:
        if edit['operator'] not in OPERATORS:
            raise ValueError('Unsupported edit operator')
        for field, remove_key in (('nodes', 'remove_nodes'), ('outcomes', 'remove_outcomes')):
            entries = {v['id']: v for v in row[field]}
            removes = edit[remove_key]
            additions = edit[field]
            if len(set(removes)) != len(removes) or not set(removes) <= set(entries):
                raise ValueError('Removal references an absent or duplicate identity')
            if len({v['id'] for v in additions}) != len(additions):
                raise ValueError('Duplicate transaction replacement')
            for key in removes:
                del entries[key]
            for value in additions:
                entries[value['id']] = value
            row[field] = list(entries.values())
        order = edit['node_order']
        if order:
            by_id = {v['id']: v for v in row['nodes']}
            if len(order) != len(by_id) or set(order) != set(by_id):
                raise ValueError('Reordering must name every node exactly once')
            row['nodes'] = [by_id[key] for key in order]
    # Validate only the completed transaction: intermediate broken references are allowed.
    child = RobustProgram.from_dict(row)
    if child.requirements != parent.requirements:
        raise ValueError('Immutable requirement provenance changed')
    mapping = {}
    for entry in transaction['outcome_mapping']:
        if entry['old_outcome'] in mapping:
            raise ValueError('Duplicate outcome replacement mapping')
        mapping[entry['old_outcome']] = entry['replacements']
    new = {o.id: o for o in child.outcomes}
    old_ids = {o.id for o in parent.outcomes}
    if not set(mapping) <= old_ids:
        raise ValueError('Mapping refers to absent original outcome')
    for old in parent.outcomes:
        if new.get(old.id) == old and old.id not in mapping:
            continue
        replacements = mapping.get(old.id, [])
        if not replacements or not set(replacements) <= set(new):
            raise ValueError('Changed outcomes need explicit replacement mappings')
        coverage = {r for oid in replacements for r in new[oid].requirement_ids}
        if not set(old.requirement_ids) <= coverage:
            raise ValueError('Replacement drops original requirement coverage')
    return child
