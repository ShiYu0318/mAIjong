from pathlib import Path

from ai.danger import safe_against, tile_danger
from ai.simulate import read_records, replay_states, run_batch
from engine.actions import decode_action
from engine.game import apply_action, new_game


def test_batch_stats_and_replayable_records(tmp_path: Path):
    path = tmp_path / "r.jsonl.gz"
    res = run_batch(["rule", "random", "rule:1.5", "random"], 20, seed=3, save_path=path)
    s = res.summary()
    assert s["hands"] == 20 and len(s["seats"]) == 4
    assert sum(x["avg_score"] for x in s["seats"]) == 0
    records = list(read_records(path))
    assert len(records) == 20
    rec = records[0]
    steps = list(replay_states(rec["seed"], rec["actions"]))
    assert len(steps) == len(rec["actions"])
    state, p, aid = steps[-1]
    final, _ = apply_action(state, p, decode_action(aid))
    assert final.result == rec["result"]


def test_safe_tiles_after_declaration():
    s = new_game(seed=11)
    # force a declaration flag and a later discard to check bookkeeping
    s.declared_ting[1] = True
    s.events.append({"seq": len(s.events), "type": "TING", "player": 1, "tile": 5})
    s.events.append({"seq": len(s.events), "type": "DISCARD", "player": 2, "tile": 7})
    assert safe_against(s, 1) == {5, 7}
    assert tile_danger(s, 0, 7) == 0.0
    assert tile_danger(s, 0, 13) > 0.0
    assert safe_against(s, 2) == set()
