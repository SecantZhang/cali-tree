"""Freeze the new validation sources and their unchanged optimized rubrics."""

from collections import Counter
import hashlib
import json
from pathlib import Path

from critical import config
from critical.core.optimization.prompt.calitree.decomposition.visual_calibration import source_pixels


def test_calibrated_holdout_has_disjoint_source_pixels_and_unchanged_category_prompts():
    directory = Path(__file__).parent / "fixtures"
    data = json.loads((directory / "aurora_vision_calibrated_holdout32.json").read_text())
    prior = [c for name in ("optimized_aurora_prompts.json", "aurora_vision_holdout.json",
                           "aurora_vision_fresh64.json", "aurora_vision_grounded_holdout64.json",
                           "aurora_vision_intent_holdout64.json")
             for c in json.loads((directory / name).read_text())["cases"].values()]
    cases = data["cases"]
    assert len(cases) == 32
    assert Counter(c["task"] for c in cases.values()) == {t: 4 for t in ("ag", "clevr", "emu", "epic", "kubric", "magicbrush", "something", "whatsup")}
    assert not {c["task_uid"] for c in cases.values()} & {c["task_uid"] for c in prior}
    prior_pixels = {source_pixels(config.PROJECT_ROOT / c["source_image"]) for c in prior}
    assert set(data["provenance"]["excluded_source_pixels"]) == prior_pixels
    assert len({c["source_pixel_sha256"] for c in cases.values()}) == 32
    assert not {c["source_pixel_sha256"] for c in cases.values()} & prior_pixels
    assert len(data["provenance"]["unused_task_uids_reusing_seen_pixels"]) == 4
    earlier = json.loads((directory / "aurora_vision_intent_holdout64.json").read_text())
    optimized = {c["task"]: c["optimized_prompt_sha256"] for c in earlier["cases"].values()}
    for digest, prompt in data["prompts"].items():
        assert hashlib.sha256(prompt.encode()).hexdigest() == digest
    for c in cases.values():
        for role in ("source", "edited"):
            path = config.PROJECT_ROOT / c[f"{role}_image"]
            assert hashlib.sha256(path.read_bytes()).hexdigest() == c[f"{role}_image_sha256"]
        assert source_pixels(config.PROJECT_ROOT / c["source_image"]) == c["source_pixel_sha256"]
        assert c["optimized_prompt_sha256"] == optimized[c["task"]]
        score = c["human_score"]
        assert c["target_label"] == ("no" if score < 0.5 else "partial" if score < 1.5 else "yes")
