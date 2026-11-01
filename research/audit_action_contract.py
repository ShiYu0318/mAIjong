"""Reproduce the archived label/deployment DISCARD-versus-TING contract discrepancy."""

import hashlib
import json
from pathlib import Path

from ai.agents import LEVEL5_PARAMS, RuleAgent
from ai.rollout_q import _rollout, candidates
from engine.actions import Action, ActionType, encode_action
from engine.game import Phase, acting_players, apply_action, get_legal_actions, new_game

ROOT = Path(__file__).resolve().parents[1]


def main():
    for seed in range(32):
        state = new_game(seed=seed)
        agents = [RuleAgent(0.0, seed * 4 + p, params=LEVEL5_PARAMS) for p in range(4)]
        prefix = []
        while state.phase is not Phase.ENDED:
            seat = acting_players(state)[0]
            legal = get_legal_actions(state, seat)
            action = agents[seat].act(state, seat, legal)
            if state.phase is Phase.DISCARD and action.type is ActionType.TING:
                tiles = candidates(agents[seat], state, seat, legal)
                if action.tile in tiles:
                    legacy = Action(ActionType.DISCARD, action.tile)
                    after_legacy, _ = apply_action(state, seat, legacy)
                    after_deployed, _ = apply_action(state, seat, action)
                    assert not after_legacy.declared_ting[seat]
                    assert after_deployed.declared_ting[seat]
                    row = {
                        "seed": seed,
                        "seat": seat,
                        "prefix_actions": prefix,
                        "information_contract": "visible-v2",
                        "teacher_action": action.to_dict(),
                        "legacy_label_action": legacy.to_dict(),
                        "legacy_declared_ting": after_legacy.declared_ting[seat],
                        "deployed_declared_ting": after_deployed.declared_ting[seat],
                        "legacy_rollout_payment": _rollout(after_legacy, seat, 712),
                        "deployed_rollout_payment": _rollout(after_deployed, seat, 712),
                        "source_sha256": {
                            name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                            for name in [
                                "ai/rollout_q.py",
                                "ai/agents/rule_agent.py",
                                "ai/danger.py",
                                "engine/game.py",
                            ]
                        },
                        "limitation": "Current source path reproduced; archived datasets lack "
                        "action types, so their affected-row fraction is unknown.",
                    }
                    out = (
                        ROOT
                        / "runs/research-20261101/rollout-action-contract-audit-visible-v2.json"
                    )
                    out.write_text(json.dumps(row, indent=2))
                    display = {k: v for k, v in row.items() if k != "prefix_actions"}
                    print(json.dumps(display, indent=2))
                    return
            prefix.append([seat, encode_action(action)])
            state, _ = apply_action(state, seat, action)
    raise ValueError("No reproducible TING decision was found")


if __name__ == "__main__":
    main()
