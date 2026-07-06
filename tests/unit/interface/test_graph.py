import pytest

from vejudge.interface.server.graph import (
    EdgeSpec,
    GraphError,
    GraphSpec,
    NodeSpec,
    NodeTypeInfo,
    topological_sort,
    validate_edges,
)

NODE_TYPES = {
    "dataset": NodeTypeInfo(input_sockets={}, output_sockets={"dataset": "dataset"}),
    "judge": NodeTypeInfo(
        input_sockets={"dataset": "dataset"}, output_sockets={"judge_result": "judge_result"}
    ),
    "eval": NodeTypeInfo(
        input_sockets={"judge_result": "judge_result", "labels": "labels"},
        output_sockets={"metrics_report": "metrics_report"},
    ),
}


def _linear_graph() -> GraphSpec:
    return GraphSpec(
        nodes=[
            NodeSpec(id="a", type="dataset"),
            NodeSpec(id="b", type="judge"),
        ],
        edges=[EdgeSpec(source="a", source_socket="dataset", target="b", target_socket="dataset")],
    )


def test_topological_sort_linear():
    assert topological_sort(_linear_graph()) == ["a", "b"]


def test_topological_sort_diamond():
    graph = GraphSpec(
        nodes=[
            NodeSpec(id="ds1", type="dataset"),
            NodeSpec(id="ds2", type="dataset"),
            NodeSpec(id="judge", type="judge"),
            NodeSpec(id="eval", type="eval"),
        ],
        edges=[
            EdgeSpec("ds1", "dataset", "judge", "dataset"),
            EdgeSpec("judge", "judge_result", "eval", "judge_result"),
            EdgeSpec("ds2", "dataset", "eval", "labels"),
        ],
    )
    order = topological_sort(graph)
    assert order.index("judge") > order.index("ds1")
    assert order.index("eval") > order.index("judge")
    assert order.index("eval") > order.index("ds2")


def test_topological_sort_detects_cycle():
    graph = GraphSpec(
        nodes=[NodeSpec(id="a", type="dataset"), NodeSpec(id="b", type="judge")],
        edges=[
            EdgeSpec("a", "dataset", "b", "dataset"),
            EdgeSpec("b", "judge_result", "a", "dataset"),
        ],
    )
    with pytest.raises(GraphError, match="cycle"):
        topological_sort(graph)


def test_topological_sort_rejects_duplicate_ids():
    graph = GraphSpec(nodes=[NodeSpec(id="a", type="dataset"), NodeSpec(id="a", type="judge")], edges=[])
    with pytest.raises(GraphError, match="Duplicate"):
        topological_sort(graph)


def test_validate_edges_ok():
    validate_edges(_linear_graph(), NODE_TYPES)  # no raise


def test_validate_edges_rejects_unknown_type_even_with_no_edges():
    # A node with zero edges must still have its type checked.
    graph = GraphSpec(nodes=[NodeSpec(id="a", type="not_a_type")], edges=[])
    with pytest.raises(GraphError, match="Unknown node type"):
        validate_edges(graph, NODE_TYPES)


def test_validate_edges_unknown_source_node():
    graph = GraphSpec(
        nodes=[NodeSpec(id="b", type="judge")],
        edges=[EdgeSpec("missing", "dataset", "b", "dataset")],
    )
    with pytest.raises(GraphError, match="unknown source node"):
        validate_edges(graph, NODE_TYPES)


def test_validate_edges_unknown_socket():
    graph = GraphSpec(
        nodes=[NodeSpec(id="a", type="dataset"), NodeSpec(id="b", type="judge")],
        edges=[EdgeSpec("a", "not_a_socket", "b", "dataset")],
    )
    with pytest.raises(GraphError, match="no output socket"):
        validate_edges(graph, NODE_TYPES)


def test_validate_edges_type_mismatch():
    graph = GraphSpec(
        nodes=[NodeSpec(id="j", type="judge"), NodeSpec(id="e", type="eval")],
        edges=[EdgeSpec("j", "judge_result", "e", "labels")],
    )
    with pytest.raises(GraphError, match="Type mismatch"):
        validate_edges(graph, NODE_TYPES)


def test_validate_edges_rejects_fan_in():
    graph = GraphSpec(
        nodes=[
            NodeSpec(id="ds1", type="dataset"),
            NodeSpec(id="ds2", type="dataset"),
            NodeSpec(id="j", type="judge"),
        ],
        edges=[
            EdgeSpec("ds1", "dataset", "j", "dataset"),
            EdgeSpec("ds2", "dataset", "j", "dataset"),
        ],
    )
    with pytest.raises(GraphError, match="fan-in"):
        validate_edges(graph, NODE_TYPES)
