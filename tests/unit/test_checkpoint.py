from vejudge.checkpoint import CheckpointStore


def test_put_get_has(tmp_path):
    s = CheckpointStore(tmp_path / "ckpt.jsonl")
    assert not s.has("a")
    s.put("a", {"score": 3})
    assert s.has("a") and "a" in s
    assert s.get("a") == {"score": 3}
    assert s.get("missing") is None
    assert len(s) == 1


def test_persists_across_reopen(tmp_path):
    p = tmp_path / "ckpt.jsonl"
    s1 = CheckpointStore(p)
    s1.put("x::M3", {"parsed": {"score_1_to_5": 4}})
    s1.put("x::M5", {"parsed": {"score_1_to_5": 2}})

    s2 = CheckpointStore(p)  # resume = reopen the same file
    assert s2.has("x::M3") and s2.has("x::M5")
    assert s2.get("x::M3")["parsed"]["score_1_to_5"] == 4
    assert sorted(s2.keys()) == ["x::M3", "x::M5"]


def test_last_write_wins(tmp_path):
    p = tmp_path / "ckpt.jsonl"
    s = CheckpointStore(p)
    s.put("k", 1)
    s.put("k", 2)
    assert CheckpointStore(p).get("k") == 2


def test_skips_torn_last_line(tmp_path):
    p = tmp_path / "ckpt.jsonl"
    s = CheckpointStore(p)
    s.put("good", {"v": 1})
    with open(p, "a", encoding="utf-8") as f:
        f.write('{"key": "bad", "value": {"v": 2')  # truncated write (crash mid-line)
    s2 = CheckpointStore(p)
    assert s2.has("good") and not s2.has("bad")
