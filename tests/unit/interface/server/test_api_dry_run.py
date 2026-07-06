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
    return {
        "graph": {
            "nodes": [
                {"id": "ds", "type": "dataset", "params": {"loader": "peanut_eval"}},
                {"id": "judge", "type": "judge", "params": {"metrics": ["M1"]}},
            ],
            "edges": [
                {
                    "source": "ds", "source_socket": "dataset",
                    "target": "judge", "target_socket": "dataset",
                }
            ],
        },
        "dry_run": dry_run,
        "allow_live": allow_live,
    }


def test_list_node_types_returns_exactly_the_3_in_scope(client):
    resp = client.get("/api/nodes")
    assert resp.status_code == 200
    types = {n["type"] for n in resp.json()}
    assert types == {"dataset", "judge", "eval"}


def test_workflow_save_load_round_trip(client):
    body = {"name": "quick_eval", "graph": _graph_body()["graph"]}
    resp = client.post("/api/workflows", json=body)
    assert resp.status_code == 200
    assert resp.json()["name"] == "quick_eval"

    resp = client.get("/api/workflows")
    assert resp.json() == ["quick_eval"]

    resp = client.get("/api/workflows/quick_eval")
    assert resp.status_code == 200
    assert resp.json()["graph"]["nodes"][0]["id"] == "ds"

    resp = client.delete("/api/workflows/quick_eval")
    assert resp.status_code == 200
    assert client.get("/api/workflows").json() == []


def test_workflow_rejects_unsafe_name(client):
    body = {"name": "../../etc/passwd", "graph": _graph_body()["graph"]}
    resp = client.post("/api/workflows", json=body)
    assert resp.status_code == 400


def test_graph_validate_endpoint(client):
    resp = client.post("/api/graph/validate", json=_graph_body()["graph"])
    assert resp.status_code == 200
    assert resp.json()["order"] == ["ds", "judge"]


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


def test_ws_unknown_run_id_reports_error(client):
    with client.websocket_connect("/api/runs/does-not-exist/ws") as ws:
        event = ws.receive_json()
    assert event["type"] == "error"
