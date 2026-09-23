"""Loading a past run from disk: reconstruction, the disk-fallback GET, /graph, /disk list,
and that a completed run persists run_results.json for faithful future reconstruction."""

import json

import pytest
from fastapi.testclient import TestClient

import vejudge.config as config
from vejudge.interface.server import run_manager
from vejudge.interface.server.app import create_app


@pytest.fixture
def logs(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "LOGS_ROOT", tmp_path / "logs")
    monkeypatch.setattr(config, "DATA_ROOT", tmp_path / "data")
    monkeypatch.setattr(config, "RENDERED_ROOT", tmp_path / "rendered")
    monkeypatch.setattr(config, "WORKFLOWS_ROOT", tmp_path / "workflows")
    return tmp_path / "logs"


def _write_run(run_id, *, status="done", results=False):
    d = run_manager.run_dir_for(run_id)
    d.mkdir(parents=True)
    (d / "run_config.json").write_text(json.dumps({
        "benchmark": "interface_graph", "dry_run": True, "allow_live": False,
        "n_nodes": 3, "node_types": ["peanut_source", "judge", "eval"], "workflow_name": "wf",
    }))
    (d / "workflow_graph.json").write_text(json.dumps({
        "nodes": [{"id": "src", "type": "peanut_source", "params": {}},
                  {"id": "jd", "type": "judge", "params": {}},
                  {"id": "ev", "type": "eval", "params": {}}],
        "edges": [{"source": "src", "source_socket": "raw_dataset", "target": "jd", "target_socket": "samples"}],
    }))
    (d / "run_status.json").write_text(json.dumps({"status": status, "error": None, "finished_at": "t"}))
    # Eval node's own output file + a judge checkpoint line.
    (d / "eval_ev.json").write_text(json.dumps({"n_items": 2, "per_dimension": {}}))
    (d / "judge_results.jsonl").write_text(
        json.dumps({"key": "jd::a::0::M1", "value": {"parsed": {"failure": False}}}) + "\n"
    )
    if results:
        (d / "run_results.json").write_text(json.dumps({
            "order": ["src", "jd", "ev"],
            "node_results": {"src": {"status": "done", "error": None, "meta": {}, "outputs": {}}},
        }))
    return d


def test_reconstruct_recovers_eval_output_and_reassembles_judge(logs):
    d = _write_run("260720-11:00:00")
    reco = run_manager.reconstruct_node_results(d)
    nr = reco["node_results"]
    assert nr["ev"]["outputs"]["metrics_report"]["n_items"] == 2   # eval file = output
    assert nr["jd"]["outputs"]["judge_result"]["a::0"]["M1"]["parsed"]["failure"] is False
    assert nr["src"]["status"] == "done"  # inferred (overall done)


def test_reconstruct_prefers_persisted_run_results(logs):
    d = _write_run("260720-11:05:00", results=True)
    reco = run_manager.reconstruct_node_results(d)
    # run_results.json wins (faithful) — its src entry, not the reconstruction's.
    assert reco["order"] == ["src", "jd", "ev"]
    assert set(reco["node_results"]) == {"src"}


def test_failed_run_infers_neutral_status_for_artifactless_nodes(logs):
    d = _write_run("260720-11:10:00", status="error")
    nr = run_manager.reconstruct_node_results(d)["node_results"]
    assert nr["src"]["status"] == "idle"     # unrecoverable per-node status pre-persistence
    assert nr["ev"]["status"] == "done"      # has an artifact


def test_disk_endpoints(logs):
    _write_run("260720-12:00:00")
    client = TestClient(create_app())
    # /disk lists the run
    runs = client.get("/api/runs/disk").json()
    assert any(r["run_id"] == "260720-12:00:00" and r["workflow_name"] == "wf" for r in runs)
    # /{id}/graph returns the saved graph
    g = client.get("/api/runs/260720-12:00:00/graph").json()
    assert [n["id"] for n in g["nodes"]] == ["src", "jd", "ev"]
    # /{id} disk fallback (not in the in-memory registry) reconstructs node_results
    st = client.get("/api/runs/260720-12:00:00").json()
    assert st["status"] == "done"
    assert st["node_results"]["ev"]["outputs"]["metrics_report"]["n_items"] == 2
    # a genuinely absent run is still a 404
    assert client.get("/api/runs/nope").status_code == 404


def test_completed_run_persists_run_results(logs):
    client = TestClient(create_app())
    body = {"graph": {"nodes": [{"id": "src", "type": "peanut_source", "params": {}}], "edges": []},
            "dry_run": True, "allow_live": False}
    rid = client.post("/api/runs", json=body).json()["run_id"]
    # Poll for the persisted snapshot (written just after the run goes terminal).
    import time as _t
    results_path = run_manager.run_dir_for(rid) / "run_results.json"
    for _ in range(100):
        if results_path.is_file():
            break
        _t.sleep(0.05)
    assert results_path.is_file()
    saved = json.loads(results_path.read_text())
    assert "src" in saved["node_results"] and "order" in saved
