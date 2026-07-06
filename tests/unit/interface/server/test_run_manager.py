import json

from vejudge.interface.server.graph import EdgeSpec, GraphSpec, NodeSpec
from vejudge.interface.server.run_manager import start_run


def _graph():
    return GraphSpec(
        nodes=[NodeSpec(id="a", type="dataset", params={"loader": "peanut_eval"})],
        edges=[],
    )


def test_start_run_tags_config_and_writes_graph(tmp_path):
    run, checkpoint = start_run(_graph(), dry_run=True, allow_live=False, resume_from=tmp_path)

    cfg = json.loads((run.run_dir / "run_config.json").read_text())
    assert cfg["benchmark"] == "interface_graph"
    assert cfg["dry_run"] is True
    assert cfg["node_types"] == ["dataset"]

    graph_json = json.loads((run.run_dir / "workflow_graph.json").read_text())
    assert graph_json["nodes"][0]["id"] == "a"
    assert (run.run_dir / "run.log").is_file()
    assert checkpoint.path == run.run_dir / "judge_results.jsonl"


def test_resume_keeps_original_config(tmp_path):
    run1, _ = start_run(_graph(), dry_run=True, allow_live=False, resume_from=tmp_path)
    run1.close()

    run2, _ = start_run(
        GraphSpec(nodes=[], edges=[]), dry_run=False, allow_live=True, resume_from=tmp_path,
    )
    cfg = json.loads((run2.run_dir / "run_config.json").read_text())
    assert cfg["dry_run"] is True  # unchanged from the original run, not the resume args
