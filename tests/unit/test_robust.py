import csv

from vejudge.benchmark import robust


def test_bootstrap_brackets_point_estimate():
    human = [1, 2, 3, 4, 5, 4, 3, 2]
    judge = [1, 2, 3, 4, 5, 4, 3, 2]  # perfect monotonic -> spearman ~1
    lo, hi = robust.bootstrap_spearman(human, judge, n_boot=300, seed=1)
    assert lo is not None and hi is not None
    assert lo <= 1.0 and hi <= 1.0001 and lo > 0.5


def test_bootstrap_too_few_returns_none():
    assert robust.bootstrap_spearman([1, 2], [1, 2]) == (None, None)


def test_self_consistency_identical_repeats():
    rep = {"a": 5.0, "b": 3.0, "c": 1.0, "d": 4.0}
    within, run2run = robust.self_consistency([dict(rep), dict(rep), dict(rep)])
    assert within == 0.0
    assert run2run is not None and abs(run2run - 1.0) < 1e-9


def test_self_consistency_noisy_repeats():
    r1 = {"a": 5.0, "b": 3.0, "c": 1.0, "d": 4.0}
    r2 = {"a": 1.0, "b": 4.0, "c": 5.0, "d": 2.0}  # very different
    within, run2run = robust.self_consistency([r1, r2])
    assert within is not None and within > 0
    assert run2run is not None and run2run < 0.8


def test_self_consistency_single_repeat_none():
    assert robust.self_consistency([{"a": 1.0}]) == (None, None)


def _make_cell(tmp_path, name, summary_rows, gap_rows):
    d = tmp_path / name
    d.mkdir()
    with open(d / "per_judge_summary.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(summary_rows[0].keys()))
        w.writeheader()
        w.writerows(summary_rows)
    with open(d / "per_judge_gap.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(gap_rows[0].keys()))
        w.writeheader()
        w.writerows(gap_rows)
    return d


def test_grid_and_summary_builders(tmp_path):
    def summary(spear):
        return [{"judge_signal": "M5.score_1_to_5", "n_items": 4,
                 "mean_human": 3.0, "mean_judge": 2.0,
                 "mean_gap_signed": -1.0, "mae": 1.0, "spearman": spear}]

    def gap(jvals):
        return [{"item_id": it, "project": "p", "use_case": "u",
                 "judge_signal": "M5.score_1_to_5", "n_human_dims": 1,
                 "human": h, "judge": j, "gap_signed": j - h, "abs_gap": abs(j - h)}
                for it, h, j in jvals]

    items = [("i1", 4, 2), ("i2", 3, 2), ("i3", 2, 1), ("i4", 5, 3)]
    c1 = _make_cell(tmp_path, "c1", summary(0.8), gap(items))
    c2 = _make_cell(tmp_path, "c2", summary(0.6), gap(items))  # identical judge values

    cells = [
        {"temperature": 0.0, "repeat": 1, "run_id": "c1", "run_dir": str(c1)},
        {"temperature": 0.0, "repeat": 2, "run_id": "c2", "run_dir": str(c2)},
    ]
    grid = robust.build_grid_rows(cells)
    assert len(grid) == 2
    assert all(r["judge_signal"] == "M5.score_1_to_5" for r in grid)
    assert all(r["ci_low"] is not None for r in grid)  # 4 items -> bootstrap runs

    summ = robust.build_summary_rows(cells)
    assert len(summ) == 1
    row = summ[0]
    assert row["n_repeats"] == 2
    assert row["within_item_std_mean"] == 0.0  # identical judge values across repeats
    assert abs(row["run_to_run_spearman_mean"] - 1.0) < 1e-9
