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


def test_should_stop_halts_before_remaining_nodes(make_ctx):
    ran = []
    _register("__fx_a__", run_fn=lambda ctx: (ran.append("a"), NodeRunResult(outputs={}))[1])
    _register("__fx_b__", run_fn=lambda ctx: (ran.append("b"), NodeRunResult(outputs={}))[1])
    graph = GraphSpec(
        nodes=[NodeSpec(id="a", type="__fx_a__"), NodeSpec(id="b", type="__fx_b__")], edges=[],
    )
    ctx = make_ctx()
    # Stop is already requested before the run even starts — the first node ("a") should
    # never execute, and both nodes end up marked "stopped".
    engine = GraphExecutionEngine(
        graph, run=ctx.run, checkpoint=ctx.checkpoint, should_stop=lambda: True,
    )
    result = engine.execute()

    assert result.status == "stopped"
    assert ran == []
    assert result.node_results["a"].status == "stopped"
    assert result.node_results["b"].status == "stopped"


def test_should_stop_lets_a_node_already_running_finish(make_ctx):
    ran = []
    _register("__fx_a__", run_fn=lambda ctx: (ran.append("a"), NodeRunResult(outputs={}))[1])
    _register("__fx_b__", run_fn=lambda ctx: (ran.append("b"), NodeRunResult(outputs={}))[1])
    graph = GraphSpec(
        nodes=[NodeSpec(id="a", type="__fx_a__"), NodeSpec(id="b", type="__fx_b__")], edges=[],
    )
    ctx = make_ctx()
    # Stop only becomes true after "a" has already been checked — "a" still runs to
    # completion (it was already past the stop check for this iteration), "b" is stopped.
    calls = {"n": 0}

    def _should_stop():
        calls["n"] += 1
        return calls["n"] > 1

    engine = GraphExecutionEngine(
        graph, run=ctx.run, checkpoint=ctx.checkpoint, should_stop=_should_stop,
    )
    result = engine.execute()

    assert result.status == "stopped"
    assert ran == ["a"]
    assert result.node_results["a"].status == "done"
    assert result.node_results["b"].status == "stopped"


def test_error_status_is_not_overwritten_by_a_later_stop(make_ctx):
    _register(
        "__fx_bad__", run_fn=lambda ctx: NodeRunResult(status="error", error="boom"),
    )
    _register("__fx_b__", run_fn=lambda ctx: NodeRunResult(outputs={}))
    graph = GraphSpec(
        nodes=[NodeSpec(id="a", type="__fx_bad__"), NodeSpec(id="b", type="__fx_b__")], edges=[],
    )
    ctx = make_ctx()
    calls = {"n": 0}

    def _should_stop():
        calls["n"] += 1
        return calls["n"] > 1  # stop kicks in only before node "b"

    engine = GraphExecutionEngine(
        graph, run=ctx.run, checkpoint=ctx.checkpoint, should_stop=_should_stop,
    )
    result = engine.execute()

    assert result.status == "error"  # error takes priority over a later stop
    assert result.node_results["a"].status == "error"
    assert result.node_results["b"].status == "stopped"


def test_on_batch_triggers_a_preview_of_a_supports_partial_input_downstream_node(make_ctx):
    _register(
        "__fx_driver__", outputs={"out": "judge_result"},
        run_fn=lambda ctx: (ctx.on_batch("out", {"a": 1}), NodeRunResult(outputs={"out": {"a": 1, "b": 2}}))[1],
    )
    seen_inputs = []

    class _Sink(NodeExecutor):
        node_type = "__fx_sink__"
        category = "node_eval"
        input_sockets = {"in": "judge_result"}
        supports_partial_input = True

        def run(self, ctx):
            seen_inputs.append(ctx.inputs["in"])
            return NodeRunResult(outputs={"report": len(ctx.inputs["in"])}, meta={"preview": ctx.is_preview})

    register(_Sink)
    graph = GraphSpec(
        nodes=[NodeSpec(id="a", type="__fx_driver__"), NodeSpec(id="b", type="__fx_sink__")],
        edges=[EdgeSpec("a", "out", "b", "in")],
    )
    events = []
    ctx = make_ctx()
    engine = GraphExecutionEngine(
        graph, run=ctx.run, checkpoint=ctx.checkpoint,
        progress_cb=lambda event, payload: events.append((event, payload)),
    )
    result = engine.execute()

    assert result.status == "done"
    # "b" is called twice: once for the preview (the in-flight batch value), once more for
    # its own normal, authoritative run at its regular topological position (against node
    # "a"'s eventual, final output) — the preview is a pure side effect, not a replacement.
    assert seen_inputs == [{"a": 1}, {"a": 1, "b": 2}]
    partials = [p for e, p in events if e == "partial_result"]
    # Two partial_result events per on_batch call: the calling node's own in-flight
    # snapshot (so e.g. a Judge Node's own secondary tab can render live), plus the
    # existing downstream-preview mechanism (unchanged).
    assert len(partials) == 2
    assert partials[0] == {"node_id": "a", "outputs": {"out": {"a": 1}}, "meta": {}}
    assert partials[1] == {"node_id": "b", "outputs": {"report": 1}, "meta": {"preview": True}}
    # Node "b"'s own, normal, authoritative run afterward is completely unaffected — it
    # still runs once, at its regular topological position, against the real final input.
    assert result.node_results["b"].outputs == {"report": 2}
    assert result.node_results["b"].meta == {"preview": False}


def test_on_batch_is_a_no_op_downstream_for_a_node_that_does_not_opt_in(make_ctx):
    _register(
        "__fx_driver__", outputs={"out": "judge_result"},
        run_fn=lambda ctx: (ctx.on_batch("out", {"a": 1}), NodeRunResult(outputs={"out": {}}))[1],
    )
    _register(
        "__fx_plain_sink__", inputs={"in": "judge_result"}, run_fn=lambda ctx: NodeRunResult(outputs={}),
    )
    graph = GraphSpec(
        nodes=[NodeSpec(id="a", type="__fx_driver__"), NodeSpec(id="b", type="__fx_plain_sink__")],
        edges=[EdgeSpec("a", "out", "b", "in")],
    )
    events = []
    ctx = make_ctx()
    engine = GraphExecutionEngine(
        graph, run=ctx.run, checkpoint=ctx.checkpoint,
        progress_cb=lambda event, payload: events.append((event, payload)),
    )
    result = engine.execute()

    assert result.status == "done"
    # The calling node "a" still emits its own snapshot (see the dedicated test below) —
    # only the downstream, non-opted-in "b" gets no preview event of its own.
    assert [p for e, p in events if e == "partial_result" and p["node_id"] == "b"] == []


def test_on_batch_always_emits_the_calling_nodes_own_snapshot(make_ctx):
    # Independent of whether anything downstream opts into previews at all — this is what
    # lets e.g. a Judge Node's own secondary tab render a live-updating view of its own
    # in-flight results, not just downstream nodes'.
    _register(
        "__fx_solo_driver__", outputs={"out": "judge_result"},
        run_fn=lambda ctx: (ctx.on_batch("out", {"a": 1}), NodeRunResult(outputs={"out": {"a": 1, "b": 2}}))[1],
    )
    graph = GraphSpec(nodes=[NodeSpec(id="a", type="__fx_solo_driver__")], edges=[])
    events = []
    ctx = make_ctx()
    engine = GraphExecutionEngine(
        graph, run=ctx.run, checkpoint=ctx.checkpoint,
        progress_cb=lambda event, payload: events.append((event, payload)),
    )
    result = engine.execute()

    assert result.status == "done"
    partials = [p for e, p in events if e == "partial_result"]
    assert partials == [{"node_id": "a", "outputs": {"out": {"a": 1}}, "meta": {}}]


def test_on_batch_skips_a_downstream_node_whose_other_input_is_not_ready_yet(make_ctx):
    _register(
        "__fx_driver__", outputs={"out": "judge_result"},
        run_fn=lambda ctx: (ctx.on_batch("out", {"a": 1}), NodeRunResult(outputs={"out": {}}))[1],
    )

    class _NeedsTwo(NodeExecutor):
        node_type = "__fx_needs_two__"
        category = "node_eval"
        input_sockets = {"judge_result": "judge_result", "labels": "labels"}
        supports_partial_input = True

        def run(self, ctx):
            # Mirrors EvalNodeExecutor's own real validation: a declared input socket
            # that was never wired at all is simply absent from ctx.inputs, not None-filled
            # by the executor — each node validates its own required inputs.
            if ctx.inputs.get("labels") is None:
                return NodeRunResult(status="error", error="missing labels")
            return NodeRunResult(outputs={})

    register(_NeedsTwo)
    # "b" also needs a "labels" input that never gets wired — the preview must be skipped
    # entirely rather than calling the downstream node with a missing socket.
    graph = GraphSpec(
        nodes=[NodeSpec(id="a", type="__fx_driver__"), NodeSpec(id="b", type="__fx_needs_two__")],
        edges=[EdgeSpec("a", "out", "b", "judge_result")],
    )
    events = []
    ctx = make_ctx()
    engine = GraphExecutionEngine(
        graph, run=ctx.run, checkpoint=ctx.checkpoint,
        progress_cb=lambda event, payload: events.append((event, payload)),
    )
    result = engine.execute()

    # "b" is missing its "labels" input for real, so its own authoritative run errors —
    # that's an unrelated, pre-existing behavior; the point here is just that no preview
    # was attempted for it while that input was still missing (the calling node "a" still
    # emits its own snapshot regardless — see test_on_batch_always_emits_the_calling_nodes_own_snapshot).
    assert result.node_results["b"].status == "error"
    assert [p for e, p in events if e == "partial_result" and p["node_id"] == "b"] == []


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
