import pytest

from vejudge.interface.server.executor import GraphExecutionEngine
from vejudge.interface.server.graph import EdgeSpec, GraphSpec, NodeSpec
from vejudge.interface.server.registry import (
    NODE_EXECUTORS,
    NodeExecutor,
    NodeRunContext,
    NodeRunResult,
    register,
)


@pytest.fixture(autouse=True)
def _clean_fake_types():
    yield
    for t in [t for t in NODE_EXECUTORS if t.startswith("__fx_")]:
        NODE_EXECUTORS.pop(t, None)


def _register(node_type, *, inputs=None, outputs=None, run_fn=None):
    class _Fake(NodeExecutor):
        input_sockets = inputs or {}
        output_sockets = outputs or {}

        def run(self, ctx: NodeRunContext) -> NodeRunResult:
            return run_fn(ctx) if run_fn else NodeRunResult(outputs={})

    _Fake.node_type = node_type
    _Fake.category = "node_db"
    return register(_Fake)


def test_linear_graph_passes_outputs_through(make_ctx):
    _register(
        "__fx_source__", outputs={"out": "dataset"},
        run_fn=lambda ctx: NodeRunResult(outputs={"out": "hello"}),
    )
    seen = {}

    def _sink_run(ctx):
        seen["value"] = ctx.inputs["in"]
        return NodeRunResult(outputs={})

    _register("__fx_sink__", inputs={"in": "dataset"}, run_fn=_sink_run)
    graph = GraphSpec(
        nodes=[NodeSpec(id="a", type="__fx_source__"), NodeSpec(id="b", type="__fx_sink__")],
        edges=[EdgeSpec("a", "out", "b", "in")],
    )
    ctx = make_ctx()
    engine = GraphExecutionEngine(graph, run=ctx.run, checkpoint=ctx.checkpoint)
    result = engine.execute()

    assert result.status == "done"
    assert seen["value"] == "hello"
    assert result.node_results["a"].status == "done"
    assert result.node_results["b"].status == "done"


def test_upstream_error_blocks_only_dependents(make_ctx):
    _register(
        "__fx_bad__", outputs={"out": "dataset"},
        run_fn=lambda ctx: NodeRunResult(status="error", error="boom"),
    )
    _register(
        "__fx_dependent__", inputs={"in": "dataset"},
        run_fn=lambda ctx: NodeRunResult(outputs={}),
    )
    _register(
        "__fx_independent__", run_fn=lambda ctx: NodeRunResult(outputs={}),
    )
    graph = GraphSpec(
        nodes=[
            NodeSpec(id="a", type="__fx_bad__"),
            NodeSpec(id="b", type="__fx_dependent__"),
            NodeSpec(id="c", type="__fx_independent__"),
        ],
        edges=[EdgeSpec("a", "out", "b", "in")],
    )
    ctx = make_ctx()
    engine = GraphExecutionEngine(graph, run=ctx.run, checkpoint=ctx.checkpoint)
    result = engine.execute()

    assert result.status == "error"
    assert result.node_results["a"].status == "error"
    assert result.node_results["b"].status == "error"
    assert "a" in result.node_results["b"].error
    assert result.node_results["c"].status == "done"  # unrelated branch still ran


def test_invalid_graph_short_circuits(make_ctx):
    graph = GraphSpec(
        nodes=[NodeSpec(id="a", type="__no_such_type__")], edges=[]
    )
    ctx = make_ctx()
    engine = GraphExecutionEngine(graph, run=ctx.run, checkpoint=ctx.checkpoint)
    result = engine.execute()
    assert result.status == "error"
    assert result.node_results == {}


def test_progress_cb_receives_node_status_events(make_ctx):
    _register("__fx_solo__", run_fn=lambda ctx: NodeRunResult(outputs={}))
    graph = GraphSpec(nodes=[NodeSpec(id="a", type="__fx_solo__")], edges=[])
    events = []
    ctx = make_ctx()
    engine = GraphExecutionEngine(
        graph, run=ctx.run, checkpoint=ctx.checkpoint,
        progress_cb=lambda event, payload: events.append((event, payload)),
    )
    engine.execute()
    statuses = [p["status"] for e, p in events if e == "node_status"]
    assert statuses == ["running", "done"]
