"""Evaluate an agent locally against reference opponents.

python -m maijong_sdk.evaluate --agent my_agent.py:MyAgent --opponent greedy --games 1000
(`my_module:MyAgent` on the import path works too)
"""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import sys
from pathlib import Path

from maijong_sdk.agents import GreedyAgent, RandomAgent
from maijong_sdk.base_agent import BaseAgent
from maijong_sdk.runner import play_hand


def load_agent(spec: str) -> BaseAgent:
    """`path/to/file.py:ClassName` (same as `maijong pack`) or `package.module:ClassName`."""
    module, _, cls = spec.partition(":")
    if module.endswith(".py"):
        path = Path(module).resolve()
        sys.path.insert(0, str(path.parent))  # let the agent import its sibling files
        mod_spec = importlib.util.spec_from_file_location(path.stem, path)
        if mod_spec is None or mod_spec.loader is None:
            raise ImportError(f"cannot load {module}")
        mod = importlib.util.module_from_spec(mod_spec)
        mod_spec.loader.exec_module(mod)
    else:
        sys.path.insert(0, str(Path.cwd()))
        mod = importlib.import_module(module)
    agent = getattr(mod, cls)()
    if not isinstance(agent, BaseAgent):
        raise TypeError(f"{spec} is not a BaseAgent subclass")
    return agent


def opponent(name: str, seed: int) -> BaseAgent:
    return GreedyAgent() if name == "greedy" else RandomAgent(seed)


def evaluate(agent: BaseAgent, opponent_name: str = "greedy", games: int = 100,
             seed: int = 0) -> dict[str, float]:
    wins = deal_ins = 0
    score = 0
    for k in range(games):
        seat = k % 4
        agents = [agent if p == seat else opponent(opponent_name, seed + k * 4 + p)
                  for p in range(4)]
        r = play_hand(agents, seed + k).result
        score += r["payments"][seat]
        if r["kind"] == "HU" and r["winner"] == seat:
            wins += 1
        elif r["kind"] == "HU" and r.get("loser") == seat and not r.get("self_draw"):
            deal_ins += 1
    return {"games": games, "win_rate": wins / games, "deal_in_rate": deal_ins / games,
            "avg_score": score / games}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--agent", required=True, help="file.py:ClassName or module:ClassName")
    ap.add_argument("--opponent", choices=["greedy", "random"], default="greedy")
    ap.add_argument("--games", type=int, default=100)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    res = evaluate(load_agent(args.agent), args.opponent, args.games, args.seed)
    print(f"{res['games']} hands vs {args.opponent}: win {res['win_rate']:.1%}, "
          f"deal-in {res['deal_in_rate']:.1%}, average score {res['avg_score']:.1f}")


if __name__ == "__main__":
    main()
