import pytest

from vejudge.interface.server.registry import (
    NODE_EXECUTORS,
    NodeExecutor,
    NodeRunContext,
    NodeRunResult,
    node_type_infos,
    register,
)


def _make_fake_executor(node_type: str) -> type[NodeExecutor]:
    class _Fake(NodeExecutor):
        input_sockets: dict = {}
        output_sockets: dict = {"out": "dataset"}

        def run(self, ctx: NodeRunContext) -> NodeRunResult:
            return NodeRunResult(outputs={"out": "ok"})

    _Fake.node_type = node_type
    _Fake.category = "node_db"
    return register(_Fake)


def test_register_adds_to_node_executors():
    before = set(NODE_EXECUTORS)
    try:
        cls = _make_fake_executor("__fake_a__")
        assert NODE_EXECUTORS["__fake_a__"] is cls
    finally:
        NODE_EXECUTORS.pop("__fake_a__", None)
    assert set(NODE_EXECUTORS) == before


def test_register_rejects_duplicate_type():
    try:
        _make_fake_executor("__fake_dup__")
        with pytest.raises(ValueError, match="already registered"):
            _make_fake_executor("__fake_dup__")
    finally:
        NODE_EXECUTORS.pop("__fake_dup__", None)


def test_abstract_run_is_required():
    class _Incomplete(NodeExecutor):
        node_type = "__incomplete__"
        category = "node_db"

    with pytest.raises(TypeError):
        _Incomplete()  # can't instantiate without implementing run()


def test_node_type_infos_reflects_registered_sockets():
    try:
        _make_fake_executor("__fake_b__")
        infos = node_type_infos()
        assert infos["__fake_b__"].output_sockets == {"out": "dataset"}
        assert infos["__fake_b__"].input_sockets == {}
    finally:
        NODE_EXECUTORS.pop("__fake_b__", None)


def test_calibration_nodes_carry_their_role_subcategory_and_share_its_socket_contract():
    import vejudge.interface.node_types  # noqa: F401 - import side effect
    from vejudge.interface.node_calibration._templates import (
        CalibrationFitterNode,
        CalibrationProducerNode,
    )

    producer = NODE_EXECUTORS["cl_adversarial"]
    fitter = NODE_EXECUTORS["cl_rule_tree"]
    assert producer.subcategory == "agent"
    assert fitter.subcategory == "model"
    # "Unified I/O within a sub-category" is enforced by inheritance: a node reuses its
    # role template's socket dicts rather than declaring its own, so any new member of the
    # sub-category conforms by construction.
    assert producer.input_sockets is CalibrationProducerNode.input_sockets
    assert producer.output_sockets is CalibrationProducerNode.output_sockets
    assert fitter.input_sockets is CalibrationFitterNode.input_sockets
    assert fitter.output_sockets is CalibrationFitterNode.output_sockets


def test_non_subcategorized_nodes_default_to_none():
    import vejudge.interface.node_types  # noqa: F401 - import side effect

    assert NODE_EXECUTORS["judge"].subcategory is None
    assert NODE_EXECUTORS["eval"].subcategory is None


def test_only_the_in_scope_node_types_are_registered():
    import vejudge.interface.node_types  # noqa: F401 - import side effect

    real_types = {t for t in NODE_EXECUTORS if not t.startswith("__fake")}
    assert real_types == {
        "peanut_source", "coconut_source", "grapenut_source", "vebench_source",
        "dataset", "preprocessing", "lm_engine",
        "judge_prompt", "judge", "eval", "alignment_report", "cl_rule_eval",
        "cl_adversarial", "cl_rule_tree", "cl_semantic_tree",
        "unit_labels", "edit_decomposition", "area_rubric", "area_judge",
        "area_aggregation", "edit_aware_calibration", "imagenhub_source",
        "calitree_train", "rubric_lite_train", "rubric_lite_boundary",
        "calitree_judge", "calitree_eval",
    }
