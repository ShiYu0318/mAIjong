"""Build the practice scenario catalogue (backend/data/scenarios.json) from rule self-play.

uv run python scripts/generate_scenarios.py
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ai.agents.rule_agent import RuleAgent  # noqa: E402
from ai.explainability.candidate_scorer import score_all_discards  # noqa: E402
from engine import tiles  # noqa: E402
from engine.actions import ActionType  # noqa: E402
from engine.game import (  # noqa: E402
    Phase,
    acting_players,
    apply_action,
    get_legal_actions,
    new_game,
)
from engine.shanten import shanten  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "backend" / "data" / "scenarios.json"
WANT = {"one_away": 15, "ready_choice": 15, "defense": 10, "call": 10, "early": 5}
TITLES = {
    "one_away": "一向聽：打哪張進張最多",
    "ready_choice": "聽牌選擇：聽哪裡比較好",
    "defense": "防守：對手已宣告聽牌",
    "call": "吃碰判斷：要不要叫牌",
    "early": "早巡整理：先丟哪張",
}


def classify(s, p) -> tuple[str, str] | None:
    legal = get_legal_actions(s, p)
    n_melds = len(s.melds[p])
    counts = tiles.to_counts(s.hands[p])
    if s.phase is Phase.RESPONSE:
        calls = [a for a in legal if a.type in (ActionType.PON, ActionType.CHI_LOW,
                                                 ActionType.CHI_MID, ActionType.CHI_HIGH)]
        if calls and not any(a.type is ActionType.HU for a in legal):
            _, t = s.last_discard
            verb = "碰" if any(a.type is ActionType.PON for a in calls) else "吃"
            return "call", f"對手打出 {tiles.name(t)}，你可以{verb}。要叫嗎？"
        return None
    if s.phase is not Phase.DISCARD or s.declared_ting[p] or s.turn != p:
        return None
    discards = {a.tile for a in legal if a.type is ActionType.DISCARD}
    if len(discards) < 5:
        return None
    if any(s.declared_ting[q] for q in range(4) if q != p) and shanten(counts, n_melds) >= 1:
        return "defense", "有對手已經宣告聽牌，你離聽牌還有距離。這一張要怎麼打才不會放槍？"
    cands = score_all_discards(s, p)
    if not cands:
        return None
    best = cands[0]
    if best.shanten_after == 0:
        tenpai = [c for c in cands if c.shanten_after == 0]
        if len(tenpai) >= 2 and len({tuple(c.waits) for c in tenpai}) >= 2:
            return "ready_choice", f"有 {len(tenpai)} 種打法都能聽牌，聽的牌和台數不同，選哪一個？"
        return None
    if best.shanten_after == 1 and len(cands) >= 2 and cands[1].shanten_after == 1 \
            and best.uke_count - cands[1].uke_count >= 4:
        return "one_away", f"一向聽，最好的打法有 {best.uke_count} 張進張。找找看是哪一張。"
    if sum(s.n_discards) <= 6 and best.shanten_after >= 3:
        return "early", "剛開局，手牌很散。先丟哪一張最不吃虧？"
    return None


def main() -> None:
    rng = random.Random(20261010)
    found: dict[str, list[dict]] = {k: [] for k in WANT}
    attempts = 0
    while any(len(found[k]) < n for k, n in WANT.items()) and attempts < 3000:
        attempts += 1
        seed = rng.randrange(2**31)
        agents = [RuleAgent(0.0, seed * 4 + i) for i in range(4)]
        s = new_game(seed=seed)
        step = 0
        used = False
        while s.phase is not Phase.ENDED and step < 400 and not used:
            for p in acting_players(s):
                c = classify(s, p)
                if c and len(found[c[0]]) < WANT[c[0]] and rng.random() < 0.35:
                    kind, desc = c
                    found[kind].append({"seed": seed, "step": step, "seat": p, "category": kind,
                                        "description": desc})
                    used = True
                    break
            if used:
                break
            p = acting_players(s)[0]
            s, _ = apply_action(s, p, agents[p].act(s, p, get_legal_actions(s, p)))
            step += 1
    out = []
    for kind, items in found.items():
        for i, it in enumerate(items, start=1):
            out.append({"id": f"{kind}-{i:02d}", "title": f"{TITLES[kind]}（{i}）", **it})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(out)} scenarios from {attempts} games → {OUT}")
    for k in WANT:
        print(f"  {k}: {len(found[k])}")


if __name__ == "__main__":
    main()
