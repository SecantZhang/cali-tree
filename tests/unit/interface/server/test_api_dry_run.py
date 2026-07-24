"""FastAPI TestClient coverage: palette, workflow round-trip, dry-run, live-call gating."""

import time

import pytest
from fastapi.testclient import TestClient

import vejudge.config as config
from vejudge.interface.server.app import create_app
from vejudge.lm_engine import openai_compat


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "WORKFLOWS_ROOT", tmp_path / "workflows")
    # Isolate from any real data/rendered-output/logs tree that might exist on this machine.
    monkeypatch.setattr(config, "DATA_ROOT", tmp_path / "data")
    monkeypatch.setattr(config, "RENDERED_ROOT", tmp_path / "rendered")
    monkeypatch.setattr(config, "LOGS_ROOT", tmp_path / "logs")
    return TestClient(create_app())


def _graph_body(*, dry_run=True, allow_live=False):
    # Minimal valid pipeline exercising the source -> sample -> judge chain (a Judge Node
    # can never be wired directly to a raw_dataset-producing source — see socketTypes.ts's
    # comment on why that split exists) plus the required engine_config input.
    return {
        "graph": {
            "nodes": [
                {"id": "src", "type": "peanut_source", "params": {}},
                {"id": "ds", "type": "dataset", "params": {}},
                {"id": "engine", "type": "lm_engine", "params": {}},
                {"id": "prompt", "type": "judge_prompt", "params": {"preset": "M1"}},
                {"id": "judge", "type": "judge", "params": {}},
            ],
            "edges": [
                {
                    "source": "src", "source_socket": "raw_dataset",
                    "target": "ds", "target_socket": "raw_dataset",
                },
                {
                    "source": "ds", "source_socket": "samples",
                    "target": "judge", "target_socket": "samples",
                },
                {
                    "source": "engine", "source_socket": "engine_config",
                    "target": "judge", "target_socket": "engine_config",
                },
                {
                    "source": "prompt", "source_socket": "judge_spec",
                    "target": "judge", "target_socket": "judge_spec",
                },
            ],
        },
        "dry_run": dry_run,
        "allow_live": allow_live,
    }


def test_list_node_types_returns_exactly_the_in_scope_set(client):
    resp = client.get("/api/nodes")
    assert resp.status_code == 200
    types = {n["type"] for n in resp.json()}
    assert types == {
        "peanut_source", "coconut_source", "grapenut_source", "vebench_source",
        "dataset", "preprocessing", "lm_engine",
        "judge_prompt", "judge", "eval", "alignment_report", "cl_rule_eval",
        "cl_adversarial", "cl_rule_tree", "cl_semantic_tree",
        "unit_labels", "edit_decomposition", "area_rubric", "area_judge",
        "area_aggregation", "edit_aware_calibration",
    }


def test_node_types_expose_calibration_subcategories(client):
    by_type = {n["type"]: n for n in client.get("/api/nodes").json()}
    assert by_type["cl_adversarial"]["subcategory"] == "agent"
    assert by_type["cl_rule_tree"]["subcategory"] == "model"
    assert by_type["cl_semantic_tree"]["subcategory"] == "model"
    assert by_type["cl_adversarial"]["multi_input_sockets"] == ["judge_result"]
    assert by_type["cl_semantic_tree"]["multi_input_sockets"] == ["calibration_results"]
    # Nodes outside a sub-folder report null, so the palette renders them flat.
    assert by_type["judge"]["subcategory"] is None


def test_workflow_save_load_round_trip(client):
    body = {"name": "quick_eval", "graph": _graph_body()["graph"]}
    resp = client.post("/api/workflows", json=body)
    assert resp.status_code == 200
    assert resp.json()["name"] == "quick_eval"

    resp = client.get("/api/workflows")
    assert resp.json() == ["quick_eval"]

    resp = client.get("/api/workflows/quick_eval")
    assert resp.status_code == 200
    assert resp.json()["graph"]["nodes"][0]["id"] == "src"

    resp = client.delete("/api/workflows/quick_eval")
    assert resp.status_code == 200
    assert client.get("/api/workflows").json() == []


def test_workflow_save_load_round_trips_position_and_size(client):
    graph = _graph_body()["graph"]
    graph["nodes"][0]["position"] = {"x": 12.5, "y": 34.0}
    graph["nodes"][0]["size"] = {"width": 220.0, "height": 140.0}
    # The other nodes have no layout yet (an older-shaped save, or never-moved node) —
    # position/size must stay optional, not required on every node.
    resp = client.post("/api/workflows", json={"name": "with_layout", "graph": graph})
    assert resp.status_code == 200

    resp = client.get("/api/workflows/with_layout")
    nodes = {n["id"]: n for n in resp.json()["graph"]["nodes"]}
    assert nodes["src"]["position"] == {"x": 12.5, "y": 34.0}
    assert nodes["src"]["size"] == {"width": 220.0, "height": 140.0}
    assert nodes["judge"]["position"] is None
    assert nodes["judge"]["size"] is None


def test_workflow_save_load_round_trips_cosmetic_view_state(client):
    # Purely cosmetic "what this node looked like last time" fields — wire-layer only,
    # same category as position/size, never touched by graph execution.
    graph = _graph_body()["graph"]
    graph["nodes"][0]["status"] = "error"
    graph["nodes"][0]["error"] = "boom"
    graph["nodes"][0]["collapsed"] = True
    graph["nodes"][0]["expanded_size"] = {"width": 300.0, "height": 220.0}
    graph["nodes"][0]["stale"] = True
    resp = client.post("/api/workflows", json={"name": "with_view_state", "graph": graph})
    assert resp.status_code == 200

    resp = client.get("/api/workflows/with_view_state")
    node = {n["id"]: n for n in resp.json()["graph"]["nodes"]}["src"]
    assert node["status"] == "error"
    assert node["error"] == "boom"
    assert node["collapsed"] is True
    assert node["expanded_size"] == {"width": 300.0, "height": 220.0}
    assert node["stale"] is True


def test_workflow_save_load_round_trips_locked_and_groups(client):
    # Both are wire-layer only (never touched by execution) but must survive save/load:
    # `locked` on a node, and a top-level `groups` array (without the GraphIn.groups field
    # a saved `groups` would be silently dropped, since models default to extra="ignore").
    graph = _graph_body()["graph"]
    graph["nodes"][0]["locked"] = True
    graph["groups"] = [
        {"id": "group-1", "title": "Data prep", "position": {"x": 10.0, "y": 20.0},
         "size": {"width": 400.0, "height": 300.0}},
    ]
    resp = client.post("/api/workflows", json={"name": "with_groups", "graph": graph})
    assert resp.status_code == 200

    loaded = client.get("/api/workflows/with_groups").json()["graph"]
    assert {n["id"]: n for n in loaded["nodes"]}["src"]["locked"] is True
    assert loaded["groups"] == [
        {"id": "group-1", "title": "Data prep", "position": {"x": 10.0, "y": 20.0},
         "size": {"width": 400.0, "height": 300.0}},
    ]


def test_workflow_rejects_unsafe_name(client):
    body = {"name": "../../etc/passwd", "graph": _graph_body()["graph"]}
    resp = client.post("/api/workflows", json=body)
    assert resp.status_code == 400


def test_graph_validate_endpoint(client):
    resp = client.post("/api/graph/validate", json=_graph_body()["graph"])
    assert resp.status_code == 200
    # Kahn's algorithm with deterministic tie-break by node id: the three indegree-0 nodes
    # (engine, prompt, src) come first in id order, then ds, then judge.
    assert resp.json()["order"] == ["engine", "prompt", "src", "ds", "judge"]


def test_graph_validate_rejects_bad_edge(client):
    bad = _graph_body()["graph"]
    bad["edges"][0]["target_socket"] = "nope"
    resp = client.post("/api/graph/validate", json=bad)
    assert resp.status_code == 400


def _wait_for_run(client, run_id, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = client.get(f"/api/runs/{run_id}")
        if resp.json()["status"] != "running":
            return resp.json()
        time.sleep(0.02)
    raise AssertionError("run did not finish in time")


def _wait_for_terminal(client, run_id, timeout=5.0):
    """Like _wait_for_run, but waits past "stopping" too, for a genuinely final status."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = client.get(f"/api/runs/{run_id}")
        if resp.json()["status"] in ("done", "error", "stopped"):
            return resp.json()
        time.sleep(0.02)
    raise AssertionError("run did not reach a terminal status in time")


def test_dry_run_makes_zero_gateway_calls(client, monkeypatch):
    def boom(**kwargs):
        raise AssertionError("dry-run must never call the gateway")

    monkeypatch.setattr(openai_compat, "chat_completion", boom)

    resp = client.post("/api/runs", json=_graph_body(dry_run=True))
    assert resp.status_code == 200
    run_id = resp.json()["run_id"]
    final = _wait_for_run(client, run_id)

    assert final["status"] == "done"
    assert final["node_results"]["judge"]["meta"]["dry_run"] is True


def test_live_run_rejected_without_allow_live(client):
    resp = client.post("/api/runs", json=_graph_body(dry_run=False, allow_live=False))
    assert resp.status_code == 200
    run_id = resp.json()["run_id"]
    final = _wait_for_run(client, run_id)

    assert final["status"] == "error"
    assert "--live" in final["node_results"]["judge"]["error"]


def test_ws_streams_node_status_then_run_complete(client):
    resp = client.post("/api/runs", json=_graph_body(dry_run=True))
    run_id = resp.json()["run_id"]

    # A dry run can finish before the WS even connects — the resync message alone
    # (status != "running") is then the terminal signal; the socket closes right after.
    with client.websocket_connect(f"/api/runs/{run_id}/ws") as ws:
        events = [ws.receive_json()]
        assert events[0]["type"] == "resync"
        if events[0]["status"] == "running":
            while events[-1]["type"] != "run_complete":
                events.append(ws.receive_json())
            assert events[-1] == {"type": "run_complete", "status": "done", "error": None}
            assert any(e["type"] == "node_status" for e in events)
        else:
            assert events[0]["status"] == "done"


def test_workflow_name_is_tagged_and_listed(client):
    resp = client.post("/api/runs", json={**_graph_body(dry_run=True), "workflow_name": "my_wf"})
    run_id = resp.json()["run_id"]
    _wait_for_run(client, run_id)

    resp = client.get("/api/workflows/my_wf/runs")
    assert resp.status_code == 200
    runs = resp.json()
    assert len(runs) == 1
    assert runs[0]["run_id"] == run_id
    assert runs[0]["status"] == "done"
    assert runs[0]["dry_run"] is True


def test_list_workflow_runs_empty_for_unknown_workflow(client):
    resp = client.get("/api/workflows/never-ran/runs")
    assert resp.status_code == 200
    assert resp.json() == []


def test_resume_reconstructs_graph_from_saved_run_and_tags_same_workflow(client):
    body = {**_graph_body(dry_run=True), "workflow_name": "resumable_wf"}
    resp = client.post("/api/runs", json=body)
    original_run_id = resp.json()["run_id"]
    _wait_for_run(client, original_run_id)

    # A resume reuses the original directory but always gets a distinct attempt id, even
    # when an immediate hard Stop/Resume happens within the same wall-clock second.
    resp = client.post("/api/runs", json={"resume_from": original_run_id})
    assert resp.status_code == 200
    resumed_run_id = resp.json()["run_id"]
    assert resumed_run_id != original_run_id
    final = _wait_for_run(client, resumed_run_id)
    assert final["status"] == "done"
    assert "src" in final["node_results"]
    assert "judge" in final["node_results"]

    # The resume reopened the SAME run directory (that's the point — same checkpoint) —
    # the listing is keyed by directory, so it reports exactly one entry, under the
    # *original* run_id (the one that names the directory), reflecting the latest status.
    resp = client.get("/api/workflows/resumable_wf/runs")
    runs = resp.json()
    assert len(runs) == 1
    assert runs[0]["run_id"] == original_run_id
    assert runs[0]["status"] == "done"


def test_workflow_runs_listing_reflects_a_resumes_final_status_not_the_original(client):
    # A resume gets its own fresh run_id/handle sharing the original's directory — the
    # ORIGINAL run_id's own in-memory handle never learns the resume finished "done"; it's
    # frozen at "stopped" forever. The listing must not report that stale value.
    import tests.hard_stop_nodes as hard_stop_nodes
    from vejudge.interface.server.registry import NODE_EXECUTORS
    from vejudge.interface.server.run_registry import REGISTRY

    hard_stop_nodes.register_worker_nodes()
    old_imports = list(REGISTRY.worker_imports)
    REGISTRY.worker_imports = [*old_imports, "tests.hard_stop_nodes"]
    try:
        # Two nodes so the between-nodes stop check (executor.py) has a second node left
        # to mark "stopped" once should_stop() flips true while the first is still running.
        graph = {
            "nodes": [
                {"id": "a", "type": "__wf_slow__", "params": {"delay": 3.0}},
                {"id": "b", "type": "__wf_marker__", "params": {}},
            ],
            "edges": [],
        }
        resp = client.post(
            "/api/runs",
            json={"graph": graph, "dry_run": True, "workflow_name": "wf_resume_status"},
        )
        run_id = resp.json()["run_id"]
        time.sleep(0.2)  # let the spawned worker enter the slow node
        t0 = time.perf_counter()
        stopped = client.post(f"/api/runs/{run_id}/stop")
        assert time.perf_counter() - t0 < 0.5
        assert stopped.json()["status"] == "stopped"
        assert _wait_for_terminal(client, run_id)["status"] == "stopped"

        resp = client.post("/api/runs", json={"resume_from": run_id})
        resumed_id = resp.json()["run_id"]
        assert resumed_id != run_id
        assert _wait_for_terminal(client, resumed_id)["status"] == "done"

        resp = client.get("/api/workflows/wf_resume_status/runs")
        runs = resp.json()
        assert len(runs) == 1
        assert runs[0]["run_id"] == run_id  # keyed by directory == original run_id
        assert runs[0]["status"] == "done"  # the resume's outcome, not the stale "stopped"
    finally:
        REGISTRY.worker_imports = old_imports
        NODE_EXECUTORS.pop("__wf_slow__", None)
        NODE_EXECUTORS.pop("__wf_marker__", None)
        NODE_EXECUTORS.pop("__stopfx_slow__", None)
        NODE_EXECUTORS.pop("__stopfx_marker__", None)
        NODE_EXECUTORS.pop("__stopfx_resumeok__", None)
        NODE_EXECUTORS.pop("__stopfx_marker2__", None)
        NODE_EXECUTORS.pop("__stopfx_checkpoint_sleep__", None)


def test_resume_unknown_run_id_returns_404(client):
    resp = client.post("/api/runs", json={"resume_from": "no-such-run"})
    assert resp.status_code == 404


def test_run_without_graph_or_resume_from_returns_400(client):
    resp = client.post("/api/runs", json={"dry_run": True})
    assert resp.status_code == 400


def test_stop_unknown_run_id_returns_404(client):
    resp = client.post("/api/runs/no-such-run/stop")
    assert resp.status_code == 404


def test_stop_an_already_finished_run_returns_409(client):
    resp = client.post("/api/runs", json=_graph_body(dry_run=True))
    run_id = resp.json()["run_id"]
    _wait_for_run(client, run_id)

    resp = client.post(f"/api/runs/{run_id}/stop")
    assert resp.status_code == 409


def test_ws_unknown_run_id_reports_error(client):
    with client.websocket_connect("/api/runs/does-not-exist/ws") as ws:
        event = ws.receive_json()
    assert event["type"] == "error"
