import time

import pytest

import vejudge.config as config
from vejudge.checkpoint import CheckpointStore
from vejudge.interface.server.graph import GraphSpec, NodeSpec
from vejudge.interface.server.run_manager import start_run
from vejudge.interface.server.run_registry import RunRegistry


@pytest.fixture(autouse=True)
def _isolate_logs_root(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "LOGS_ROOT", tmp_path)


def _wait_until_terminal(handle, timeout=5.0):
    deadline = time.time() + timeout
    while handle.status not in ("stopped", "done", "error") and time.time() < deadline:
        time.sleep(0.02)
    if handle.monitor_thread is not None:
        handle.monitor_thread.join(timeout=max(0.0, deadline - time.time()))


def test_request_stop_on_unknown_run_id_returns_false():
    registry = RunRegistry()
    assert registry.request_stop("no-such-run") is False


def test_request_stop_halts_the_second_node_and_finishes_stopped():
    graph = GraphSpec(
        nodes=[
            NodeSpec(id="a", type="__stopfx_slow__", params={"delay": 3.0}),
            NodeSpec(id="b", type="__stopfx_marker__"),
        ],
        edges=[],
    )

    registry = RunRegistry(worker_imports=["tests.hard_stop_nodes"])
    handle = registry.start(graph, dry_run=True, allow_live=False)
    time.sleep(0.2)  # let the spawned worker enter node "a"
    assert handle.status == "running"
    t0 = time.perf_counter()
    assert registry.request_stop(handle.run_id) is True
    elapsed = time.perf_counter() - t0
    assert handle.status == "stopped"
    assert elapsed < 0.5

    _wait_until_terminal(handle)

    assert handle.status == "stopped"
    assert handle.result is not None
    assert handle.result.node_results["a"].status == "stopped"
    assert handle.result.node_results["b"].status == "stopped"
    assert registry.request_stop(handle.run_id) is False

    deadline = time.time() + 2.0
    while handle.process is not None and handle.process.is_alive() and time.time() < deadline:
        time.sleep(0.01)
    assert handle.process is not None and not handle.process.is_alive()


def test_hard_stop_preserves_flushed_checkpoint_but_not_interrupted_work():
    graph = GraphSpec(nodes=[
        NodeSpec(
            id="a", type="__stopfx_checkpoint_sleep__", params={"delay": 3.0},
        ),
    ], edges=[])
    registry = RunRegistry(worker_imports=["tests.hard_stop_nodes"])
    handle = registry.start(graph, dry_run=True, allow_live=False)
    checkpoint_path = handle.run.run_dir / "judge_results.jsonl"

    deadline = time.time() + 2.0
    while (not checkpoint_path.is_file() or checkpoint_path.stat().st_size == 0) and time.time() < deadline:
        time.sleep(0.01)
    assert checkpoint_path.is_file()
    assert registry.request_stop(handle.run_id) is True

    checkpoint = CheckpointStore(checkpoint_path)
    assert checkpoint.get("completed-before-stop") == {"ok": True}
    assert not checkpoint.has("must-not-exist-after-stop")


def test_try_claim_resume_dir_blocks_a_second_concurrent_claim(tmp_path):
    registry = RunRegistry()
    run_dir = tmp_path / "some-run-exps"
    assert registry.try_claim_resume_dir(run_dir) is True
    assert registry.try_claim_resume_dir(run_dir) is False  # already claimed
    registry.release_resume_dir(run_dir)
    assert registry.try_claim_resume_dir(run_dir) is True  # free again after release


def test_resumed_run_releases_its_claim_once_finished():
    graph = GraphSpec(nodes=[NodeSpec(id="a", type="__stopfx_resumeok__")], edges=[])

    # Materialize a real run dir the way a first run would, then "resume" it directly
    # through the registry (bypassing the HTTP layer, which is covered separately).
    run, _ = start_run(graph, dry_run=True, allow_live=False)
    run_dir = run.run_dir
    run.close()

    registry = RunRegistry(worker_imports=["tests.hard_stop_nodes"])
    assert registry.try_claim_resume_dir(run_dir) is True
    handle = registry.start(graph, dry_run=True, allow_live=False, resume_from=run_dir)
    _wait_until_terminal(handle)
    assert handle.status == "done"
    assert handle.result is not None
    assert handle.result.node_results["a"].outputs == {"resumed": True}
    event_types = []
    while not handle.events.empty():
        event_types.append(handle.events.get_nowait()["type"])
    assert "run_order" in event_types
    assert "node_status" in event_types
    assert "run_complete" in event_types
    # The worker monitor should have released the claim.
    assert registry.try_claim_resume_dir(run_dir) is True


def test_request_stop_on_a_finished_run_returns_false():
    graph = GraphSpec(nodes=[NodeSpec(id="a", type="__stopfx_marker2__")], edges=[])

    registry = RunRegistry(worker_imports=["tests.hard_stop_nodes"])
    handle = registry.start(graph, dry_run=True, allow_live=False)
    _wait_until_terminal(handle)
    assert handle.status == "done"
    assert registry.request_stop(handle.run_id) is False
