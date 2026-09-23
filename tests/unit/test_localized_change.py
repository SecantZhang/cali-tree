"""Tests for the localized source→edited change-map preprocessor."""

import numpy as np
import pytest

PIL = pytest.importorskip("PIL")
from PIL import Image  # noqa: E402

from vejudge.preprocessing.localized_change import (  # noqa: E402
    LocalizedChangeConfig,
    LocalizedChangePreprocessor,
)


def _write_pair(tmp_path):
    """SOURCE = flat gray; EDITED = gray with a white block in the top-left grid cell."""
    base = np.full((300, 300), 128, dtype=np.uint8)
    source = tmp_path / "source.png"
    Image.fromarray(base).save(source)
    edited_arr = base.copy()
    edited_arr[0:100, 0:100] = 255  # top-left 1/9 of the image
    edited = tmp_path / "edited.png"
    Image.fromarray(edited_arr).save(edited)
    return {
        "item_id": "task::Editor",
        "input": {"instruction": "make the corner white", "source_image_path": str(source)},
        "output": {"edited_image_path": str(edited)},
    }


def test_change_map_reports_extent_and_location(tmp_path):
    sample = _write_pair(tmp_path)
    pre = LocalizedChangePreprocessor(cache_root=tmp_path / "cache")
    result = pre.run(sample)

    # ~1/9 of the image changed.
    assert result["changed_extent"] == pytest.approx(1 / 9, abs=0.02)
    assert "top-left" in result["descriptor"]
    assert "partial" in result["descriptor"]  # the descriptor coaches the partial boundary
    # The change-map PNG and its metadata sidecar are cached on disk.
    assert (tmp_path / "cache").exists()
    from pathlib import Path
    assert Path(result["change_map_path"]).is_file()


def test_cache_key_is_stable_and_reused(tmp_path):
    sample = _write_pair(tmp_path)
    pre = LocalizedChangePreprocessor(cache_root=tmp_path / "cache")
    first = pre.run(sample)
    key = pre.cache_key(sample)
    # Deterministic key; a second run reads the cached artifact (identical result).
    assert pre.cache_key(sample) == key
    second = pre.run(sample)
    assert second == first
    assert first["cache_key"] == key


def test_config_hash_changes_the_cache_key(tmp_path):
    sample = _write_pair(tmp_path)
    a = LocalizedChangePreprocessor(
        cache_root=tmp_path / "c", config=LocalizedChangeConfig(threshold=0.12)
    )
    b = LocalizedChangePreprocessor(
        cache_root=tmp_path / "c", config=LocalizedChangeConfig(threshold=0.30)
    )
    assert a.cache_key(sample) != b.cache_key(sample)
