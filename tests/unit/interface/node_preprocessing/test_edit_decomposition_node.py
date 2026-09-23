from vejudge.interface.node_preprocessing import edit_decomposition_node
from vejudge.interface.node_preprocessing.edit_decomposition_node import (
    EditDecompositionNodeExecutor,
)


def test_dry_run_never_requires_video_binaries(tmp_path, make_ctx, monkeypatch):
    video = tmp_path / "video.mp4"
    video.write_bytes(b"not a real video, dry run only hashes it")
    monkeypatch.setattr(edit_decomposition_node.config, "EVIDENCE_ROOT", tmp_path / "evidence")
    samples = {
        "item": {
            "item_id": "item",
            "output": {"output_video_path": str(video)},
        }
    }
    result = EditDecompositionNodeExecutor().run(
        make_ctx(inputs={"samples": samples}, dry_run=True)
    )
    assert result.status == "done"
    assert result.meta["would_decompose"] == 1
    assert result.outputs["evidence_bundle"]["manifests"] == {}
