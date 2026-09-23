"""GET /api/media — path-confined file streaming."""

import pytest
from fastapi.testclient import TestClient

import vejudge.config as config
from vejudge.interface.server.app import create_app
from vejudge.interface.server.routes import media


@pytest.fixture
def client(tmp_path, monkeypatch):
    rendered_root = tmp_path / "rendered"
    data_root = tmp_path / "data"
    evidence_root = tmp_path / "evidence"
    rendered_root.mkdir()
    data_root.mkdir()
    evidence_root.mkdir()
    monkeypatch.setattr(config, "RENDERED_ROOT", rendered_root)
    monkeypatch.setattr(config, "DATA_ROOT", data_root)
    monkeypatch.setattr(config, "EVIDENCE_ROOT", evidence_root)
    monkeypatch.setattr(media, "ALLOWED_ROOTS", (rendered_root, data_root, evidence_root))
    app = create_app()
    return TestClient(app), rendered_root, data_root, evidence_root


def test_serves_a_real_file_inside_an_allowed_root(client):
    c, rendered_root, _, _ = client
    video = rendered_root / "prj-a" / "videos"
    video.mkdir(parents=True)
    (video / "clip.mp4").write_bytes(b"fake-mp4-bytes")

    resp = c.get("/api/media", params={"path": str(video / "clip.mp4")})
    assert resp.status_code == 200
    assert resp.content == b"fake-mp4-bytes"


def test_rejects_a_path_outside_every_allowed_root(client, tmp_path):
    c, _, _, _ = client
    outside = tmp_path / "outside" / "secret.mp4"
    outside.parent.mkdir(parents=True)
    outside.write_bytes(b"nope")

    resp = c.get("/api/media", params={"path": str(outside)})
    assert resp.status_code == 404


def test_rejects_a_path_traversal_attempt_out_of_an_allowed_root(client, tmp_path):
    c, rendered_root, _, _ = client
    outside = tmp_path / "outside" / "secret.mp4"
    outside.parent.mkdir(parents=True)
    outside.write_bytes(b"nope")

    traversal_path = str(rendered_root / ".." / "outside" / "secret.mp4")
    resp = c.get("/api/media", params={"path": traversal_path})
    assert resp.status_code == 404


def test_rejects_a_missing_file_even_inside_an_allowed_root(client):
    c, rendered_root, _, _ = client
    resp = c.get("/api/media", params={"path": str(rendered_root / "does_not_exist.mp4")})
    assert resp.status_code == 404


def test_rejects_a_directory_even_inside_an_allowed_root(client):
    c, rendered_root, _, _ = client
    a_dir = rendered_root / "some_dir"
    a_dir.mkdir()
    resp = c.get("/api/media", params={"path": str(a_dir)})
    assert resp.status_code == 404


def test_serves_a_file_inside_the_second_allowed_root_too(client):
    c, _, data_root, _ = client
    asset = data_root / "prj-a" / "user_query.json"
    asset.parent.mkdir(parents=True)
    asset.write_bytes(b'{"prompts": []}')

    resp = c.get("/api/media", params={"path": str(asset)})
    assert resp.status_code == 200
    assert resp.content == b'{"prompts": []}'


def test_serves_a_cached_evidence_artifact(client):
    c, _, _, evidence_root = client
    clip = evidence_root / "objects" / "ab" / "clip.mp4"
    clip.parent.mkdir(parents=True)
    clip.write_bytes(b"evidence-clip")
    response = c.get("/api/media", params={"path": str(clip)})
    assert response.status_code == 200
    assert response.content == b"evidence-clip"
