"""Per-node Run (ancestors mode) / Re-run (self_only mode) — scoped graph execution."""

import time

import pytest
from fastapi.testclient import TestClient

import vejudge.config as config
from vejudge.interface.server.app import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "WORKFLOWS_ROOT", tmp_path / "workflows")
    monkeypatch.setattr(config, "DATA_ROOT", tmp_path / "data")
    monkeypatch.setattr(config, "RENDERED_ROOT", tmp_path / "rendered")
    monkeypatch.setattr(config, "LOGS_ROOT", tmp_path / "logs")
    return TestClient(create_app())


def _graph():
    # src -> ds -> judge (+ engine + prompt) -> eval (+ ds.labels), with judge as a real
    # fan-in point (3 upstream deps) — enough to exercise ancestor-closure reduction
    # meaningfully (judge's own closure is {src, ds, engine, prompt, judge}, excluding eval).
    return {
        "nodes": [
            {"id": "src", "type": "peanut_source", "params": {}},
            {"id": "ds", "type": "dataset", "params": {}},
            {"id": "engine", "type": "lm_engine", "params": {}},
            {"id": "prompt", "type": "judge_prompt", "params": {"preset": "M1"}},
            {"id": "judge", "type": "judge", "params": {}},
            {"id": "eval", "type": "eval", "params": {}},
        ],
        "edges": [
            {"source": "src", "source_socket": "raw_dataset", "target": "ds", "target_socket": "raw_dataset"},
            {"source": "ds", "source_socket": "samples", "target": "judge", "target_socket": "samples"},
            {"source": "engine", "source_socket": "engine_config", "target": "judge", "target_socket": "engine_config"},
            {"source": "prompt", "source_socket": "judge_spec", "target": "judge", "target_socket": "judge_spec"},
            {"source": "judge", "source_socket": "judge_result", "target": "eval", "target_socket": "judge_result"},
            {"source": "ds", "source_socket": "labels", "target": "eval", "target_socket": "labels"},
        ],
    }


def _wait_for_run(client, run_id, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = client.get(f"/api/runs/{run_id}")
        if resp.json()["status"] != "running":
            return resp.json()
        time.sleep(0.02)
    raise AssertionError("run did not finish in time")


def _start(client, **overrides):
    body = {"graph": _graph(), "dry_run": True, "allow_live": False, **overrides}
    resp = client.post("/api/runs", json=body)
    assert resp.status_code == 200, resp.text
    return resp.json()["run_id"]


def test_run_mode_ancestors_only_executes_target_and_its_ancestors(client):
    run_id = _start(client, run_mode="ancestors", target_node_id="judge")
    final = _wait_for_run(client, run_id)
    assert final["status"] == "done"
    assert set(final["node_results"]) == {"src", "ds", "engine", "prompt", "judge"}
    # `order` (the REST mirror of the `run_order` WS event — see GraphRunResult.order) is
    # this run's real scope, so the frontend's order badge is populated even for a run that
    # finishes before its websocket ever connects.
    assert set(final["order"]) == {"src", "ds", "engine", "prompt", "judge"}
    assert "eval" not in final["order"]


def test_run_mode_ancestors_missing_target_node_id_returns_400(client):
    resp = client.post("/api/runs", json={"graph": _graph(), "dry_run": True, "run_mode": "ancestors"})
    assert resp.status_code == 400
    assert "target_node_id" in resp.json()["detail"]


def test_run_mode_self_only_reuses_seed_results_for_ancestors(client):
    seed_run_id = _start(client)  # full graph, normal run
    seed_final = _wait_for_run(client, seed_run_id)
    assert seed_final["status"] == "done"

    run_id = _start(
        client, run_mode="self_only", target_node_id="judge", seed_run_id=seed_run_id,
    )
    final = _wait_for_run(client, run_id)
    assert final["status"] == "done"
    # Every node's result is present (seeded ones carried over, judge freshly computed) —
    # not just the target, since the frontend reconstructs the whole picture from this.
    assert set(final["node_results"]) == {"src", "ds", "engine", "prompt", "judge", "eval"}
    # But `order` (this run's real *executed* scope) is just the target — the seeded nodes
    # never actually ran, so they must not appear here even though their results do above.
    assert final["order"] == ["judge"]
    # The seeded (non-target) nodes' outputs are exactly what the seed run produced, not
    # recomputed — proof this really reused them instead of quietly re-running everything.
    assert final["node_results"]["src"] == seed_final["node_results"]["src"]
    assert final["node_results"]["ds"] == seed_final["node_results"]["ds"]


def test_run_mode_self_only_missing_seed_run_id_returns_400(client):
    resp = client.post(
        "/api/runs",
        json={"graph": _graph(), "dry_run": True, "run_mode": "self_only", "target_node_id": "judge"},
    )
    assert resp.status_code == 400
    assert "seed_run_id" in resp.json()["detail"]


def test_run_mode_self_only_unknown_seed_run_returns_404(client):
    resp = client.post(
        "/api/runs",
        json={
            "graph": _graph(), "dry_run": True, "run_mode": "self_only",
            "target_node_id": "judge", "seed_run_id": "no-such-run",
        },
    )
    assert resp.status_code == 404


def test_run_mode_self_only_seed_run_missing_ancestor_coverage_returns_400(client):
    # A seed run that only ever covered a single unrelated node — nowhere near enough to
    # satisfy "judge"'s real dependencies (src/ds/engine).
    lone_graph = {"nodes": [{"id": "engine", "type": "lm_engine", "params": {}}], "edges": []}
    seed_run_id = client.post(
        "/api/runs", json={"graph": lone_graph, "dry_run": True}
    ).json()["run_id"]
    _wait_for_run(client, seed_run_id)

    resp = client.post(
        "/api/runs",
        json={
            "graph": _graph(), "dry_run": True, "run_mode": "self_only",
            "target_node_id": "judge", "seed_run_id": seed_run_id,
        },
    )
    assert resp.status_code == 400
    assert "doesn't cover" in resp.json()["detail"]


def test_run_order_event_reflects_the_ancestors_scope_not_the_full_graph(client):
    resp = client.post(
        "/api/runs",
        json={"graph": _graph(), "dry_run": True, "run_mode": "ancestors", "target_node_id": "judge"},
    )
    run_id = resp.json()["run_id"]
    with client.websocket_connect(f"/api/runs/{run_id}/ws") as ws:
        events = [ws.receive_json()]
        if events[0]["type"] == "resync" and events[0].get("status") != "running":
            order_event = None
        else:
            while events[-1]["type"] != "run_complete":
                events.append(ws.receive_json())
            order_event = next((e for e in events if e["type"] == "run_order"), None)
    if order_event is not None:
        assert set(order_event["order"]) == {"src", "ds", "engine", "prompt", "judge"}
        assert "eval" not in order_event["order"]


def test_run_order_event_for_self_only_scope_is_just_the_target(client):
    seed_run_id = _start(client)
    _wait_for_run(client, seed_run_id)

    resp = client.post(
        "/api/runs",
        json={
            "graph": _graph(), "dry_run": True, "run_mode": "self_only",
            "target_node_id": "judge", "seed_run_id": seed_run_id,
        },
    )
    run_id = resp.json()["run_id"]
    with client.websocket_connect(f"/api/runs/{run_id}/ws") as ws:
        events = [ws.receive_json()]
        if events[0]["type"] == "resync" and events[0].get("status") != "running":
            order_event = None
        else:
            while events[-1]["type"] != "run_complete":
                events.append(ws.receive_json())
            order_event = next((e for e in events if e["type"] == "run_order"), None)
    if order_event is not None:
        assert order_event["order"] == ["judge"]


def test_locked_nodes_are_seeded_and_skipped(client):
    # A baseline run produces results to reuse.
    seed_run_id = _start(client)
    seed_final = _wait_for_run(client, seed_run_id)
    assert seed_final["status"] == "done"

    # Lock src + ds: a global run seeds them from the baseline and executes only the rest.
    run_id = _start(client, locked_node_ids=["src", "ds"], seed_run_id=seed_run_id)
    final = _wait_for_run(client, run_id)
    assert final["status"] == "done"
    # Locked nodes are not in the executed order; everything downstream is.
    assert "src" not in final["order"] and "ds" not in final["order"]
    assert {"engine", "prompt", "judge", "eval"} <= set(final["order"])
    # Their results are still present (seeded), and match the baseline (reused, not recomputed).
    assert final["node_results"]["ds"] == seed_final["node_results"]["ds"]
    assert final["node_results"]["src"] == seed_final["node_results"]["src"]


def test_locked_nodes_require_seed_run_id(client):
    resp = client.post(
        "/api/runs", json={"graph": _graph(), "dry_run": True, "locked_node_ids": ["ds"]}
    )
    assert resp.status_code == 400
    assert "seed_run_id" in resp.json()["detail"]


def test_locked_node_not_covered_by_seed_run_is_400(client):
    # A seed run covering only an unrelated lone node — can't reuse 'ds' from it.
    lone = {"nodes": [{"id": "engine", "type": "lm_engine", "params": {}}], "edges": []}
    seed_id = client.post("/api/runs", json={"graph": lone, "dry_run": True}).json()["run_id"]
    _wait_for_run(client, seed_id)
    resp = client.post(
        "/api/runs",
        json={"graph": _graph(), "dry_run": True, "locked_node_ids": ["ds"], "seed_run_id": seed_id},
    )
    assert resp.status_code == 400
    assert "no result for locked" in resp.json()["detail"]
