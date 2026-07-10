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


def test_only_the_in_scope_node_types_are_registered():
    import vejudge.interface.node_types  # noqa: F401 - import side effect

    real_types = {t for t in NODE_EXECUTORS if not t.startswith("__fake")}
    assert real_types == {
        "peanut_source", "dataset", "preprocessing", "lm_engine",
        "judge_prompt", "judge", "eval",
    }
