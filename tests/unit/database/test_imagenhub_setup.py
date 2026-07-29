import hashlib

from run.setup_imagenhub import build_asset_manifest, download


def test_asset_manifest_hashes_materialized_files_and_ignores_partial_files(tmp_path):
    (tmp_path / "inputs").mkdir()
    (tmp_path / "inputs" / "sample.jpg").write_bytes(b"image")
    (tmp_path / "unfinished.jpg.part").write_bytes(b"partial")
    manifest = build_asset_manifest(tmp_path, [{"uid": "sample"}])
    assert manifest["revision"] == "a393c006cd0c843d8ca57ae4a6ee954ee376ef67"
    assert manifest["tasks"] == 1
    assert manifest["files"] == {
        "inputs/sample.jpg": {
            "bytes": 5,
            "sha256": hashlib.sha256(b"image").hexdigest(),
        },
    }


def test_download_reuses_existing_nonempty_asset_without_network(tmp_path, monkeypatch):
    path = tmp_path / "asset.jpg"
    path.write_bytes(b"complete")
    monkeypatch.setattr(
        "run.setup_imagenhub.requests.get",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("network called")),
    )
    download("https://example.invalid/asset.jpg", path)
    assert path.read_bytes() == b"complete"
