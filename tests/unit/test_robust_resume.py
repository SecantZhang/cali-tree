import json
import logging

from vejudge.benchmark import robust
from vejudge.benchmark.human_gap import HumanGapBenchmark
from vejudge.checkpoint import CheckpointStore


def _make_cell_dir(root, name, complete):
    d = root / name
    d.mkdir()
    with open(d / "per_judge_summary.csv", "w") as f:
        f.write("judge_signal,n_items,spearman\n")  # header
        if complete:
            f.write("M5.score_1_to_5,5,0.4\n")  # a data row
    return d


def test_cell_is_complete(tmp_path):
    done = _make_cell_dir(tmp_path, "temp0.0_rep1-exps", complete=True)
    empty = _make_cell_dir(tmp_path, "temp0.0_rep2-exps", complete=False)
    missing = tmp_path / "temp0.0_rep3-exps"
    assert robust.cell_is_complete(done) is True
    assert robust.cell_is_complete(empty) is False
    assert robust.cell_is_complete(missing) is False


def test_scan_complete_cells(tmp_path):
    _make_cell_dir(tmp_path, "temp0.0_rep1-exps", complete=True)
    _make_cell_dir(tmp_path, "temp1.0_rep2-exps", complete=True)
    _make_cell_dir(tmp_path, "temp1.0_rep3-exps", complete=False)  # incomplete
    cells = robust.scan_complete_cells(tmp_path)
    keys = {(c["temperature"], c["repeat"]) for c in cells}
    assert keys == {(0.0, 1), (1.0, 2)}
    assert all(c["run_dir"].endswith("-exps") for c in cells)


def test_find_last_robust_dir(tmp_path, monkeypatch):
    import vejudge.config as cfg
    monkeypatch.setattr(cfg, "LOGS_ROOT", tmp_path)
    (tmp_path / "exps").mkdir()
    (tmp_path / "exps" / "260101-00:00:00-robust").mkdir()
    (tmp_path / "exps" / "260102-00:00:00-robust").mkdir()
    (tmp_path / "exps" / "260103-00:00:00-exps").mkdir()  # not a robust dir
    last = robust.find_last_robust_dir()
    assert last.name == "260102-00:00:00-robust"


def test_load_grid_config(tmp_path):
    cfg = {"temperatures": [0.0, 1.0], "repeats": 3, "model": "peanut"}
    (tmp_path / "robust_config.json").write_text(json.dumps(cfg))
    assert robust.load_grid_config(tmp_path)["repeats"] == 3
    assert robust.load_grid_config(tmp_path / "nope") == {}


def test_runner_reuses_cached_calls(tmp_path):
    # All (item, metric) already checkpointed -> zero engine calls this session.
    store = CheckpointStore(tmp_path / "judge_results.jsonl")
    store.put("i1::M3", {"judge": "M3", "parsed": {"score_1_to_5": 4}})

    bench = HumanGapBenchmark(judges=["M3"], concurrency=1)  # M3 is text-only
    samples = {"i1": {"input": {"user_prompt": "x"}, "output": {}}}
    per_item, session = bench._run_judges_concurrent(
        samples, engines=None, run=None, log=logging.getLogger("t"), store=store
    )
    assert session == []  # nothing was called
    assert per_item["i1"]["M3"]["parsed"]["score_1_to_5"] == 4
