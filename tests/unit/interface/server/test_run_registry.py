import time

import pytest

import vejudge.config as config
from vejudge.interface.server.graph import GraphSpec, NodeSpec
from vejudge.interface.server.registry import (
    NODE_EXECUTORS,
    NodeExecutor,
    NodeRunContext,
    NodeRunResult,
    register,
)
from vejudge.interface.server.run_manager import start_run
from vejudge.interface.server.run_registry import RunRegistry


@pytest.fixture(autouse=True)
def _clean_fake_types():
    yield
    for t in [t for t in NODE_EXECUTORS if t.startswith("__stopfx_")]:
        NODE_EXECUTORS.pop(t, None)


@pytest.fixture(autouse=True)
def _isolate_logs_root(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "LOGS_ROOT", tmp_path)


def _register_slow(node_type, delay=0.2):
    class _Slow(NodeExecutor):
        def run(self, ctx: NodeRunContext) -> NodeRunResult:
            time.sleep(delay)
            return NodeRunResult(outputs={})

    _Slow.node_type = node_type
    _Slow.category = "node_db"
    return register(_Slow)


def _register_marker(node_type, ran: list[str]):
    class _Marker(NodeExecutor):
        def run(self, ctx: NodeRunContext) -> NodeRunResult:
            ran.append(node_type)
            return NodeRunResult(outputs={})

    _Marker.node_type = node_type
    _Marker.category = "node_db"
    return register(_Marker)


def _wait_until_terminal(handle, timeout=5.0):
    deadline = time.time() + timeout
    while handle.status not in ("stopped", "done", "error") and time.time() < deadline:
        time.sleep(0.02)


def test_request_stop_on_unknown_run_id_returns_false():
    registry = RunRegistry()
    assert registry.request_stop("no-such-run") is False


def test_request_stop_halts_the_second_node_and_finishes_stopped():
    ran: list[str] = []
    _register_slow("__stopfx_slow__", delay=0.3)
    _register_marker("__stopfx_marker__", ran)
    graph = GraphSpec(
        nodes=[
            NodeSpec(id="a", type="__stopfx_slow__"),
            NodeSpec(id="b", type="__stopfx_marker__"),
        ],
        edges=[],
    )

    registry = RunRegistry()
    handle = registry.start(graph, dry_run=True, allow_live=False)
    time.sleep(0.05)  # let node "a" start (it sleeps 0.3s)
    assert handle.status == "running"
    assert registry.request_stop(handle.run_id) is True
    assert handle.status == "stopping"

    _wait_until_terminal(handle)

    assert handle.status == "stopped"
    assert ran == []  # node "b" never ran
    assert handle.result is not None
    assert handle.result.node_results["a"].status == "done"  # "a" finished on its own
    assert handle.result.node_results["b"].status == "stopped"


def test_try_claim_resume_dir_blocks_a_second_concurrent_claim(tmp_path):
    registry = RunRegistry()
    run_dir = tmp_path / "some-run-exps"
    assert registry.try_claim_resume_dir(run_dir) is True
    assert registry.try_claim_resume_dir(run_dir) is False  # already claimed
    registry.release_resume_dir(run_dir)
    assert registry.try_claim_resume_dir(run_dir) is True  # free again after release


def test_resumed_run_releases_its_claim_once_finished():
    _register_marker("__stopfx_resumeok__", [])
    graph = GraphSpec(nodes=[NodeSpec(id="a", type="__stopfx_resumeok__")], edges=[])

    # Materialize a real run dir the way a first run would, then "resume" it directly
    # through the registry (bypassing the HTTP layer, which is covered separately).
    run, _ = start_run(graph, dry_run=True, allow_live=False)
    run_dir = run.run_dir
    run.close()

    registry = RunRegistry()
    assert registry.try_claim_resume_dir(run_dir) is True
    handle = registry.start(graph, dry_run=True, allow_live=False, resume_from=run_dir)
    _wait_until_terminal(handle)
    assert handle.status == "done"
    # The background thread's own finally block should have released the claim.
    assert registry.try_claim_resume_dir(run_dir) is True


def test_request_stop_on_a_finished_run_returns_false():
    _register_marker("__stopfx_marker2__", [])
    graph = GraphSpec(nodes=[NodeSpec(id="a", type="__stopfx_marker2__")], edges=[])

    registry = RunRegistry()
    handle = registry.start(graph, dry_run=True, allow_live=False)
    _wait_until_terminal(handle)
    assert handle.status == "done"
    assert registry.request_stop(handle.run_id) is False
