"""Node `outputs` (added to NodeResultOut for the secondary-tab viewers) must survive a
real HTTP round-trip — including the Dataset node's `labels` output, whose values are
`AggregatedHumanRecord` dataclass instances, not plain dicts.
"""

import time

from fastapi.testclient import TestClient

import vejudge.config as config
from vejudge.interface.server.app import create_app


def _wait_for_run(client, run_id, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = client.get(f"/api/runs/{run_id}")
        if resp.json()["status"] != "running":
            return resp.json()
        time.sleep(0.02)
    raise AssertionError("run did not finish in time")


def test_node_outputs_serialize_over_http(
    tmp_path, monkeypatch, fixture_tree, fake_engine, quick_eval_graph
):
    monkeypatch.setattr(config, "LOGS_ROOT", tmp_path / "logs")
    monkeypatch.setattr(config, "WORKFLOWS_ROOT", tmp_path / "workflows")
    client = TestClient(create_app())

    from vejudge.interface.server.schemas import from_graph_spec

    body = {
        "graph": from_graph_spec(quick_eval_graph).model_dump(),
        "dry_run": False,
        "allow_live": True,
    }
    resp = client.post("/api/runs", json=body)
    assert resp.status_code == 200
    run_id = resp.json()["run_id"]
    final = _wait_for_run(client, run_id)

    assert final["status"] == "done", final
    labels = final["node_results"]["ds"]["outputs"]["labels"]
    assert set(labels) == {"prj-a::0::peanut", "prj-b::0::peanut"}
    assert labels["prj-a::0::peanut"]["scores"]["video_addresses_prompt"] == 4.0
    assert labels["prj-a::0::peanut"]["use_case"] == "visual montage"

    report = final["node_results"]["eval"]["outputs"]["metrics_report"]
    assert report["n_items"] == 2
