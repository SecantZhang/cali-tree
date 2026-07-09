"""End-to-end 4-node graph (Peanut Source -> Dataset -> Judge Text -> Eval, with Dataset's
`labels` output, joined by item id against its own sampled items, also feeding Eval), no
network, no HTTP.

Proves the graph engine's wiring against real vejudge modules (loaders, judge prompt
building/parsing, alignment, metrics) before any FastAPI layer exists. The only thing
mocked is the LM engine's HTTP transport, per CLAUDE.md's testing convention.
"""

import json

from vejudge.interface.server.executor import GraphExecutionEngine
from vejudge.interface.server.run_manager import start_run


def test_graph_end_to_end(tmp_path, fixture_tree, fake_engine, quick_eval_graph):
    run_dir = tmp_path / "run"
    graph = quick_eval_graph
    run, checkpoint = start_run(graph, dry_run=False, allow_live=True, resume_from=run_dir)
    engine = GraphExecutionEngine(
        graph, run=run, checkpoint=checkpoint, dry_run=False, allow_live=True
    )
    result = engine.execute()

    assert result.status == "done", {nid: r.error for nid, r in result.node_results.items()}
    assert result.node_results["peanut_src"].outputs["raw_dataset"]
    assert result.node_results["ds"].outputs["dataset"]
    assert result.node_results["ds"].outputs["labels"]

    report = result.node_results["eval"].outputs["metrics_report"]
    assert report["n_items"] == 2  # prj-a::0::peanut, prj-b::0::peanut
    pd = report["per_dimension"]["video_addresses_prompt"]
    assert pd["n"] == 2

    for name in ("run.log", "llm-histories.log", "run_config.json", "judge_results.jsonl",
                 "workflow_graph.json", "eval_eval.json"):
        assert (run_dir / name).is_file(), f"missing {name}"

    cfg = json.loads((run_dir / "run_config.json").read_text())
    assert cfg["benchmark"] == "interface_graph"
