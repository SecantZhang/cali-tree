"""Compatibility and default-routing regressions for the fulfillment consolidation."""
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT=Path(__file__).resolve().parents[3]


def test_current_import_does_not_load_historical_optimizers():
    script='''import sys
from critical.core.optimization.program import create_leaf_optimizer
from critical.core.optimization.program.fulfillment import create_fulfillment_leaf_optimizer
assert create_leaf_optimizer is create_fulfillment_leaf_optimizer
import run.calitree_fulfillment
assert not [m for m in sys.modules if m.startswith('critical.core.optimization.program.legacy')]
assert not [m for m in sys.modules if m.startswith('run.legacy')]
'''
    subprocess.run([sys.executable,'-c',script],cwd=ROOT,check=True)


def test_current_and_compatibility_defaults_are_fulfillment(tmp_path):
    from run.calitree_fulfillment import preflight
    from run.calitree_adaptive_leaf import preflight as compatibility_preflight
    current=preflight(tmp_path/'current')
    old=compatibility_preflight(tmp_path/'compatibility')
    assert current['scoring']==old['scoring']=='fulfillment'
    assert current['arms']==['binary','fulfillment']
    # Moving code changes source hashes, never the experimental protocol or case bindings.
    assert {k:v for k,v in current.items() if k!='code_hashes'}=={k:v for k,v in old.items() if k!='code_hashes'}
    assert preflight(tmp_path/'current')==current
    assert current['semantic_audit'] is current['model_readout'] is False
    assert current['policy']['agreement']==1 and current['policy']['repeats']==5
    assert current['thresholds']=={'yes':.9,'no':.1}
    with pytest.raises(ValueError,match='Unknown scoring'):preflight(tmp_path/'unsupported',scoring='semantic')


def test_cli_offline_demo_defaults_to_fulfillment(tmp_path):
    for runner in ('run.calitree_fulfillment','run.calitree_adaptive_leaf'):
        result=subprocess.run([sys.executable,'-m',runner,'--offline-demo','--output-dir',str(tmp_path/runner)],
                              cwd=ROOT,check=True,capture_output=True,text=True)
        demo=json.loads(result.stdout)
        assert demo['model_calls']==0
        assert demo['labels']['half']['fulfillment']=='partial'
        assert demo['labels']['almost']['fulfillment']=='yes'


def test_historical_imports_remain_identical_and_patchable():
    from critical.core.optimization.program.robust.adaptive import AdaptiveLeafOptimizer
    from critical.core.optimization.program.legacy.robust.adaptive import AdaptiveLeafOptimizer as archived
    from critical.core.optimization.program.shared.search import LocalLeafOptimizer
    from critical.core.optimization.program.robust.fulfillment import FulfillmentLeafOptimizer
    from critical.core.optimization.program.fulfillment import FulfillmentLeafOptimizer as current
    assert AdaptiveLeafOptimizer is archived and issubclass(archived,LocalLeafOptimizer)
    assert FulfillmentLeafOptimizer is current and issubclass(current,LocalLeafOptimizer)
    from critical.core.optimization.program.backends.textgrad import load_textgrad
    from critical.core.optimization.program.shared.textgrad import load_textgrad as shared
    assert load_textgrad is shared


@pytest.mark.parametrize('directory,version',[
    ('261006-casewise-leaf-v2',2),('261009-adaptive-leaf-v4',4),
    ('261009-counting-leaf-v5',5),('261009-counting-endpoints-v6',6),('261009-fulfillment-v7',7)])
def test_saved_bundle_dispatch_and_hash_parity(directory,version):
    from critical.core.optimization.prompt.calitree.node.program_leaf import validate_program_leaves,artifact_runtime
    saved=json.loads((ROOT/'logs/exps'/directory/'leaves.json').read_text())
    validate_program_leaves(saved)
    restore,identify=artifact_runtime(saved)
    assert saved['version']==f'calitree-casewise-leaves-v{version}'
    for ref,artifact in saved['programs'].items():
        p=restore(artifact)
        assert identify(p)==ref
        assert p.to_dict()==artifact['program']


def test_saved_v3_program_hashes_remain_exact():
    from critical.core.decision.robust.models import restore_program
    artifacts=[]
    for path in (ROOT/'logs/exps/261007-robust-hard-cases-v3/prepared').glob('*.json'):
        row=json.loads(path.read_text())
        if 'seed' in row:artifacts.append(row['seed'])
    assert artifacts
    for artifact in artifacts:
        p=restore_program(artifact)
        assert p.ref==artifact['program_ref'] and p.to_dict()==artifact['program']


def test_shared_templates_preserve_frozen_backward_and_discovery_prompts():
    from critical.core.optimization.program.shared.templates import template
    templates=ROOT/'critical/core/prompts/templates'
    assert template('gradient')==(templates/'robust_leaf_v3/gradient.txt').read_text()
    assert template('discovery')==(templates/'evidence_refinement_v1/discovery.txt').read_text()
